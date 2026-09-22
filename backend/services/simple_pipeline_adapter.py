"""
Simplified pipeline adapter — integrated new progress system
"""

import json
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from backend.services.simple_progress import emit_progress, clear_progress
from backend.pipeline.step1_outline import run_step1_outline
from backend.pipeline.step2_timeline import run_step2_timeline
from backend.pipeline.step3_scoring import run_step3_scoring
from backend.pipeline.step4_title import run_step4_title
from backend.pipeline.step5_clustering import run_step5_clustering
from backend.pipeline.step6_video import run_step6_video

logger = logging.getLogger(__name__)


def check_duration_regression_canary(clips: list, stage_name: str = "selection") -> None:
    """
    Computes duration distribution of selected clips.
    If >80% of clips are under 75 seconds, emits an explicit warning canary.
    """
    if not clips:
        return
    
    from backend.utils.text_processor import TextProcessor
    tp = TextProcessor()
    durations = []
    for c in clips:
        st = c.get('start_time', '00:00:00')
        et = c.get('end_time', '00:00:00')
        try:
            dur = max(0.0, tp.time_to_seconds(et) - tp.time_to_seconds(st))
            durations.append(dur)
        except Exception:
            pass

    if not durations:
        return

    under_75 = sum(1 for d in durations if d < 75.0)
    pct_under_75 = (under_75 / len(durations)) * 100.0
    avg_dur = sum(durations) / len(durations)
    max_dur = max(durations)
    min_dur = min(durations)

    logger.info(
        f"[Duration Distribution @ {stage_name}] Total clips: {len(durations)}, "
        f"Avg: {avg_dur:.1f}s, Min: {min_dur:.1f}s, Max: {max_dur:.1f}s, "
        f"Under 75s: {under_75}/{len(durations)} ({pct_under_75:.1f}%)"
    )

    if pct_under_75 >= 80.0:
        logger.warning(
            "WARNING: clip duration distribution looks suspiciously short. "
            "Possible bias in Step 1 or Step 3 prompts. Review prompt duration framing."
        )


