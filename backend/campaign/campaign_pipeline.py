"""
Campaign Pipeline Orchestrator — C1 through C7.
Completely separate from simple_pipeline_adapter.py.
Reuses: speech_recognizer.py, video_processor.py utility functions.
"""
import os
import json
import logging
import uuid
import requests
import re
import shutil
from pathlib import Path
from typing import Optional

from .brief_parser    import parse_brief
from .moment_finder   import find_moments_in_transcript, auto_discover_moments
from .logo_overlay    import apply_logo_overlay, download_logo
from .caption_matcher import match_captions_to_moment
from .package_builder import build_compliance_checklist, build_platform_post_guide
from .video_formatter import format_to_vertical, get_video_dimensions
from .video_editor    import auto_edit_full_video, get_video_duration
from .copy_generator  import generate_clip_copy_and_hook

from ..utils.speech_recognizer import transcribe_video_to_srt
from ..utils.video_processor   import build_ffmpeg_cut_command, detect_hw_accel
from ..utils.caption_styles    import ViralCaptionGenerator
from ..utils.cta_overlay       import apply_cta_overlay, get_platform_cta, generate_multiplatform_cta_overlays
from ..schemas.campaign        import CampaignSchema
from ..core.database           import SessionLocal

logger = logging.getLogger(__name__)

CAMPAIGN_DATA_DIR = Path("data/campaigns")


