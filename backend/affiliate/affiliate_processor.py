"""
Affiliate Marketing Video Processor
Lightweight, focused video processing pipeline that:
1. Transcribes audio in Filipino / Tagalog ('tl') with word-level timestamps using:
   - Primary/High-Accuracy: Google Gemini 2.5 Flash AI (native conversational Filipino & slang)
   - Fallback/Offline: faster-whisper (CTranslate2)
2. Generates styled viral ASS captions (active-word highlights, 9:16 safe-zone margins).
3. Burns styled captions into the video via FFmpeg libass.
4. Overlays an authentic animated Facebook Follow CTA ('Follow' pill / card with checkmark animation).
5. Produces a polished affiliate marketing video ready for Facebook / Reels / TikTok.
"""

import os
import re
import json
import time
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

from backend.utils.caption_styles import ViralCaptionGenerator, CAPTION_STYLES, _parse_time_to_seconds
from backend.utils.cta_overlay import apply_cta_overlay

logger = logging.getLogger(__name__)


class AffiliateVideoProcessor:
    """
    Dedicated processor for affiliate marketing videos.
    Contains ONLY the captioning system and Facebook CTA system.
    """

    def __init__(
        self,
        whisper_model: str = "small",
        device: str = "auto",
        compute_type: str = "int8",
        default_caption_style: str = "hormozi_yellow",
        default_engine: str = "auto",
    ):
        """
        Initialize the affiliate video processor.
        
        Args:
            whisper_model: faster-whisper model size ('tiny', 'base', 'small', 'medium')
            device: 'auto', 'cpu', or 'cuda'
            compute_type: 'int8', 'float16', 'float32'
            default_caption_style: Style preset from CAPTION_STYLES ('hormozi_yellow', 'neon_green', 'neon_cyan', etc.)
            default_engine: 'auto' (prefers Gemini for high accuracy), 'gemini', or 'whisper'
        """
        self.whisper_model_name = whisper_model
        self.device = device
        self.compute_type = compute_type
        self.default_caption_style = default_caption_style
        self.default_engine = default_engine
        self._whisper_model = None

    def _get_gemini_api_key(self) -> Optional[str]:
        """Fetch Gemini API key from environment variables or .env file."""
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_GEMINI_API_KEY")
        if not api_key:
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_file.exists():
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("GEMINI_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break
                            elif line.startswith("API_GEMINI_API_KEY=") and not api_key:
                                api_key = line.split("=", 1)[1].strip()
                except Exception:
                    pass
        return api_key

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

    def transcribe_with_gemini(
        self,
        video_path: Path,
        language: str = "tl"
    ) -> List[Dict[str, Any]]:
        """
        Transcribe audio using Google Gemini 2.5 Flash for native, high-accuracy Filipino/Taglish.
        Produces short, punchy subtitle chunks with word-level interpolated timestamps.
        """
        api_key = self._get_gemini_api_key()
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or .env")

        from google import genai
        from google.genai import types

        video_path = Path(video_path)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            tmp_audio_path = tmp_audio.name

        try:
            # Extract 16kHz mono audio for optimal speech recognition
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",
                "-ar", "16000",
                "-ac", "1",
                "-b:a", "64k",
                tmp_audio_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            with open(tmp_audio_path, "rb") as f:
                audio_bytes = f.read()

            client = genai.Client(api_key=api_key)
            prompt = """
You are an expert transcriber for Philippine social media, TikTok, and Facebook affiliate marketing videos.
Transcribe this entire audio in native conversational Filipino (Tagalog / Taglish) with 100% accuracy.
Ensure correct Filipino spelling, slang, and brand terms (e.g. portable gas stove, solid, sulit, brownout, Shopee, etc.).
Break speech into punchy, short subtitle chunks (2 to 5 words per chunk, 1 to 2.5 seconds each) designed for TikTok / Reels / Shorts captions.
Return strictly a JSON array of objects without markdown formatting:
[
  {"start": 0.0, "end": 2.1, "text": "Grabe, ito na 'yung binili ko"},
  {"start": 2.1, "end": 4.6, "text": "na portable gas stove!"}
]
"""
            logger.info(f"Transcribing {video_path.name} with Gemini 2.5 Flash (Filipino AI)...")
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3"),
                    prompt
                ]
            )

            raw = res.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

            chunks = json.loads(raw.strip())
            structured_segments: List[Dict[str, Any]] = []

            for chunk in chunks:
                start_t = float(chunk["start"])
                end_t = float(chunk["end"])
                chunk_text = str(chunk["text"]).strip()
                if not chunk_text:
                    continue

                # Tokenize words and interpolate word timings
                words = chunk_text.split()
                w_count = len(words)
                total_duration = max(0.2, end_t - start_t)
                word_dur = total_duration / max(1, w_count)

                words_list = []
                for i, w in enumerate(words):
                    w_s = round(start_t + i * word_dur, 2)
                    w_e = round(min(end_t, w_s + word_dur), 2)
                    words_list.append({
                        "word": w,
                        "start": w_s,
                        "end": w_e
                    })

                structured_segments.append({
                    "start": start_t,
                    "end": end_t,
                    "text": chunk_text,
                    "words": words_list
                })

            logger.info(f"Gemini transcription complete: {len(structured_segments)} accurate Filipino chunks.")
            return structured_segments

        finally:
            if os.path.exists(tmp_audio_path):
                try:
                    os.remove(tmp_audio_path)
                except Exception:
                    pass

    def transcribe_with_whisper(
        self,
        video_path: Path,
        language: str = "tl",
        vad_filter: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Transcribe speech from video using local faster-whisper.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Input video not found: {video_path}")

        model = self._get_whisper_model()
        logger.info(f"Transcribing {video_path.name} with faster-whisper (model='{self.whisper_model_name}', language='{language}')...")

        # Initial prompt with authentic Filipino affiliate vocabulary
        filipino_prompt = (
            "Grabe, sobrang ganda, sulit, i-try natin kung gaano kabilis, portable gas stove, sapatos, tela, "
            "quality, malakas ang apoy, i-on natin, safe dalhin sa bag, checkout, comment section, link, follow."
        )

        seg_iter, _ = model.transcribe(
            str(video_path),
            language=language,
            vad_filter=vad_filter,
            word_timestamps=True,
            initial_prompt=filipino_prompt
        )
        raw_segments = list(seg_iter)

        if not raw_segments and vad_filter:
            logger.info("VAD filter yielded no speech segments, retrying without VAD filter...")
            seg_iter, _ = model.transcribe(
                str(video_path),
                language=language,
                vad_filter=False,
                word_timestamps=True,
                initial_prompt=filipino_prompt
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

        logger.info(f"Whisper transcription complete: {len(structured_segments)} segments extracted.")
        return structured_segments

    def transcribe_filipino(
        self,
        video_path: Path,
        language: str = "tl",
        engine: str = "auto",
        vad_filter: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe video audio with automatic model routing:
        1. If engine == 'gemini' or ('auto' and GEMINI_API_KEY available): use Gemini 2.5 Flash for native Filipino accuracy.
        2. Fall back to faster-whisper on any error or if engine == 'whisper'.
        """
        chosen_engine = engine or self.default_engine
        use_gemini = (chosen_engine == "gemini") or (chosen_engine == "auto" and bool(self._get_gemini_api_key()))

        if use_gemini:
            try:
                segments = self.transcribe_with_gemini(video_path, language=language)
                return {
                    "segments": segments,
                    "model": "gemini-2.5-flash",
                    "engine": "gemini"
                }
            except Exception as e:
                logger.warning(f"Gemini transcription failed ({e}), falling back to local faster-whisper...")

        segments = self.transcribe_with_whisper(video_path, language=language, vad_filter=vad_filter)
        return {
            "segments": segments,
            "model": f"whisper-{self.whisper_model_name}",
            "engine": "whisper"
        }

    @staticmethod
    def parse_transcript_content(content: str) -> Optional[List[Dict[str, Any]]]:
        """
        Parse user-provided transcript content into structured subtitle segments.
        Supports:
        - SRT format (subtitles with HH:MM:SS,mmm --> HH:MM:SS,mmm)
        - WebVTT format (WEBVTT with HH:MM:SS.mmm --> HH:MM:SS.mmm)
        - JSON array of segment dicts (or dict with 'segments')
        If timestamps are present, interpolates word-level timestamps so word-by-word active
        highlight styling operates smoothly.
        Returns None if content is plain untimed text.
        """
        if not content or not content.strip():
            return None

        clean_content = content.strip()

        # 1. Try JSON parsing
        if clean_content.startswith(("[", "{")):
            try:
                data = json.loads(clean_content)
                if isinstance(data, dict) and "segments" in data:
                    data = data["segments"]
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    if "start" in data[0] and "text" in data[0]:
                        structured = []
                        for item in data:
                            st = float(item.get("start", 0.0))
                            en = float(item.get("end", st + 2.0))
                            txt = str(item.get("text", "")).strip()
                            words = item.get("words", [])
                            if not words and txt:
                                w_tokens = txt.split()
                                if w_tokens:
                                    dur = max(0.1, en - st)
                                    step = dur / len(w_tokens)
                                    words = [
                                        {"word": w, "start": round(st + i * step, 3), "end": round(st + (i + 1) * step, 3)}
                                        for i, w in enumerate(w_tokens)
                                    ]
                            structured.append({
                                "start": st,
                                "end": en,
                                "text": txt,
                                "words": words
                            })
                        return structured
            except Exception:
                pass

        # 2. Try SRT / WebVTT parsing
        if "-->" in clean_content:
            raw_blocks = re.split(r'\n\s*\n', clean_content)
            segments = []
            for block in raw_blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if not lines:
                    continue
                time_line_idx = -1
                for idx, line in enumerate(lines[:3]):
                    if "-->" in line:
                        time_line_idx = idx
                        break
                if time_line_idx == -1:
                    continue

                time_line = lines[time_line_idx]
                time_match = re.search(r'((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)', time_line)
                if not time_match:
                    continue

                start_sec = _parse_time_to_seconds(time_match.group(1))
                end_sec = _parse_time_to_seconds(time_match.group(2))
                text_lines = lines[time_line_idx + 1:]
                clean_text = ' '.join(text_lines)
                clean_text = re.sub(r'<[^>]+>', '', clean_text).strip()

                if clean_text and end_sec > start_sec:
                    # Interpolate word timings for highlighting
                    w_tokens = clean_text.split()
                    dur = max(0.1, end_sec - start_sec)
                    step = dur / max(1, len(w_tokens))
                    words = [
                        {"word": w, "start": round(start_sec + i * step, 3), "end": round(start_sec + (i + 1) * step, 3)}
                        for i, w in enumerate(w_tokens)
                    ]
                    segments.append({
                        "start": start_sec,
                        "end": end_sec,
                        "text": clean_text,
                        "words": words
                    })

            if segments:
                return segments

        # If neither JSON nor timestamped subtitle pattern was found, it's untimed text
        return None

    def align_transcript_with_audio(
        self,
        reference_text: str,
        video_path: Path,
        language: str = "tl"
    ) -> List[Dict[str, Any]]:
        """
        Align an untimed user transcript script to the actual audio in the video.
        Uses Gemini 2.5 Flash to accurately synchronize the user's exact words with speech timestamps.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found for alignment: {video_path}")

        api_key = self._get_gemini_api_key()
        if not api_key:
            logger.warning("GEMINI_API_KEY not found for transcript audio alignment; using duration-proportional pacing fallback.")
            return self._fallback_script_pacing(reference_text, video_path)

        # Extract 16kHz mono audio
        tmp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_audio_path = tmp_audio.name
        tmp_audio.close()

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-b:a", "64k",
                tmp_audio_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0 or not os.path.exists(tmp_audio_path) or os.path.getsize(tmp_audio_path) < 500:
                raise RuntimeError("Failed to extract audio for transcript alignment.")

            with open(tmp_audio_path, "rb") as f:
                audio_bytes = f.read()

            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a professional audio alignment and subtitle synchronization system.\n"
                f"We have an audio track of a video, and the EXACT reference transcript provided by the creator.\n"
                f"Language: {language} (Filipino / Tagalog).\n\n"
                f"YOUR TASK: Align the user's reference transcript to the audio timestamps.\n"
                f"RULES:\n"
                f"1. Use the EXACT text provided by the user. Do NOT omit, rephrase, or rewrite their words.\n"
                f"2. Break the transcript into natural, short subtitle chunks (2 to 6 words each) suitable for vertical mobile video captions.\n"
                f"3. For each chunk, provide exact start and end timestamps in seconds (float).\n"
                f"4. For each word in the chunk, provide word-level start and end timestamps.\n"
                f"5. Return ONLY a valid JSON array of chunk objects.\n\n"
                f"User's Reference Transcript:\n"
                f'\"\"\"{reference_text.strip()}\"\"\"\n\n'
                f"Output format:\n"
                f"[\n"
                f'  {{"start": 0.0, "end": 2.1, "text": "...", "words": [{{"word": "...", "start": 0.0, "end": 0.5}}]}}\n'
                f"]"
            )

            logger.info(f"Aligning user transcript ({len(reference_text)} chars) with audio using Gemini 2.5 Flash...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3"),
                    prompt
                ]
            )

            raw_text = response.text or ""
            raw_text = re.sub(r"^```json\s*", "", raw_text.strip())
            raw_text = re.sub(r"^```\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text.strip())

            segments_data = json.loads(raw_text)
            if not isinstance(segments_data, list) or not segments_data:
                raise ValueError("Gemini returned invalid segment list structure.")

            structured: List[Dict[str, Any]] = []
            for seg in segments_data:
                st = float(seg.get("start", 0.0))
                en = float(seg.get("end", st + 1.0))
                txt = str(seg.get("text", "")).strip()
                words = seg.get("words", [])
                if not words and txt:
                    w_tokens = txt.split()
                    step = (en - st) / max(1, len(w_tokens))
                    words = [
                        {"word": w, "start": round(st + i * step, 3), "end": round(st + (i + 1) * step, 3)}
                        for i, w in enumerate(w_tokens)
                    ]
                structured.append({
                    "start": st,
                    "end": en,
                    "text": txt,
                    "words": words
                })
            logger.info(f"Transcript aligned successfully: {len(structured)} chunks created.")
            return structured

        except Exception as e:
            logger.warning(f"Gemini transcript alignment failed ({e}); falling back to proportional script pacing.")
            return self._fallback_script_pacing(reference_text, video_path)
        finally:
            if os.path.exists(tmp_audio_path):
                try:
                    os.remove(tmp_audio_path)
                except Exception:
                    pass

    def _fallback_script_pacing(self, text: str, video_path: Path) -> List[Dict[str, Any]]:
        """Fallback when audio alignment cannot be run: evenly pace script sentences across video duration."""
        vinfo = self.get_video_info(video_path)
        duration = vinfo.get("duration", 30.0)
        lines = [l.strip() for l in re.split(r'[\n.!?]+', text) if l.strip()]
        if not lines:
            lines = [text.strip()]
        seg_dur = duration / max(1, len(lines))
        segments = []
        for i, line in enumerate(lines):
            st = i * seg_dur
            en = min(duration, (i + 1) * seg_dur)
            w_tokens = line.split()
            step = (en - st) / max(1, len(w_tokens))
            words = [
                {"word": w, "start": round(st + j * step, 3), "end": round(st + (j + 1) * step, 3)}
                for j, w in enumerate(w_tokens)
            ]
            segments.append({
                "start": round(st, 3),
                "end": round(en, 3),
                "text": line,
                "words": words
            })
        return segments

    def load_or_align_transcript(
        self,
        transcript_source: Union[str, Path],
        video_path: Path,
        language: str = "tl"
    ) -> Dict[str, Any]:
        """
        Load an existing transcription or align an untimed transcript with the video.
        Accepts:
        - A Path or path string to an .srt, .vtt, .txt, or .json file
        - A raw string containing SRT subtitles or plain text script
        Returns:
            Dict containing:
                "segments": List[Dict[str, Any]],
                "model": str,
                "engine": str
        """
        content = ""
        source_is_file = False
        source_str = str(transcript_source).strip()

        try:
            possible_path = Path(source_str)
            if possible_path.exists() and possible_path.is_file():
                content = possible_path.read_text(encoding="utf-8", errors="ignore")
                source_is_file = True
        except Exception:
            pass

        if not content:
            content = source_str

        if not content.strip():
            raise ValueError("Provided transcript content is empty.")

        # 1. Attempt to parse as timed subtitle (SRT / VTT / JSON with timestamps)
        timed_segments = self.parse_transcript_content(content)
        if timed_segments:
            logger.info(f"Loaded {len(timed_segments)} timed subtitle segments from transcript source.")
            return {
                "segments": timed_segments,
                "model": "user-transcript-file" if source_is_file else "user-transcript-text",
                "engine": "custom_file"
            }

        # 2. Untimed script: align against video audio
        logger.info("Transcript contains no timestamps. Aligning transcript text with video audio...")
        aligned_segments = self.align_transcript_with_audio(content, video_path=video_path, language=language)
        return {
            "segments": aligned_segments,
            "model": "user-script-aligned",
            "engine": "gemini_aligned"
        }

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
        transcript_source: Optional[Union[str, Path]] = None,
        fb_handle: str = "",
        caption_style: Optional[str] = None,
        cta_style: str = "pill",
        cta_position: str = "lower_center",
        language: str = "tl",
        engine: str = "auto",
        keep_intermediate: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete end-to-end affiliate video creation pipeline:
        1. Probe video dimensions and duration.
        2. Obtain subtitle segments: from provided user transcript slot (SRT/VTT/aligned script)
           or automatically transcribed via Gemini 2.5 Flash / Whisper in Filipino ('tl').
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
            final_output = input_path.parent / f"{input_path.stem}_filipino_fb.mp4"
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

            # 1. Obtain subtitle segments (from user transcript slot or automatic speech transcription)
            if transcript_source:
                logger.info("Using provided user transcript slot for video captions...")
                trans_result = self.load_or_align_transcript(transcript_source, input_path, language=language)
            else:
                trans_result = self.transcribe_filipino(input_path, language=language, engine=engine)

            segments = trans_result["segments"]
            model_used = trans_result["model"]

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

            # Write SRT/ASS companion files next to final output
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
                "model_used": model_used,
                "transcript_provided": bool(transcript_source),
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
            logger.info(f"Affiliate video processing completed in {elapsed}s (Model: {model_used}) -> {final_output}")
            return result

        finally:
            if not keep_intermediate:
                import shutil
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