class SimplePipelineAdapter:
    """Simplified pipeline adapter — using fixed-stage progress system"""
    
    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id
        from backend.core.progress_tracker import get_tracker
        self.tracker = get_tracker(project_id, task_id)
        
    async def _generate_subtitle_automatically(self, video_path: str, metadata_dir: Path) -> Path:
        """
        Auto-generating subtitles file
        
        Args:
            Video file path
            metadata_dir: Metadata directory
            
        Returns:
            Path to generated SRT file, returns None on failure
        """
        try:
            logger.info(f"Starting video {video_path} Auto-caption generation")
            
            # Updating progress
            from backend.services.simple_progress import emit_progress
            emit_progress(self.project_id, "SUBTITLE", "Auto-generating subtitles with AI…", subpercent=25)
            
            # Using Whisper local model to generate subtitles
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                from pathlib import Path
                
                video_file_path = Path(video_path)
                if not video_file_path.exists():
                    logger.error(f"Video file does not exist: {video_path}")
                    return None
                
                logger.info("Attempting to generate subtitles using Whisper local model")
                output_path = metadata_dir / f"{video_file_path.stem}.srt"
                srt_path = generate_subtitle_for_video(
                    video_file_path,
                    output_path=output_path,
                    method="auto",
                    model="base",
                    language="auto"
                )
                
                if srt_path and srt_path.exists():
                    logger.info(f"WhisperSubtitle generation successful: {srt_path}")
                    emit_progress(self.project_id, "SUBTITLE", "AI subtitle generation complete", subpercent=40)
                    return srt_path
                else:
                    logger.warning("Whisper subtitle generation failed")
                    
            except Exception as e:
                logger.warning(f"Whisper subtitle generation failed: {e}")
            
            logger.error("WhisperSubtitle generation failed")
            return None
            
        except Exception as e:
            logger.error(f"Auto-caption generation failed: {e}")
            return None
        
    async def process_project_sync(self, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        Synchronizing project — using simplified progress system
        
        Args:
            input_video_path: Input video path
            Input SRT path
            
        Returns:
            Processing result
        """
        logger.info(f"Beginning processing project: {self.project_id}")
        input_video_path = Path(input_video_path)
        if input_srt_path:
            input_srt_path = str(input_srt_path)
        
        try:
            # Clearing previous progress data
            clear_progress(self.project_id)
            tracker = self.tracker
            tracker.set_step(0, "Transcribing Audio")
            tracker.log("Starting audio transcription...")
            
            # Creating necessary directory structure — using correct paths
            from backend.core.path_utils import get_project_directory
            project_dir = get_project_directory(self.project_id)
            metadata_dir = project_dir / "metadata"
            output_dir = project_dir / "output"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            # Dedicated output subdirectory within Project
            clips_output_dir = output_dir / "clips"
            collections_output_dir = output_dir / "collections"
            clips_output_dir.mkdir(parents=True, exist_ok=True)
            collections_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Stage 1: Ingest
            emit_progress(self.project_id, "INGEST", "Materials prepared")
            
            # Retrieve project category for category-aware duration and calibrated scoring
            category = "default"
            proj_name = "Viral Highlight"
            try:
                from backend.core.database import SessionLocal
                from backend.services.project_service import ProjectService
                with SessionLocal() as db_session:
                    ps = ProjectService(db_session)
                    proj = ps.get(self.project_id)
                    if proj and proj.name:
                        proj_name = proj.name
                    if proj and (proj.processing_config or proj.settings):
                        cfg = proj.processing_config or proj.settings or {}
                        category = cfg.get("video_category", "default")
            except Exception:
                pass

            # Stage 2: Subtitles & Transcription
            emit_progress(self.project_id, "SUBTITLE", "Starting transcription...")
            
            # Step 1: Outline extraction with category duration calibration
            logger.info(f"Executing Step 1: Outline extraction (Category: {category})")
            tracker.set_step(1, "Finding Key Moments")
            tracker.log(f"Extracting outline candidates (Category: {category})...")
            from ..utils.subtitle_validator import validate_subtitle_file
            existing_meta_srt = metadata_dir / "input.srt"
            if not input_srt_path and existing_meta_srt.exists() and validate_subtitle_file(existing_meta_srt, video_path=input_video_path):
                logger.info(f"Project {self.project_id}: Reusing existing validated transcript from metadata: {existing_meta_srt}")
                input_srt_path = str(existing_meta_srt)

            srt_path: Optional[Path] = None
            outlines = []
            existing_meta_outline = metadata_dir / "step1_outline.json"
            if existing_meta_outline.exists() and existing_meta_outline.stat().st_size > 2:
                try:
                    with open(existing_meta_outline, 'r', encoding='utf-8') as f:
                        cached_outlines = json.load(f)
                    if isinstance(cached_outlines, list) and len(cached_outlines) > 1:
                        logger.info(f"Project {self.project_id}: Reusing existing step1_outline.json with {len(cached_outlines)} moments.")
                        outlines = cached_outlines
                except Exception as oe:
                    logger.warning(f"Failed to read existing step1_outline.json: {oe}")

            if input_srt_path and Path(input_srt_path).exists() and validate_subtitle_file(input_srt_path, video_path=input_video_path):
                logger.info(f"Using validated existing SRT file: {input_srt_path}")
                srt_path = Path(input_srt_path)
                if not outlines:
                    outlines = run_step1_outline(srt_path, metadata_dir=metadata_dir, category=category, tracker=tracker)
            else:
                if input_srt_path and Path(input_srt_path).exists():
                    logger.warning(f"Provided SRT file '{input_srt_path}' failed validation (empty, dummy placeholder, or duration mismatch). Discarding and running Whisper auto-transcription.")
                else:
                    logger.info("No SRT provided, generating subtitles automatically with AI Whisper")
                srt_path = await self._generate_subtitle_automatically(input_video_path, metadata_dir)
                if srt_path and srt_path.exists() and validate_subtitle_file(srt_path, video_path=input_video_path):
                    logger.info(f"AI Subtitles generated successfully: {srt_path}")
                    if not outlines:
                        outlines = run_step1_outline(srt_path, metadata_dir=metadata_dir, category=category, tracker=tracker)
                else:
                    logger.warning("Subtitle generation empty or invalid, setting outlines to empty")
                    outlines = []
                    outline_file = metadata_dir / "step1_outline.json"
                    with open(outline_file, 'w', encoding='utf-8') as f:
                        json.dump(outlines, f, ensure_ascii=False, indent=2)

            # If outlines returned empty or only 1 generic mega-outline for longer videos (> 180s),
            # trigger intelligent multi-moment discovery across footage
            need_auto_discovery = False
            if not outlines:
                need_auto_discovery = True
            elif len(outlines) == 1 and srt_path and srt_path.exists():
                try:
                    from backend.utils.text_processor import TextProcessor
                    import subprocess
                    _tp = TextProcessor()
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(input_video_path)],
                        capture_output=True, text=True
                    )
                    v_dur = float(probe.stdout.strip() or "60")
                    s_sec = _tp.time_to_seconds(outlines[0].get("start_time", "00:00:00"))
                    e_sec = _tp.time_to_seconds(outlines[0].get("end_time", "00:00:00"))
                    if (e_sec - s_sec) > 180.0 or v_dur > 180.0:
                        logger.warning(f"Project {self.project_id}: Single outline extracted from {v_dur:.1f}s video. Triggering intelligent moment discovery across footage.")
                        need_auto_discovery = True
                except Exception:
                    need_auto_discovery = True

            if need_auto_discovery and srt_path and srt_path.exists():
                try:
                    from backend.campaign.moment_finder import auto_discover_moments
                    from backend.utils.text_processor import TextProcessor
                    import subprocess
                    _tp = TextProcessor()
                    segments = _tp.parse_srt(srt_path)
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(input_video_path)],
                        capture_output=True, text=True
                    )
                    v_dur = float(probe.stdout.strip() or "60")
                    discovered = auto_discover_moments(
                        segments=segments,
                        total_duration=v_dur,
                        duration_min=20.0,
                        duration_max=90.0,
                        max_clips=5
                    )
                    if discovered:
                        outlines = [
                            {
                                "title": m.get("moment_name", f"Viral Moment {i+1}"),
                                "subtopics": [m.get("matched_text", "")],
                                "chunk_index": 0,
                                "category": category,
                                "start_time": _tp.seconds_to_time(m["start_sec"]),
                                "end_time": _tp.seconds_to_time(m["end_sec"]),
                                "source_model": "auto_discovery",
                                "confidence": m.get("confidence", "high")
                            }
                            for i, m in enumerate(discovered)
                        ]
                        logger.info(f"Project {self.project_id}: Discovered {len(outlines)} distinct moments across {v_dur:.1f}s footage.")
                        tmp_outline = metadata_dir / "step1_outline.json.tmp"
                        with open(tmp_outline, "w", encoding="utf-8") as f:
                            json.dump(outlines, f, ensure_ascii=False, indent=2)
                        tmp_outline.replace(metadata_dir / "step1_outline.json")
                except Exception as ad_err:
                    logger.warning(f"Project {self.project_id}: Auto-discovery moment fallback failed: {ad_err}")

            tracker.log(f"Identified {len(outlines)} moment candidates")
            emit_progress(self.project_id, "SUBTITLE", "Subtitle processing complete", subpercent=50)
            
            # Stage 3: Content Analysis & Scoring
            emit_progress(self.project_id, "ANALYZE", "Analyzing content & viral moments...")

            # Step 2: Timeline extraction
            logger.info("Executing Step 2: Timeline extraction")
            tracker.set_step(2, "Setting Timestamps")
            tracker.log("Localizing timestamp intervals for moments...")
            if outlines:
                timeline_data = run_step2_timeline(
                    metadata_dir / "step1_outline.json",
                    metadata_dir=metadata_dir,
                    category=category,
                    tracker=tracker
                )
                if not timeline_data:
                    error_msg = f"Step 2 failed to extract any timeline intervals from {len(outlines)} outlines. Pipeline aborted."
                    logger.error(f"Project {self.project_id}: {error_msg}")
                    raise RuntimeError(error_msg)

                tracker.log(f"Set timestamps for {len(timeline_data)} moments")
                emit_progress(self.project_id, "ANALYZE", "Timeline extracted", subpercent=50)
                
                # Step 3: Content scoring with category calibration
                logger.info(f"Executing Step 3: Content scoring (Category: {category})")
                tracker.set_step(3, "Scoring Clips")
                tracker.log("Scoring viral potential & creative delivery...")
                scored_clips = run_step3_scoring(
                    metadata_dir / "step2_timeline.json",
                    metadata_dir=metadata_dir,
                    category=category,
                    tracker=tracker
                )
                tracker.log(f"Scored {len(scored_clips)} clips")
                emit_progress(self.project_id, "ANALYZE", "Content analysis complete", subpercent=100)
            else:
                logger.warning("No outlines, skipping timeline and scoring")
                timeline_file = metadata_dir / "step2_timeline.json"
                scored_file = metadata_dir / "step3_high_score_clips.json"
                with open(timeline_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                with open(scored_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                timeline_data = []
                scored_clips = []
                emit_progress(self.project_id, "ANALYZE", "Content analysis complete", subpercent=100)
            
            # Stage 4: Highlight & Title Generation
            emit_progress(self.project_id, "HIGHLIGHT", "Locating highlights & generating titles...")
            tracker.set_step(4, "Generating Titles")
            tracker.log("Generating titles and hooks...")
            
            # Step 4: Title generation
            logger.info("Executing Step 4: Title generation")
            if outlines:
                titled_clips = run_step4_title(
                    metadata_dir / "step3_high_score_clips.json",
                    metadata_dir=metadata_dir,
                    category=category
                )
                tracker.log(f"Generated titles for {len(titled_clips)} clips")
                emit_progress(self.project_id, "HIGHLIGHT", "Titles generated", subpercent=40)
                
                # Step 5: Topic clustering
                logger.info("Executing Step 5: Topic clustering")
                tracker.set_step(5, "Selecting Best Clips")
                tracker.log("Clustering highlights into thematic collections...")
                collections = run_step5_clustering(
                    metadata_dir / "step4_titles.json",
                    metadata_dir=str(metadata_dir)
                )
                tracker.log(f"Selected {len(collections)} collections")
                emit_progress(self.project_id, "HIGHLIGHT", "Highlight selection complete", subpercent=100)
            else:
                logger.warning(
                    f"Project {self.project_id}: Step 1 outline extraction returned empty or subtitles unavailable. "
                    "Activating structured fallback segmentation with distinct multi-segment highlights."
                )
                emit_progress(
                    self.project_id,
                    "HIGHLIGHT",
                    "Notice: Outline extraction empty; generating fallback highlights from video...",
                    subpercent=10
                )
                from backend.utils.video_processor import VideoProcessor
                vp = VideoProcessor(clips_dir=str(clips_output_dir), collections_dir=str(collections_output_dir))
                vinfo = vp.get_video_info(input_video_path)
                try:
                    dur_sec = float(vinfo.get("format", {}).get("duration", 60.0))
                except Exception:
                    dur_sec = 60.0
                
                def _format_srt_timestamp(sec: float) -> str:
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s = int(sec % 60)
                    ms = int((sec - int(sec)) * 1000)
                    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                
                proj_name = "Viral Highlight"
                category = "general"
                try:
                    from backend.core.database import SessionLocal
                    from backend.services.project_service import ProjectService
                    with SessionLocal() as db_session:
                        ps = ProjectService(db_session)
                        proj = ps.get(self.project_id)
                        if proj and proj.name:
                            proj_name = proj.name
                        if proj and (proj.processing_config or proj.settings):
                            cfg = proj.processing_config or proj.settings or {}
                            category = cfg.get("video_category", "general")
                except Exception as e:
                    logger.warning(f"Failed to get project info: {e}")
                
                from backend.utils.hook_generator import ViralHookGenerator
                transcript_content = ""
                if srt_path and srt_path.exists():
                    transcript_content = srt_path.read_text(encoding="utf-8", errors="ignore")
                
                hook_data = ViralHookGenerator.generate_hook_from_transcript(
                    transcript_text=transcript_content,
                    video_title=proj_name,
                    category=category
                )
                base_hook = hook_data.get("hook_headline", proj_name)
                base_title = hook_data.get("clip_title", proj_name)

                # Segment planning:
                from backend.core.duration_config import duration_config
                cat_min, cat_max = duration_config.get_duration_range(category)
                fallback_segments = []
                if dur_sec <= cat_min:
                    fallback_segments.append((0.0, dur_sec))
                else:
                    segment_length = min(cat_max, max(cat_min, dur_sec / 3.0))
                    # Pick 3 spaced offsets: 10% (avoid cold intro), 45% (core content), 75% (climax)
                    p1_start = max(0.0, dur_sec * 0.10)
                    p2_start = max(p1_start + segment_length + 5.0, dur_sec * 0.45)
                    p3_start = max(p2_start + segment_length + 5.0, dur_sec * 0.75)

                    for seg_start in [p1_start, p2_start, p3_start]:
                        if seg_start + 15.0 < dur_sec:
                            seg_end = min(dur_sec, seg_start + segment_length)
                            fallback_segments.append((seg_start, seg_end))

                def _slice_srt_text(srt_text: str, start_sec: float, end_sec: float) -> str:
                    if not srt_text:
                        return ""
                    matched = []
                    in_window = False
                    for line in srt_text.splitlines():
                        line_clean = line.strip()
                        if "-->" in line_clean:
                            parts = line_clean.split("-->")
                            if len(parts) == 2:
                                try:
                                    s_part = parts[0].strip().replace(",", ".")
                                    s_tokens = s_part.split(":")
                                    if len(s_tokens) == 3:
                                        sec = float(s_tokens[0]) * 3600 + float(s_tokens[1]) * 60 + float(s_tokens[2])
                                    elif len(s_tokens) == 2:
                                        sec = float(s_tokens[0]) * 60 + float(s_tokens[1])
                                    else:
                                        sec = float(s_part)
                                    in_window = (start_sec - 1.0 <= sec <= end_sec + 1.0)
                                except Exception:
                                    in_window = False
                        elif in_window and line_clean and not line_clean.isdigit():
                            matched.append(line_clean)
                    return " ".join(matched)

                titled_clips = []
                for idx, (seg_start, seg_end) in enumerate(fallback_segments, 1):
                    seg_slice = _slice_srt_text(transcript_content, seg_start, seg_end)
                    seg_title = f"{base_title} (Part {idx})" if len(fallback_segments) > 1 else base_title
                    seg_hook = f"{base_hook} #{idx}" if len(fallback_segments) > 1 else base_hook

                    if seg_slice and len(seg_slice) > 20:
                        try:
                            hook_info = ViralHookGenerator.generate_hook_from_transcript(
                                transcript_text=seg_slice,
                                video_title=f"{proj_name} Part {idx}",
                                category=category,
                                recommend_reason=f"Highlight moment {idx} in {proj_name}"
                            )
                            if hook_info.get("hook_headline"):
                                seg_hook = hook_info["hook_headline"]
                            if hook_info.get("clip_title"):
                                seg_title = hook_info["clip_title"]
                        except Exception as e_sh:
                            logger.debug(f"Per-segment hook generation bypassed for segment {idx}: {e_sh}")

                    clip_dict = {
                        "id": str(idx),
                        "title": seg_title,
                        "generated_title": seg_title,
                        "hook_title": seg_hook,
                        "hook_text": seg_hook,
                        "category": category,
                        "start_time": _format_srt_timestamp(seg_start),
                        "end_time": _format_srt_timestamp(seg_end),
                        "final_score": round(0.85 - (0.05 * (idx - 1)), 2),
                        "recommend_reason": f"Fallback highlight segment {idx} in {proj_name}",
                        "outline": seg_title,
                        "content": [f"Segment spanning {_format_srt_timestamp(seg_start)} to {_format_srt_timestamp(seg_end)}."],
                        "is_fallback": True,
                        "fallback_reason": "step1_outline_empty",
                        "tags": ["fallback", "auto_segmented", category]
                    }
                    try:
                        from backend.utils.social_caption_generator import SocialCaptionGenerator
                        sc_gen = SocialCaptionGenerator()
                        clip_sc = sc_gen._generate_fallback_caption(
                            clip_dict,
                            global_context={
                                "video_title": base_title,
                                "video_category": category,
                                "project_name": proj_name,
                            },
                            clip_transcript=seg_slice
                        )
                        clip_dict["social_copy"] = clip_sc
                        clip_dict["post_caption"] = clip_sc.get("post_caption")
                        clip_dict["hashtags"] = clip_sc.get("hashtags", [])
                    except Exception as e_sc:
                        logger.debug(f"Fallback social copy generation skipped for segment {idx}: {e_sc}")

                    titled_clips.append(clip_dict)

                # Write pipeline intermediate files so metadata is consistent across all steps
                with open(metadata_dir / "step2_timeline.json", 'w', encoding='utf-8') as f:
                    json.dump(titled_clips, f, ensure_ascii=False, indent=2)
                with open(metadata_dir / "step3_high_score_clips.json", 'w', encoding='utf-8') as f:
                    json.dump(titled_clips, f, ensure_ascii=False, indent=2)
                with open(metadata_dir / "step4_titles.json", 'w', encoding='utf-8') as f:
                    json.dump(titled_clips, f, ensure_ascii=False, indent=2)

                collections = [{
                    "id": "1",
                    "collection_title": base_title,
                    "collection_summary": "Auto-segmented highlight collection (generated from fallback mode).",
                    "clip_ids": [clip["id"] for clip in titled_clips]
                }]
                with open(metadata_dir / "step5_collections.json", 'w', encoding='utf-8') as f:
                    json.dump(collections, f, ensure_ascii=False, indent=2)

                emit_progress(self.project_id, "HIGHLIGHT", "Highlight selection complete (fallback mode)", subpercent=100)

            # Part 1: Layer 1 Sentence Boundary Extension (eliminate dialogue cut mid-sentence)
            if srt_path and srt_path.exists():
                try:
                    from backend.utils.silence_detector import extend_to_sentence_boundary
                    from backend.utils.video_processor import VideoProcessor
                    for c in titled_clips:
                        raw_end = VideoProcessor.convert_ffmpeg_time_to_seconds(
                            VideoProcessor.convert_srt_time_to_ffmpeg_time(c.get('end_time', '00:00:00'))
                        )
                        adj_end = extend_to_sentence_boundary(raw_end, srt_words=srt_path, tolerance_sec=12.0)
                        if adj_end > raw_end:
                            logger.info(f"Extended clip {c.get('id')} end boundary from {raw_end:.2f}s to {adj_end:.2f}s for sentence completion.")
                            c['end_time'] = VideoProcessor.convert_seconds_to_ffmpeg_time(adj_end)
                except Exception as ext_err:
                    logger.debug(f"Sentence boundary extension skipped in pipeline adapter: {ext_err}")

            # Part 2: Smart Duration Advisory (no forced cuts)
            try:
                from backend.core.platform_advisor import get_platform_advisory
                from backend.utils.video_processor import VideoProcessor
                for c in titled_clips:
                    s_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(VideoProcessor.convert_srt_time_to_ffmpeg_time(c.get('start_time', '00:00:00')))
                    e_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(VideoProcessor.convert_srt_time_to_ffmpeg_time(c.get('end_time', '00:00:00')))
                    clip_dur = max(1.0, e_sec - s_sec)
                    c['platform_advisory'] = get_platform_advisory(clip_dur)
            except Exception as adv_err:
                logger.debug(f"Platform advisory calculation skipped in pipeline adapter: {adv_err}")

            # Update step4_titles.json with final sentence-completed boundaries & platform advisories
            try:
                with open(metadata_dir / "step4_titles.json", 'w', encoding='utf-8') as f:
                    json.dump(titled_clips, f, ensure_ascii=False, indent=2)
            except Exception as w_err:
                logger.debug(f"Failed to update step4_titles.json: {w_err}")

            # Regression Canary: check clip duration distribution of selected clips
            check_duration_regression_canary(titled_clips, stage_name=f"Project {self.project_id} Final Highlights")

            # Stage 5: Video Export
            emit_progress(self.project_id, "EXPORT", "Rendering vertical 9:16 clips with captions...")
            
            caption_style = "hormozi_yellow"
            show_hook_banner = True
            aspect_ratio = "9:16_blur"
            watermark_path = None
            watermark_position = "bottom_right"
            watermark_scale = 15.0
            watermark_opacity = 0.85
            watermark_margin = 24
            watermark_text = None
            watermark_text_opacity = 0.50
            watermark_text_position = "lower_center"
            from backend.core import shared_config
            cta_style = getattr(shared_config, 'DEFAULT_CTA_STYLE', 'follow_tap')
            cta_platform = getattr(shared_config, 'DEFAULT_CTA_PLATFORM', 'tiktok')
            cta_handle = getattr(shared_config, 'DEFAULT_CTA_HANDLE', '')
            cta_position = getattr(shared_config, 'DEFAULT_CTA_POSITION', 'lower_center')
            try:
                from backend.core.database import SessionLocal
                from backend.services.project_service import ProjectService
                from backend.services.watermark_service import watermark_service
                with SessionLocal() as db_session:
                    ps = ProjectService(db_session)
                    proj = ps.get(self.project_id)
                    if proj:
                        cfg = proj.processing_config or proj.settings or {}
                        caption_style = cfg.get("caption_style", "hormozi_yellow")
                        show_hook_banner = cfg.get("show_hook_banner", True)
                        aspect_ratio = cfg.get("aspect_ratio", "9:16_blur")
                        if cfg.get("watermark_text"):
                            watermark_text = cfg["watermark_text"]
                        if cfg.get("watermark_text_opacity") is not None:
                            try:
                                watermark_text_opacity = float(cfg["watermark_text_opacity"])
                            except (ValueError, TypeError):
                                watermark_text_opacity = 0.50
                        if cfg.get("watermark_text_position"):
                            watermark_text_position = cfg["watermark_text_position"]
                        if cfg.get("cta_style"):
                            cta_style = cfg["cta_style"]
                        if cfg.get("cta_platform"):
                            cta_platform = cfg["cta_platform"]
                        if cfg.get("cta_handle"):
                            cta_handle = cfg["cta_handle"]
                        if cfg.get("cta_position"):
                            cta_position = cfg["cta_position"]
                        wm_preset_id = cfg.get("watermark_preset_id")
                        if not wm_preset_id or wm_preset_id == "none":
                            default_presets = [p for p in watermark_service.get_all_presets() if p.get("is_default")]
                            if default_presets:
                                wm_preset_id = default_presets[0]["id"]
                        if wm_preset_id and wm_preset_id != "none":
                            wm_preset = watermark_service.get_preset(wm_preset_id)
                            if wm_preset and wm_preset.get("logo_filename"):
                                logo_file = watermark_service.get_logo_path(wm_preset["logo_filename"])
                                if logo_file and logo_file.exists():
                                    watermark_path = logo_file
                                    watermark_position = wm_preset.get("position", "bottom_right")
                                    watermark_scale = float(wm_preset.get("scale_percent", 15.0))
                                    watermark_opacity = float(wm_preset.get("opacity", 0.85))
                                    watermark_margin = int(wm_preset.get("margin", 24))
            except Exception as e:
                logger.warning(f"Failed to get watermark/caption config: {e}")

            # Ensure clips in step4_titles.json have CTA metadata
            try:
                titles_file = metadata_dir / "step4_titles.json"
                if titles_file.exists():
                    with open(titles_file, 'r', encoding='utf-8') as f:
                        cur_titles = json.load(f)
                    changed = False
                    for c in cur_titles:
                        if not c.get('cta_style'):
                            c['cta_style'] = cta_style
                            changed = True
                        if not c.get('cta_platform'):
                            c['cta_platform'] = cta_platform
                            changed = True
                        if not c.get('cta_handle') and cta_handle:
                            c['cta_handle'] = cta_handle
                            changed = True
                        if not c.get('cta_position') and cta_position:
                            c['cta_position'] = cta_position
                            changed = True
                    if changed:
                        with open(titles_file, 'w', encoding='utf-8') as f:
                            json.dump(cur_titles, f, ensure_ascii=False, indent=2)
            except Exception as cta_err:
                logger.debug(f"CTA config population skipped: {cta_err}")

            # Step 6: Video cutting and subtitle burning
            logger.info(f"Executing Step 6: Video extraction (Style: {caption_style}, Ratio: {aspect_ratio}, Banner: {show_hook_banner}, Watermark: {bool(watermark_path)}, TextWM: {bool(watermark_text)})")
            tracker.set_step(6, "Cutting Video Clips")
            tracker.log(f"Cutting and formatting vertical video clips (Style: {caption_style})...")
            video_result = run_step6_video(
                metadata_dir / "step4_titles.json",
                metadata_dir / "step5_collections.json",
                input_video_path,
                output_dir=output_dir,
                clips_dir=str(clips_output_dir),
                collections_dir=str(collections_output_dir),
                metadata_dir=str(metadata_dir),
                srt_path=srt_path,
                caption_style=caption_style,
                show_hook_banner=show_hook_banner,
                watermark_path=watermark_path,
                watermark_position=watermark_position,
                watermark_scale=watermark_scale,
                watermark_opacity=watermark_opacity,
                watermark_margin=watermark_margin,
                watermark_text=watermark_text,
                watermark_text_opacity=watermark_text_opacity,
                watermark_text_position=watermark_text_position,
                aspect_ratio=aspect_ratio,
                category=category,
                tracker=tracker
            )
            clips_generated = video_result.get('clips_generated', 0)
            tracker.log(f"Exported {clips_generated} clips")
            if len(titled_clips) > 0 and clips_generated == 0:
                logger.error(f"Project {self.project_id}: Step 6 failed to generate any clip videos ({len(titled_clips)} expected).")
            emit_progress(self.project_id, "EXPORT", "Video export complete", subpercent=100)
            
            # Stage 6: Done
            emit_progress(self.project_id, "DONE", "Processing complete!")
            tracker.complete()
            
            # Automatically synchronizing data to database
            try:
                from backend.services.data_sync_service import DataSyncService
                from backend.core.database import SessionLocal
                
                db = SessionLocal()
                try:
                    sync_service = DataSyncService(db)
                    sync_result = sync_service.sync_project_from_filesystem(self.project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"Project {self.project_id} Data synchronization successful: {sync_result}")
                    else:
                        logger.error(f"Project {self.project_id} Data synchronization failed: {sync_result}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Data synchronization failed: {e}")
            
            # Phase 9.1: Automated post-pipeline cleanup of intermediate chunk files
            try:
                for chunk_dir_name in ["step1_srt_chunks", "step2_timeline_chunks", "step2_llm_raw_output"]:
                    chunk_dir = metadata_dir / chunk_dir_name
                    if chunk_dir.exists() and chunk_dir.is_dir():
                        import shutil
                        shutil.rmtree(chunk_dir, ignore_errors=True)
                logger.info(f"Intermediate chunk directories cleaned for project {self.project_id}")
            except Exception as clean_err:
                logger.debug(f"Post-pipeline cleanup error: {clean_err}")

            logger.info(f"ProjectProcessing complete: {self.project_id}")
            return {
                "status": "succeeded",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "result": {
                    "outlines": outlines,
                    "timeline": timeline_data,
                    "scored_clips": scored_clips,
                    "titled_clips": titled_clips,
                    "collections": collections,
                    "video_result": video_result
                }
            }
            
        except Exception as e:
            error_msg = f"PipelineProcessing failed: {str(e)}"
            logger.error(error_msg)
            tracker.fail(error_msg)
            
            # Sending failure status
            emit_progress(self.project_id, "DONE", f"Processing failed: {error_msg}")
            
            return {
                "status": "failed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "error": error_msg
            }


def create_simple_pipeline_adapter(project_id: str, task_id: str) -> SimplePipelineAdapter:
    """Creating simplified pipeline adapter instance"""
    return SimplePipelineAdapter(project_id, task_id)
