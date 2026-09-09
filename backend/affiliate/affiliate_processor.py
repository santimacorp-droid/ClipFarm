"""
Affiliate Marketing Video Processor
Lightweight, focused video processing pipeline that:
1. Transcribes audio in Filipino / Tagalog ('tl') with word-level timestamps using faster-whisper.
2. Generates styled viral ASS captions (active-word highlights, 9:16 safe-zone margins).
3. Burns styled captions into the video via FFmpeg libass.
4. Overlays an authentic animated Facebook Follow CTA ('Follow' pill / card with checkmark animation).
5. Produces a polished affiliate marketing video ready for Facebook / Reels / TikTok.
"""

import os
import json
import time
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

from backend.utils.caption_styles import ViralCaptionGenerator, CAPTION_STYLES
from backend.utils.cta_overlay import apply_cta_overlay

logger = logging.getLogger(__name__)


class AffiliateVideoProcessor:
    """
    Dedicated processor for affiliate marketing videos.
    Contains ONLY the captioning system and Facebook CTA system.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        default_caption_style: str = "hormozi_yellow",
    ):
        """
        Initialize the affiliate video processor.
        
        Args:
            whisper_model: faster-whisper model size ('tiny', 'base', 'small', 'medium')
            device: 'auto', 'cpu', or 'cuda'
            compute_type: 'int8', 'float16', 'float32'
            default_caption_style: Style preset from CAPTION_STYLES ('hormozi_yellow', 'neon_green', 'neon_cyan', etc.)
        """
        self.whisper_model_name = whisper_model
        self.device = device
        self.compute_type = compute_type
        self.default_caption_style = default_caption_style
        self._whisper_model = None

    def _get_whisper_model(self):
        """Lazy load faster-whisper model to optimize startup time and memory."""
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model '{self.whisper_model_name}' on {self.device}...")
            self._whisper_model = WhisperModel(
                self.whisper_model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._whisper_model

    @staticmethod
    def get_video_info(video_path: Path) -> Dict[str, Any]:
        """Extract video resolution, duration, and framerate via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name",
            "-of", "json", str(video_path)
        ]
        info = {
            "width": 1080,
            "height": 1920,
            "duration": 30.0,
            "fps": 30.0,
            "codec": "h264"
        }
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                if "format" in data and "duration" in data["format"]:
                    info["duration"] = float(data["format"]["duration"])
                if "streams" in data:
                    for s in data["streams"]:
                        if s.get("width") and s.get("height"):
                            info["width"] = int(s["width"])
                            info["height"] = int(s["height"])
                            if "r_frame_rate" in s and "/" in s["r_frame_rate"]:
                                num, den = s["r_frame_rate"].split("/")
                                if float(den) > 0:
                                    info["fps"] = float(num) / float(den)
                            info["codec"] = s.get("codec_name", "h264")
                            break
        except Exception as e:
            logger.warning(f"Failed to probe video {video_path}: {e}")
        return info

    def transcribe_filipino(
        self,
        video_path: Path,
        language: str = "tl",
        vad_filter: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Transcribe speech from video in Filipino/Tagalog ('tl') with word-level timestamps.
        
        Returns:
            List of segment dictionaries with 'start', 'end', 'text', and 'words'.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Input video not found: {video_path}")

        model = self._get_whisper_model()
        logger.info(f"Transcribing {video_path.name} in Filipino (language='{language}')...")

        # First attempt with vad_filter
        seg_iter, transcription_info = model.transcribe(
            str(video_path),
            language=language,
            vad_filter=vad_filter,
            word_timestamps=True,
            initial_prompt="Magandang araw! Ito ay isang affiliate marketing product review sa Tagalog o Filipino."
        )
        raw_segments = list(seg_iter)

        # If vad_filter filtered everything out, retry without vad_filter
        if not raw_segments and vad_filter:
            logger.info("VAD filter yielded no speech segments, retrying without VAD filter...")
            seg_iter, _ = model.transcribe(
                str(video_path),
                language=language,
                vad_filter=False,
                word_timestamps=True
            )
            raw_segments = list(seg_iter)

        structured_segments: List[Dict[str, Any]] = []
        for s in raw_segments:
            words_list = []
            if hasattr(s, "words") and s.words:
                for w in s.words:
                    word_clean = w.word.strip()
                    if word_clean:
                        words_list.append({
                            "word": word_clean,
                            "start": float(w.start),
                            "end": float(w.end)
                        })
            
            clean_text = s.text.strip()
            if clean_text:
                structured_segments.append({
                    "start": float(s.start),
                    "end": float(s.end),
                    "text": clean_text,
                    "words": words_list
                })

        logger.info(f"Transcription complete: {len(structured_segments)} segments extracted.")
        return structured_segments

    def export_srt(self, segments: List[Dict[str, Any]], output_srt_path: Path) -> Path:
        """Write standard SRT subtitle file."""
        output_srt_path = Path(output_srt_path)
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)
        
        def fmt_ts(seconds: float) -> str:
            millis = int((seconds - int(seconds)) * 1000)
            mins, secs = divmod(int(seconds), 60)
            hours, mins = divmod(mins, 60)
            return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

        lines = []
        for idx, seg in enumerate(segments, 1):
            s_ts = fmt_ts(seg["start"])
            e_ts = fmt_ts(seg["end"])
            lines.append(f"{idx}\n{s_ts} --> {e_ts}\n{seg['text']}\n")

        content = "\n".join(lines)
        output_srt_path.write_text(content, encoding="utf-8")
        return output_srt_path

    def generate_styled_ass(
        self,
        segments: List[Dict[str, Any]],
        output_ass_path: Path,
        video_width: int,
        video_height: int,
        style: Optional[str] = None
    ) -> Path:
        """
        Generate ASS subtitle file with active-word highlight styling using ViralCaptionGenerator.
        """
        output_ass_path = Path(output_ass_path)
        output_ass_path.parent.mkdir(parents=True, exist_ok=True)
        chosen_style = style or self.default_caption_style

        ok = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=None,
            clip_start=0.0,
            clip_end=999999.0,
            output_ass_path=output_ass_path,
            style_key=chosen_style,
            video_width=video_width,
            video_height=video_height,
            words_data=segments,
            show_hook_banner=False
        )

        if not ok or not output_ass_path.exists() or output_ass_path.stat().st_size == 0:
            raise RuntimeError(f"Failed to generate ASS file at {output_ass_path}")

        logger.info(f"Generated styled ASS captions ({chosen_style}): {output_ass_path}")
        return output_ass_path

    @staticmethod
    def burn_captions(
        input_video_path: Path,
        ass_path: Path,
        output_video_path: Path
    ) -> Path:
        """Burn ASS subtitles into video using FFmpeg libass."""
        input_video_path = Path(input_video_path)
        ass_path = Path(ass_path)
        output_video_path = Path(output_video_path)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        ass_filter_path = str(ass_path.resolve()).replace("\\", "/").replace(":", r"\:")

        for filter_name in ["ass", "subtitles"]:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video_path),
                "-vf", f"{filter_name}='{ass_filter_path}'",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-c:a", "copy",
                str(output_video_path)
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if res.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 1024:
                    logger.info(f"Burned subtitles via filter '{filter_name}': {output_video_path}")
                    return output_video_path
                else:
                    logger.warning(f"Filter '{filter_name}' burn attempt failed: {res.stderr[-300:] if res.stderr else ''}")
            except Exception as e:
                logger.warning(f"Caption burn error with '{filter_name}': {e}")

        raise RuntimeError("Failed to burn ASS subtitles with FFmpeg (both 'ass' and 'subtitles' filters failed).")

    @staticmethod
    def apply_facebook_cta(
        input_video_path: Path,
        output_video_path: Path,
        fb_handle: str = "",
        cta_style: str = "pill",
        cta_position: str = "lower_center",
        start_time: Optional[float] = None,
        video_width: Optional[int] = None,
        video_height: Optional[int] = None,
        video_duration: Optional[float] = None
    ) -> Path:
        """
        Overlay the Facebook Follow CTA animation onto the video.
        """
        input_video_path = Path(input_video_path)
        output_video_path = Path(output_video_path)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        success = apply_cta_overlay(
            input_path=input_video_path,
            output_path=output_video_path,
            platform="facebook",
            handle=fb_handle,
            style=cta_style,
            position=cta_position,
            start_time=start_time,
            video_width=video_width,
            video_height=video_height,
            video_duration=video_duration
        )

        if not success or not output_video_path.exists() or output_video_path.stat().st_size <= 1024:
            raise RuntimeError(f"Failed to apply Facebook CTA overlay to {input_video_path}")

        logger.info(f"Applied Facebook Follow CTA: {output_video_path}")
        return output_video_path

    def process_affiliate_video(
        self,
        input_video_path: Union[str, Path],
        output_video_path: Optional[Union[str, Path]] = None,
        fb_handle: str = "",
        caption_style: Optional[str] = None,
        cta_style: str = "pill",
        cta_position: str = "lower_center",
        language: str = "tl",
        keep_intermediate: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end affiliate video creation pipeline:
        1. Probe video dimensions and duration.
        2. Transcribe audio in Filipino ('tl') with word timestamps.
        3. Generate stylish ASS captions (e.g. Hormozi Yellow).
        4. Burn captions into video.
        5. Overlay Facebook Follow CTA.
        6. Return complete metadata and output path.
        """
        t0 = time.time()
        input_path = Path(input_video_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input video does not exist: {input_path}")

        # Determine output paths
        if output_video_path:
            final_output = Path(output_video_path).resolve()
        else:
            final_output = input_path.parent / f"{input_path.stem}_filipino_fb_cta.mp4"
        final_output.parent.mkdir(parents=True, exist_ok=True)

        # Video metadata
        vinfo = self.get_video_info(input_path)
        w, h, duration = vinfo["width"], vinfo["height"], vinfo["duration"]
        logger.info(f"Processing affiliate video: {input_path.name} ({w}x{h}, {duration:.1f}s)")

        # Create temporary working directory for intermediate files
        temp_dir = Path(tempfile.mkdtemp(prefix="affiliate_vid_"))
        try:
            srt_path = temp_dir / f"{input_path.stem}.srt"
            ass_path = temp_dir / f"{input_path.stem}.ass"
            captioned_video = temp_dir / f"{input_path.stem}_captioned.mp4"

            # 1. Transcribe Filipino speech
            segments = self.transcribe_filipino(input_path, language=language)
            self.export_srt(segments, srt_path)

            # 2. Generate styled ASS captions
            chosen_style = caption_style or self.default_caption_style
            self.generate_styled_ass(
                segments=segments,
                output_ass_path=ass_path,
                video_width=w,
                video_height=h,
                style=chosen_style
            )

            # 3. Burn captions into video
            self.burn_captions(
                input_video_path=input_path,
                ass_path=ass_path,
                output_video_path=captioned_video
            )

            # 4. Overlay Facebook Follow CTA
            self.apply_facebook_cta(
                input_video_path=captioned_video,
                output_video_path=final_output,
                fb_handle=fb_handle,
                cta_style=cta_style,
                cta_position=cta_position,
                video_width=w,
                video_height=h,
                video_duration=duration
            )

            elapsed = round(time.time() - t0, 2)
            word_count = sum(len(s.get("words", [])) for s in segments)

            # If user wants to keep SRT/ASS companion files next to final output
            final_srt = final_output.parent / f"{final_output.stem}.srt"
            final_ass = final_output.parent / f"{final_output.stem}.ass"
            final_srt.write_text(srt_path.read_text(encoding="utf-8"), encoding="utf-8")
            final_ass.write_text(ass_path.read_text(encoding="utf-8"), encoding="utf-8")

            result = {
                "success": True,
                "input_video": str(input_path),
                "output_video": str(final_output),
                "srt_path": str(final_srt),
                "ass_path": str(final_ass),
                "language": language,
                "caption_style": chosen_style,
                "cta_platform": "facebook",
                "cta_handle": fb_handle,
                "cta_style": cta_style,
                "video_width": w,
                "video_height": h,
                "video_duration": duration,
                "segment_count": len(segments),
                "word_count": word_count,
                "processing_time_sec": elapsed,
            }
            logger.info(f"Affiliate video processing completed in {elapsed}s -> {final_output}")
            return result

        finally:
            if not keep_intermediate:
                import shutil
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