def run_campaign_pipeline(campaign_id: str, schema_dict: dict, db_session=None) -> None:
    """
    Full campaign pipeline: download → transcribe → find moments → cut → logo → package.
    Designed to run in a background thread/task (called from API endpoint).
    
    Updates campaign status in DB throughout.
    """
    from ..models.campaign import Campaign, CampaignClip
    
    schema       = CampaignSchema(**schema_dict)
    campaign_dir = CAMPAIGN_DATA_DIR / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Use dedicated session if running in background thread
    owns_session = False
    if db_session is None:
        db_session = SessionLocal()
        owns_session = True
    
    def update_status(status: str, msg: str = ""):
        session = SessionLocal()
        try:
            camp = session.query(Campaign).filter_by(id=campaign_id).first()
            if camp:
                camp.status = status
                try:
                    s_data = json.loads(camp.schema_json) if camp.schema_json else {}
                except Exception:
                    s_data = {}
                s_data["status_message"] = msg or status.replace("_", " ").title()
                camp.schema_json = json.dumps(s_data, ensure_ascii=False)
                from datetime import datetime
                camp.updated_at = datetime.utcnow()
                session.commit()
            logger.info(f"Campaign {campaign_id} status: {status} ({msg})")
        except Exception as err:
            session.rollback()
            logger.error(f"Failed to update campaign status: {err}")
        finally:
            session.close()
    
    try:
        # === C1: Download/Check source video ===
        dest_video = campaign_dir / "source.mp4"
        if dest_video.exists() and dest_video.stat().st_size > 0:
            source_video = dest_video
            update_status("transcribing", "Source video verified. Starting Whisper transcription...")
        else:
            update_status("downloading", "Downloading source video...")
            source_video = _acquire_source_video(
                schema.source_video_url, campaign_dir
            )
            
        if not source_video or not source_video.exists() or source_video.stat().st_size == 0:
            update_status("failed", "Source video not found or download failed. Please upload video directly.")
            logger.error(f"Campaign {campaign_id}: Could not acquire source video")
            return
        
        # === C2: Transcribe ===
        update_status("transcribing", "Transcribing video audio with Whisper...")
        srt_path = campaign_dir / "transcript.srt"
        segments = _transcribe(source_video, srt_path)
        if not segments:
            update_status("failed", "Whisper transcription failed. Ensure audio is clear and audible.")
            logger.error(f"Campaign {campaign_id}: Transcription failed")
            return

        # Verify SRT file was actually written or search for it
        if srt_path.exists() and srt_path.stat().st_size > 0:
            logger.info(f"SRT confirmed at {srt_path} ({srt_path.stat().st_size} bytes)")
        else:
            srt_candidates = list(campaign_dir.rglob("*.srt"))
            if srt_candidates:
                srt_path = srt_candidates[0]
                logger.info(f"SRT found at non-standard path: {srt_path}")
            else:
                logger.warning(f"No SRT file found anywhere in {campaign_dir} — synthesizing from segments")
                try:
                    from ..utils.speech_recognizer import SpeechRecognizer
                    srt_content = SpeechRecognizer._segments_to_srt(segments)
                    with open(srt_path, "w", encoding="utf-8") as f:
                        f.write(srt_content)
                    logger.info(f"Synthesized and saved SRT to {srt_path} ({len(srt_content)} chars)")
                except Exception as write_err:
                    logger.error(f"Failed to generate SRT from segments: {write_err}")
        
        # Check local logo file FIRST (uploaded via Studio), then remote logo_url
        local_logo = campaign_dir / "assets" / "logo.png"
        logo_path = None
        if local_logo.exists() and local_logo.stat().st_size > 0:
            logo_path = local_logo
        elif schema.restrictions.logo_required and schema.logo_url:
            logo_path = download_logo(schema.logo_url, campaign_dir / "assets")

        edit_mode = _get_edit_mode(schema)
        logger.info(f"Campaign {campaign_id}: Edit mode is '{edit_mode}'")

        if edit_mode == "full_video_edit":
            # ============================================================
            # FULL VIDEO EDIT BRANCH
            # Keep entire video, remove dead air, add outro if configured
            # ============================================================
            update_status("editing", "Editing full video — removing dead air...")

            restrictions_dict = _get_restrictions_dict(schema)
            clip_id    = str(uuid.uuid4())
            clip_dir   = campaign_dir / "clips" / clip_id
            clip_dir.mkdir(parents=True, exist_ok=True)

            campaign_record = db_session.query(Campaign).filter_by(id=campaign_id).first()
            campaign_display_name = (
                campaign_record.name if campaign_record and campaign_record.name
                else (getattr(schema, "campaign_name", None) or "Full Edit")
            )

            clip_data = auto_edit_full_video(
                source_path=source_video,
                clip_dir=clip_dir,
                restrictions=restrictions_dict,
                campaign_name=campaign_display_name
            )

            if not clip_data:
                update_status("failed", "Full video edit failed — check logs")
                return

            raw_clip_path = Path(clip_data['video_file'])
            start_sec     = clip_data['start_sec']
            end_sec       = clip_data['end_sec']
            moment_name   = clip_data['moment_name']

            # === C4.5: Format to 9:16 (SAME as moment_extraction) ===
            output_format = _get_output_format(schema)
            formatted_clip_path = clip_dir / "clip_vertical.mp4"
            if output_format != "original":
                update_status("editing", f"Formatting full video to 9:16 ({output_format})...")
                format_ok = format_to_vertical(raw_clip_path, formatted_clip_path, mode=output_format)
                logo_input_path = formatted_clip_path if (format_ok and formatted_clip_path.exists()) else raw_clip_path
            else:
                logo_input_path = raw_clip_path

            # === C5: Logo overlay (SAME as moment_extraction) ===
            logo_clip_path = clip_dir / "clip_with_logo.mp4"
            logo_applied   = False
            if logo_path and logo_path.exists() and logo_input_path.exists():
                update_status("editing", "Applying logo watermark...")
                logo_applied = apply_logo_overlay(
                    video_path=logo_input_path,
                    logo_path=logo_path,
                    output_path=logo_clip_path,
                    position=_get_logo_position(schema),
                    scale_percent=_get_logo_scale(schema)
                )

            # Generate Text Hook and Search-Optimized Platform Post Guide
            full_transcript = " ".join(s.get('text', '') for s in segments) if segments else ""
            tags_dict = schema.platform_tags.model_dump() if hasattr(schema.platform_tags, "model_dump") else schema.platform_tags.dict()
            copy_res = generate_clip_copy_and_hook(
                moment_name=moment_name,
                transcript_text=full_transcript,
                brand_name=schema.brand_name,
                description="Full video edit",
                platform_tags=tags_dict,
                caption_options=schema.caption_options
            )
            hook_text = copy_res.get("hook_text", "")
            post_guide = {
                "tiktok": copy_res.get("tiktok", {}),
                "instagram": copy_res.get("instagram", {}),
                "youtube_shorts": copy_res.get("youtube_shorts", {}),
                "facebook": copy_res.get("facebook", {})
            }

            # === C5.5: Caption & Hook burning ===
            subtitle_mode  = _get_subtitle_mode(schema)
            caption_style  = _get_caption_style(schema)
            show_hook_banner = _get_show_hook_banner(schema)
            caption_input  = logo_clip_path if (logo_applied and logo_clip_path.exists()) else logo_input_path
            caption_output = clip_dir / "clip_captioned.mp4"
            ass_path       = clip_dir / "captions.ass"
            final_clip_path = caption_input

            if caption_input.exists():
                actual_w, actual_h = get_video_dimensions(caption_input)
                ass_ok = False
                if subtitle_mode == "styled_burned" and srt_path.exists():
                    update_status("editing", f"Generating styled captions ({caption_style}) with hook banner...")
                    ass_ok = ViralCaptionGenerator.generate_clip_ass(
                        source_srt_path=srt_path,
                        clip_start=start_sec,
                        clip_end=min(end_sec, get_video_duration(source_video)),
                        output_ass_path=ass_path,
                        style_key=caption_style,
                        hook_title=hook_text,
                        show_hook_banner=show_hook_banner,
                        video_width=actual_w,
                        video_height=actual_h
                    )
                elif show_hook_banner and hook_text:
                    update_status("editing", "Generating opening text hook banner...")
                    ass_ok = ViralCaptionGenerator.generate_clip_ass(
                        source_srt_path=None,
                        clip_start=start_sec,
                        clip_end=min(end_sec, get_video_duration(source_video)),
                        output_ass_path=ass_path,
                        style_key=caption_style,
                        hook_title=hook_text,
                        show_hook_banner=True,
                        video_width=actual_w,
                        video_height=actual_h,
                        words_data=[]
                    )

                if ass_ok and ass_path.exists():
                    update_status("editing", "Burning styled captions into video...")
                    burn_ok = _burn_ass_captions(caption_input, ass_path, caption_output)
                    if burn_ok and caption_output.exists():
                        final_clip_path = caption_output

                if show_hook_banner and hook_text and final_clip_path.exists():
                    update_status("editing", "Applying full-color emoji hook banner...")
                    try:
                        from ..utils.hook_overlay import apply_hook_overlay
                        hook_output = clip_dir / "clip_with_hook.mp4"
                        if apply_hook_overlay(final_clip_path, hook_output, hook_text):
                            final_clip_path = hook_output
                    except Exception as h_err:
                        logger.warning(f"Failed to apply hook overlay in campaign pipeline: {h_err}")

            # Clean SRT for full edit
            clip_srt_path = clip_dir / "captions.srt"
            if srt_path.exists() and not clip_srt_path.exists():
                shutil.copy2(str(srt_path), str(clip_srt_path))

            # === C6: CTA Overlay ===
            cta = _get_cta_settings(schema)
            cta_style = cta['cta_style']
            cta_output = None
            cta_platform = None
            cta_platforms_map = {}

            if cta_style != 'none':
                cta_input = final_clip_path
                cta_output = clip_dir / "clip_cta.mp4"

                # Auto-detect platform from campaign platform_tags if cta_platform = 'auto'
                cta_platform = cta['cta_platform']
                if cta_platform == 'auto':
                    try:
                        tags = schema.platform_tags.model_dump() if hasattr(schema.platform_tags, "model_dump") else \
                               schema.platform_tags if isinstance(schema.platform_tags, dict) else \
                               schema.get('platform_tags', {}) if isinstance(schema, dict) else {}
                        platform_keys = [k for k, v in tags.items() if v] if isinstance(tags, dict) else []
                        cta_platform = platform_keys[0] if platform_keys else 'tiktok'
                    except Exception:
                        cta_platform = 'tiktok'

                update_status("editing", "Generating multi-platform CTA overlays (TikTok, Instagram, YouTube Shorts, Facebook)...")
                cta_w, cta_h = get_video_dimensions(cta_input)

                cta_platforms_map = generate_multiplatform_cta_overlays(
                    input_path=cta_input,
                    output_dir=clip_dir,
                    stem_prefix="clip",
                    handle=cta['cta_handle'],
                    base_style=cta_style,
                    position=cta['cta_position'],
                    start_time=cta['cta_start_offset'],
                    video_width=cta_w,
                    video_height=cta_h,
                    primary_platform=cta_platform
                )

                if cta_platforms_map:
                    primary_file = cta_platforms_map.get(cta_platform) or str(cta_output)
                    if os.path.exists(primary_file):
                        final_clip_path = Path(primary_file)
                        logger.info(f"Multi-platform CTA overlays generated for full edit: {list(cta_platforms_map.keys())}")
                else:
                    logger.warning("CTA overlays failed, using clip without CTA")

            # === Write CampaignClip record ===
            clip_data.update({
                'video_file':           str(final_clip_path),
                'logo_video_file':      str(logo_clip_path) if logo_clip_path.exists() else None,
                'captioned_video_file': str(caption_output) if caption_output.exists() else None,
                'cta_video_file':       str(cta_output) if cta_output and cta_output.exists() else (str(final_clip_path) if cta_platforms_map else None),
                'cta_platforms':        cta_platforms_map,
                'platform_videos':      cta_platforms_map,
                'cta_style':            cta_style,
                'cta_platform':         cta_platform if cta_style != 'none' else None,
                'vertical_video_file':  str(formatted_clip_path) if formatted_clip_path.exists() else None,
                'srt_file':             str(clip_srt_path) if clip_srt_path.exists() else None,
                'subtitle_mode':        subtitle_mode,
                'output_format':        output_format,
                'duration_seconds':     max(0.0, end_sec - start_sec),
                'confidence':           'high',
                'compliance_checklist': [],
                'caption_suggestions':  [],
                'hook_text':            hook_text,
                'platform_post_guide':  post_guide,
                'edit_mode':            'full_video_edit',
            })

            clip_record = CampaignClip(
                id=clip_id,
                campaign_id=campaign_id,
                moment_name=moment_name,
                status="ready",
                clip_data_json=json.dumps(clip_data, ensure_ascii=False)
            )
            save_session = SessionLocal()
            try:
                save_session.add(clip_record)
                save_session.commit()
            except Exception as save_err:
                save_session.rollback()
                logger.error(f"Failed to save CampaignClip for full edit: {save_err}")
                raise save_err
            finally:
                save_session.close()

            update_status("done", "Full edit complete — 1 clip ready")
            logger.info(f"Campaign {campaign_id} full edit completed: clip {clip_id}")
            return

        # ============================================================
        # MOMENT EXTRACTION BRANCH (existing code)
        # ============================================================
        # === C3: Find moments ===
        update_status("finding_moments", "Matching mandated moments in transcript...")
        priority_dicts = [
            m.model_dump() if hasattr(m, "model_dump") else m.dict()
            for m in schema.priority_moments
        ]
        found_moments = find_moments_in_transcript(
            segments,
            priority_dicts,
            schema.clip_duration.min_seconds,
            schema.clip_duration.max_seconds
        )
        
        # Probe total video duration
        import subprocess
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(source_video)],
            capture_output=True, text=True
        )
        total_dur = float(probe.stdout.strip() or "60")

        max_clips = getattr(schema, "max_clips", None) or (schema_dict.get("max_clips") if isinstance(schema_dict, dict) else None)
        if not found_moments:
            moments_cache_file = campaign_dir / "discovered_moments.json"
            if moments_cache_file.exists():
                try:
                    with open(moments_cache_file, "r") as f:
                        found_moments = json.load(f)
                    logger.info(f"Loaded {len(found_moments)} discovered moments from cache: {moments_cache_file}")
                except Exception as e:
                    logger.warning(f"Failed to read moments cache: {e}")

            if not found_moments:
                logger.warning(f"Campaign {campaign_id}: No priority moments matched — auto-discovering moments across video footage (duration: {total_dur:.1f}s)")
                update_status("finding_moments", f"Auto-discovering best moments across {total_dur:.0f}s footage...")
                found_moments = auto_discover_moments(
                    segments=segments,
                    total_duration=total_dur,
                    duration_min=schema.clip_duration.min_seconds,
                    duration_max=schema.clip_duration.max_seconds,
                    max_clips=max_clips
                )
                if found_moments:
                    try:
                        with open(moments_cache_file, "w") as f:
                            json.dump(found_moments, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed to write moments cache: {e}")

        # Apply clip count limit (e.g. if creator only needs 1 or 2 clips)
        if max_clips and isinstance(max_clips, int) and max_clips > 0:
            found_moments = found_moments[:max_clips]
        
        # === C4+C5+C6+C7: Cut + Logo + Caption + Package per moment ===
        total_clips = len(found_moments)
        update_status("cutting", f"Preparing to process {total_clips} clip(s)" + (" with watermark..." if logo_path else "..."))
        hw_device = detect_hw_accel()
        
        # Clear previous clips if re-running
        try:
            db_session.query(CampaignClip).filter_by(campaign_id=campaign_id).delete()
            db_session.commit()
        except Exception as e:
            logger.debug(f"Could not clear previous clips: {e}")
        
        for idx, moment in enumerate(found_moments):
            clip_name = moment.get('moment_name', f'Clip {idx + 1}')
            clip_progress_prefix = f"[{idx + 1}/{total_clips}] '{clip_name}'"
            update_status("cutting", f"{clip_progress_prefix}: Cutting video segment...")

            clip_id   = str(uuid.uuid4())
            clip_dir  = campaign_dir / "clips" / clip_id
            clip_dir.mkdir(parents=True, exist_ok=True)
            
            raw_clip_path  = clip_dir / "clip_raw.mp4"
            logo_clip_path = clip_dir / "clip_with_logo.mp4"
            
            # C4: Cut clip
            start_sec = moment['start_sec']
            end_sec   = moment['end_sec']
            cut_cmd = build_ffmpeg_cut_command(
                input_path=str(source_video),
                output_path=str(raw_clip_path),
                start_time=start_sec,
                end_time=end_sec,
                hw_device=hw_device
            )
            if len(cut_cmd) > 1:
                cut_cmd = cut_cmd[:-1] + ["-pix_fmt", "yuv420p", "-movflags", "+faststart", cut_cmd[-1]]
            import subprocess
            subprocess.run(cut_cmd, capture_output=True, timeout=120)

            # === C4.5: Format to 9:16 vertical ===
            output_format = "blur_pad"
            if hasattr(schema.restrictions, 'output_format'):
                val = schema.restrictions.output_format
                output_format = val.value if hasattr(val, 'value') else str(val)
            formatted_clip_path = clip_dir / "clip_vertical.mp4"

            if output_format != "original":
                update_status("cutting", f"{clip_progress_prefix}: Formatting to 9:16 ({output_format})...")
                format_success = format_to_vertical(
                    input_path=raw_clip_path,
                    output_path=formatted_clip_path,
                    mode=output_format,
                    hw_device=hw_device
                )
                if format_success and formatted_clip_path.exists():
                    # Use formatted version as input for logo step
                    logo_input_path = formatted_clip_path
                else:
                    logger.warning(f"Format to 9:16 failed for {moment['moment_name']}, using raw clip")
                    logo_input_path = raw_clip_path
            else:
                logo_input_path = raw_clip_path

            # === C5: Apply logo (use logo_input_path instead of raw_clip_path) ===
            logo_applied = False
            if logo_path and logo_path.exists() and logo_input_path.exists():
                update_status("cutting", f"{clip_progress_prefix}: Applying logo watermark...")
                logo_applied = apply_logo_overlay(
                    video_path=logo_input_path,
                    logo_path=logo_path,
                    output_path=logo_clip_path,
                    position=schema.restrictions.logo_position.value,
                    scale_percent=schema.restrictions.logo_scale_percent
                )

            # Generate Text Hook and Search-Optimized Platform Post Guide
            clip_transcript = " ".join(
                s.get('text', '') for s in segments
                if s.get('start', 0) >= (start_sec - 1.0) and s.get('end', 0) <= (end_sec + 1.0)
            ) or moment.get('matched_text', '')

            tags_dict = schema.platform_tags.model_dump() if hasattr(schema.platform_tags, "model_dump") else schema.platform_tags.dict()
            copy_res = generate_clip_copy_and_hook(
                moment_name=moment['moment_name'],
                transcript_text=clip_transcript,
                brand_name=schema.brand_name,
                description=moment.get('description', ''),
                platform_tags=tags_dict,
                caption_options=schema.caption_options
            )
            hook_text = copy_res.get("hook_text", "")
            post_guide = {
                "tiktok": copy_res.get("tiktok", {}),
                "instagram": copy_res.get("instagram", {}),
                "youtube_shorts": copy_res.get("youtube_shorts", {}),
                "facebook": copy_res.get("facebook", {})
            }

            # === C5.5: Burn captions & Text Hook ===
            subtitle_mode = _get_subtitle_mode(schema)
            caption_style = _get_caption_style(schema)
            show_hook_banner = _get_show_hook_banner(schema)

            # Determine which video to caption (logo version if exists, else formatted/raw)
            caption_input = logo_clip_path if (logo_applied and logo_clip_path.exists()) else logo_input_path
            caption_output = clip_dir / "clip_captioned.mp4"
            ass_path = clip_dir / "captions.ass"
            clip_srt_path = clip_dir / "captions.srt"

            final_clip_path = caption_input  # default: no captions

            logger.info(
                f"Caption step for clip '{clip_name}' — mode={subtitle_mode!r}, "
                f"style={caption_style!r}, srt_exists={srt_path.exists()}, "
                f"input_exists={caption_input.exists()}, show_hook_banner={show_hook_banner}"
            )

            if subtitle_mode == "styled_burned":
                if not srt_path.exists() or srt_path.stat().st_size == 0:
                    logger.error(f"Cannot burn captions: SRT not found or empty at {srt_path}")
                elif not caption_input.exists():
                    logger.error(f"Cannot burn captions: input clip not found at {caption_input}")
                else:
                    actual_w, actual_h = get_video_dimensions(caption_input)
                    logger.info(f"Generating ASS for clip dimensions: {actual_w}x{actual_h}")
                    update_status("cutting", f"{clip_progress_prefix}: Generating styled captions ({caption_style}) with hook banner...")

                    ass_ok = ViralCaptionGenerator.generate_clip_ass(
                        source_srt_path=srt_path,
                        clip_start=start_sec,
                        clip_end=end_sec,
                        output_ass_path=ass_path,
                        style_key=caption_style,
                        hook_title=hook_text,
                        show_hook_banner=show_hook_banner,
                        video_width=actual_w,
                        video_height=actual_h
                    )

                    # Sanity check on ASS content
                    if ass_ok and ass_path.exists():
                        try:
                            with open(ass_path, 'r', encoding='utf-8', errors='ignore') as af:
                                ass_content = af.read()
                            if '[Events]' not in ass_content or 'Dialogue:' not in ass_content:
                                logger.error(f"ASS file appears empty or malformed:\n{ass_content[:500]}")
                                ass_ok = False
                            elif ass_content.count('Dialogue:') < 2:
                                logger.warning(f"ASS has only {ass_content.count('Dialogue:')} dialogue line(s)")
                        except Exception as af_err:
                            logger.warning(f"Error reading ASS file for validation: {af_err}")

                    if not ass_ok or not ass_path.exists():
                        logger.error(f"ASS file generation failed. ass_ok={ass_ok}, exists={ass_path.exists()}")
                        final_clip_path = caption_input
                    else:
                        logger.info(f"ASS generated ({ass_path.stat().st_size} bytes) — burning into video")
                        update_status("cutting", f"{clip_progress_prefix}: Burning styled captions & hook into video...")
                        burn_ok = _burn_ass_captions(caption_input, ass_path, caption_output)

                        if burn_ok and caption_output.exists():
                            final_clip_path = caption_output
                            logger.info(f"Caption burn SUCCESS → final clip: {final_clip_path}")
                        else:
                            logger.error("Caption burn FAILED — serving uncaptioned clip")
                            final_clip_path = caption_input

                if show_hook_banner and hook_text and final_clip_path.exists():
                    update_status("cutting", f"{clip_progress_prefix}: Applying full-color emoji hook banner...")
                    try:
                        from ..utils.hook_overlay import apply_hook_overlay
                        hook_output = clip_dir / "clip_with_hook.mp4"
                        if apply_hook_overlay(final_clip_path, hook_output, hook_text):
                            final_clip_path = hook_output
                    except Exception as h_err:
                        logger.warning(f"Failed to apply hook overlay in fast edit: {h_err}")

            elif show_hook_banner and hook_text and caption_input.exists():
                update_status("cutting", f"{clip_progress_prefix}: Applying opening full-color emoji hook banner...")
                try:
                    from ..utils.hook_overlay import apply_hook_overlay
                    hook_output = clip_dir / "clip_with_hook.mp4"
                    if apply_hook_overlay(caption_input, hook_output, hook_text):
                        final_clip_path = hook_output
                except Exception as h_err:
                    logger.warning(f"Failed to apply standalone hook overlay in fast edit: {h_err}")

            if subtitle_mode == "clean_srt_only" and srt_path.exists():
                update_status("cutting", f"{clip_progress_prefix}: Extracting clean SRT file...")
                try:
                    ViralCaptionGenerator.generate_clip_srt(
                        source_srt_path=srt_path,
                        clip_start=start_sec,
                        clip_end=end_sec,
                        output_srt_path=clip_srt_path
                    )
                    logger.info(f"SRT generated: {clip_srt_path}")
                except Exception as e:
                    logger.error(f"SRT generation failed: {e}")

            # === C6: CTA Overlay ===
            cta = _get_cta_settings(schema)
            cta_style = cta['cta_style']
            cta_output = None
            cta_platform = None
            cta_platforms_map = {}

            if cta_style != 'none':
                cta_input = final_clip_path
                cta_output = clip_dir / "clip_cta.mp4"

                # Auto-detect platform from campaign platform_tags if cta_platform = 'auto'
                cta_platform = cta['cta_platform']
                if cta_platform == 'auto':
                    try:
                        tags = schema.platform_tags.model_dump() if hasattr(schema.platform_tags, "model_dump") else \
                               schema.platform_tags if isinstance(schema.platform_tags, dict) else \
                               schema.get('platform_tags', {}) if isinstance(schema, dict) else {}
                        platform_keys = [k for k, v in tags.items() if v] if isinstance(tags, dict) else []
                        cta_platform = platform_keys[0] if platform_keys else 'tiktok'
                    except Exception:
                        cta_platform = 'tiktok'

                update_status("cutting", f"{clip_progress_prefix}: Generating multi-platform CTA overlays (TikTok, Instagram, YouTube Shorts, Facebook)...")
                cta_w, cta_h = get_video_dimensions(cta_input)

                cta_platforms_map = generate_multiplatform_cta_overlays(
                    input_path=cta_input,
                    output_dir=clip_dir,
                    stem_prefix="clip",
                    handle=cta['cta_handle'],
                    base_style=cta_style,
                    position=cta['cta_position'],
                    start_time=cta['cta_start_offset'],
                    video_width=cta_w,
                    video_height=cta_h,
                    primary_platform=cta_platform
                )

                if cta_platforms_map:
                    primary_file = cta_platforms_map.get(cta_platform) or str(cta_output)
                    if os.path.exists(primary_file):
                        final_clip_path = Path(primary_file)
                        logger.info(f"Multi-platform CTA overlays generated for clip {clip_id}: {list(cta_platforms_map.keys())}")
                else:
                    logger.warning("CTA overlays failed, using clip without CTA")

            # C6: Match captions
            caption_suggestions = match_captions_to_moment(
                moment_name=moment['moment_name'],
                matched_text=moment.get('matched_text', ''),
                caption_options=schema.caption_options
            )
            
            # C7: Build output package
            duration_sec = end_sec - start_sec
            
            compliance = build_compliance_checklist(
                duration_sec=duration_sec,
                duration_min=schema.clip_duration.min_seconds,
                duration_max=schema.clip_duration.max_seconds,
                logo_applied=logo_applied,
                styled_captions_off=(subtitle_mode != "styled_burned" and not schema.restrictions.styled_captions),
                min_days_live=schema.compliance.min_days_live,
                min_engagement_rate=schema.compliance.min_engagement_rate,
                ftc_required=schema.compliance.ftc_compliant,
                logo_required=bool(schema.restrictions.logo_required and (logo_path is not None or schema.logo_url))
            )
            
            clip_data = {
                "id":                   clip_id,
                "campaign_id":          campaign_id,
                "moment_name":          moment['moment_name'],
                "video_file":           str(final_clip_path) if final_clip_path.exists() else str(raw_clip_path),
                "logo_video_file":      str(logo_clip_path) if logo_clip_path.exists() else None,
                "captioned_video_file": str(caption_output) if caption_output.exists() else None,
                "cta_video_file":       str(cta_output) if cta_output and cta_output.exists() else (str(final_clip_path) if cta_platforms_map else None),
                "cta_platforms":        cta_platforms_map,
                "platform_videos":      cta_platforms_map,
                "cta_style":            cta_style,
                "cta_platform":         cta_platform if cta_style != 'none' else None,
                "vertical_video_file":  str(formatted_clip_path) if formatted_clip_path.exists() else None,
                "srt_file":             str(clip_srt_path) if clip_srt_path.exists() else None,
                "subtitle_mode":        subtitle_mode,
                "output_format":        output_format,
                "duration_seconds":     duration_sec,
                "start_sec":            start_sec,
                "end_sec":              end_sec,
                "confidence":           moment.get('confidence', 'low'),
                "matched_text":         moment.get('matched_text', ''),
                "hook_text":            hook_text,
                "caption_suggestions":  caption_suggestions,
                "platform_post_guide":  post_guide,
                "compliance_checklist": compliance,
                "status":               "done"
            }
            logger.info(f"Clip {clip_id} final video_file: {clip_data['video_file']}")
            
            # Save to DB
            db_clip = CampaignClip(
                id=clip_id,
                campaign_id=campaign_id,
                moment_name=moment['moment_name'],
                clip_data_json=json.dumps(clip_data),
                status="done"
            )
            db_session.add(db_clip)
            db_session.commit()
        
        update_status("done", f"Successfully generated {len(found_moments)} campaign clips")
        logger.info(f"Campaign {campaign_id} completed: {len(found_moments)} clips")
        
    except Exception as e:
        logger.error(f"Campaign pipeline failed: {e}", exc_info=True)
        update_status("failed", f"Pipeline error: {str(e)[:150]}")
    finally:
        if owns_session:
            db_session.close()


def _acquire_source_video(url: Optional[str], dest_dir: Path) -> Optional[Path]:
    """Download or locate source video."""
    dest_path = dest_dir / "source.mp4"
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        # Verify it's not an HTML page accidentally saved as mp4
        with open(dest_path, "rb") as f:
            header = f.read(512)
            if b"<html" not in header.lower() and b"<!doctype" not in header.lower():
                return dest_path

    if not url:
        return None
    
    clean_url = url.replace("file://", "").strip()
    # Check if URL is actually a local file path
    local_path = Path(clean_url)
    if local_path.exists() and local_path.is_file():
        shutil.copy(local_path, dest_path)
        logger.info(f"Copied local source video: {local_path} -> {dest_path}")
        return dest_path

    # YouTube / Bilibili / Video platform link
    if any(kw in url.lower() for kw in ["youtube.com", "youtu.be", "bilibili.com", "vimeo.com"]):
        import sys, subprocess
        ytdlp_bin = sys.executable.replace("python", "yt-dlp")
        if not Path(ytdlp_bin).exists():
            ytdlp_bin = shutil.which("yt-dlp") or "yt-dlp"
        try:
            logger.info(f"Downloading campaign video with yt-dlp: {url}")
            cmd = [
                ytdlp_bin,
                "--no-playlist",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", str(dest_path),
                url
            ]
            subprocess.run(cmd, capture_output=True, timeout=300)
            if dest_path.exists() and dest_path.stat().st_size > 1000:
                logger.info(f"yt-dlp download completed: {dest_path}")
                return dest_path
        except Exception as e:
            logger.warning(f"yt-dlp download error: {e}")

    # Google Drive share link
    drive_match = re.search(r'/(?:file/d/|open\?id=)([a-zA-Z0-9_-]+)', url)
    if drive_match:
        file_id  = drive_match.group(1)
        dl_url   = f"https://drive.google.com/uc?export=download&id={file_id}"
    else:
        dl_url = url
    
    try:
        session = requests.Session()
        resp = session.get(dl_url, stream=True, timeout=120)
        
        # Handle Google Drive virus scan confirmation for large files
        token = None
        for k, v in resp.cookies.items():
            if k.startswith('download_warning'):
                token = v
                break
        if not token and 'confirm=' in resp.text:
            match = re.search(r'confirm=([0-9A-Za-z_-]+)', resp.text)
            if match:
                token = match.group(1)
        if token:
            resp = session.get(f"{dl_url}&confirm={token}", stream=True, timeout=120)

        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        
        # Sanity check: Ensure not HTML error page
        with open(dest_path, "rb") as f:
            header = f.read(512)
            if b"<html" in header.lower() or b"<!doctype" in header.lower():
                logger.warning(f"Downloaded file appears to be an HTML page, not a video: {dest_path}")
                dest_path.unlink(missing_ok=True)
                return None

        logger.info(f"Source video downloaded: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Source video download failed: {e}")
        return None


def _parse_srt_to_segments(srt_path: Path) -> list:
    """Parse an existing SRT file into Whisper-compatible segment dicts."""
    try:
        import pysrt
        subs = None
        for enc in ["utf-8", "utf-8-sig", "latin1"]:
            try:
                subs = pysrt.open(str(srt_path), encoding=enc)
                break
            except Exception:
                continue
        if not subs:
            return []

        segments = []
        for sub in subs:
            start_sec = sub.start.ordinal / 1000.0
            end_sec   = sub.end.ordinal / 1000.0
            text      = sub.text.replace("\n", " ").strip()
            if text:
                segments.append({
                    "start": start_sec,
                    "end":   end_sec,
                    "text":  text
                })
        return segments
    except Exception as e:
        logger.warning(f"Failed to parse cached SRT file {srt_path}: {e}")
        return []


def _transcribe(video_path: Path, srt_output: Path) -> list:
    """Transcribe source video. Uses existing transcript.srt if valid, otherwise runs Whisper."""
    if srt_output.exists() and srt_output.stat().st_size > 50:
        cached_segments = _parse_srt_to_segments(srt_output)
        if cached_segments:
            logger.info(f"Reusing cached transcript ({len(cached_segments)} segments) from {srt_output}")
            return cached_segments

    try:
        return transcribe_video_to_srt(str(video_path), str(srt_output))
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
def _get_edit_mode(schema) -> str:
    """Safely extract edit_mode string from schema (Pydantic or dict)."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'edit_mode'):
            val = schema.restrictions.edit_mode
            return val.value if hasattr(val, 'value') else str(val)
        if isinstance(schema, dict):
            return str(schema.get('restrictions', {}).get('edit_mode', 'moment_extraction'))
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            return str(schema.restrictions.get('edit_mode', 'moment_extraction'))
    except Exception:
        pass
    return 'moment_extraction'


def _get_restrictions_dict(schema) -> dict:
    """Extract restrictions as a plain dict for passing to video_editor."""
    try:
        if hasattr(schema, 'restrictions'):
            r = schema.restrictions
            if hasattr(r, 'model_dump'):
                return r.model_dump()
            if hasattr(r, 'dict'):
                return r.dict()
            if isinstance(r, dict):
                return r
        if isinstance(schema, dict):
            return schema.get('restrictions', {})
    except Exception:
        pass
    return {}


def _get_output_format(schema) -> str:
    """Safely extract output_format string."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'output_format'):
            val = schema.restrictions.output_format
            return val.value if hasattr(val, 'value') else str(val)
        if isinstance(schema, dict):
            return str(schema.get('restrictions', {}).get('output_format', 'blur_pad'))
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            return str(schema.restrictions.get('output_format', 'blur_pad'))
    except Exception:
        pass
    return 'blur_pad'


def _get_logo_position(schema) -> str:
    """Safely extract logo_position string."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'logo_position'):
            val = schema.restrictions.logo_position
            return val.value if hasattr(val, 'value') else str(val)
        if isinstance(schema, dict):
            return str(schema.get('restrictions', {}).get('logo_position', 'top_right'))
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            return str(schema.restrictions.get('logo_position', 'top_right'))
    except Exception:
        pass
    return 'top_right'


def _get_logo_scale(schema) -> float:
    """Safely extract logo_scale_percent float."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'logo_scale_percent'):
            return float(schema.restrictions.logo_scale_percent)
        if isinstance(schema, dict):
            return float(schema.get('restrictions', {}).get('logo_scale_percent', 0.12))
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            return float(schema.restrictions.get('logo_scale_percent', 0.12))
    except Exception:
        pass
    return 0.12


def _get_subtitle_mode(schema) -> str:
    """Safely extract subtitle mode string regardless of schema type."""
    try:
        # Case 1: Pydantic model
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'subtitles'):
            val = schema.restrictions.subtitles
            return val.value if hasattr(val, 'value') else str(val)
        
        # Case 2: dict (schema loaded from JSON without re-parsing)
        if isinstance(schema, dict):
            restrictions = schema.get('restrictions', {})
            if isinstance(restrictions, dict):
                val = restrictions.get('subtitles', 'native_preferred')
                return val.value if hasattr(val, 'value') else str(val)
        
        # Case 3: schema.restrictions is a dict
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            val = schema.restrictions.get('subtitles', 'native_preferred')
            return val.value if hasattr(val, 'value') else str(val)
    except Exception as e:
        logger.warning(f"Could not extract subtitle_mode: {e}")
    return 'native_preferred'


def _get_caption_style(schema) -> str:
    """Safely extract caption style string."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'caption_style'):
            val = schema.restrictions.caption_style
            return val.value if hasattr(val, 'value') else str(val)
        if isinstance(schema, dict):
            restrictions = schema.get('restrictions', {})
            if isinstance(restrictions, dict):
                val = restrictions.get('caption_style', 'hormozi_yellow')
                return val.value if hasattr(val, 'value') else str(val)
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            val = schema.restrictions.get('caption_style', 'hormozi_yellow')
            return val.value if hasattr(val, 'value') else str(val)
    except Exception:
        pass
    return 'hormozi_yellow'


def _get_show_hook_banner(schema) -> bool:
    """Safely extract show_hook_banner boolean (defaults to True)."""
    try:
        if hasattr(schema, 'restrictions') and hasattr(schema.restrictions, 'show_hook_banner'):
            val = schema.restrictions.show_hook_banner
            return bool(val)
        if isinstance(schema, dict):
            restrictions = schema.get('restrictions', {})
            if isinstance(restrictions, dict):
                return bool(restrictions.get('show_hook_banner', True))
        if hasattr(schema, 'restrictions') and isinstance(schema.restrictions, dict):
            return bool(schema.restrictions.get('show_hook_banner', True))
    except Exception:
        pass
    return True


def _get_cta_settings(schema) -> dict:
    """Safely extract CTA settings from schema."""
    defaults = {
        'cta_style':         'follow_tap',
        'cta_platform':      'auto',
        'cta_position':      'bottom_right',
        'cta_handle':        '',
        'cta_start_offset':  None,
    }
    try:
        r = schema.restrictions if hasattr(schema, 'restrictions') else \
            schema.get('restrictions', {}) if isinstance(schema, dict) else {}
        for k in defaults:
            val = r.get(k) if isinstance(r, dict) else getattr(r, k, None)
            if val is not None:
                v = val.value if hasattr(val, 'value') else val
                defaults[k] = v
    except Exception:
        pass
    return defaults



def _burn_ass_captions(input_path: Path, ass_path: Path, output_path: Path) -> bool:
    """Burn ASS captions into video. Returns True on success."""
    import subprocess
    ass_path_str = str(ass_path).replace('\\', '/').replace(':', r'\:')
    
    for filter_name in ['ass', 'subtitles']:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"{filter_name}={ass_path_str}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Captions burned via '{filter_name}=' filter: {output_path}")
                return True
            else:
                logger.warning(f"'{filter_name}=' filter failed (rc={result.returncode}): {result.stderr[-300:] if result.stderr else ''}")
        except subprocess.TimeoutExpired:
            logger.error("Caption burn timed out")
            return False
        except Exception as e:
            logger.error(f"Caption burn exception: {e}")
            return False
    
    logger.error("Both 'ass=' and 'subtitles=' filters failed. Check FFmpeg libass support.")
    return False

