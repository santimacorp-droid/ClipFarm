"""
Speech Recognition Utility - Multi-provider speech recognition service
Supports local Whisper, OpenAI API, Azure Speech Services, etc.
"""
import logging
import subprocess
import json
import os
import re
import asyncio
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from enum import Enum
import time
import requests
from dataclasses import dataclass
from .ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)


class SpeechRecognitionMethod(str, Enum):
    """Speech recognition method enumeration"""
    WHISPER_LOCAL = "whisper_local"
    OPENAI_API = "openai_api"
    AZURE_SPEECH = "azure_speech"
    GOOGLE_SPEECH = "google_speech"
    ALIYUN_SPEECH = "aliyun_speech"
    # Reserved for future service extension
    CUSTOM_API = "custom_api"


class LanguageCode(str, Enum):
    """Supported language codes"""
    # Chinese
    CHINESE_SIMPLIFIED = "zh"
    CHINESE_TRADITIONAL = "zh-TW"
    # English
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    # Japanese
    JAPANESE = "ja"
    # Korean
    KOREAN = "ko"
    # French
    FRENCH = "fr"
    # German
    GERMAN = "de"
    # Spanish
    SPANISH = "es"
    # Russian
    RUSSIAN = "ru"
    # Arabic
    ARABIC = "ar"
    # Portuguese
    PORTUGUESE = "pt"
    # Italian
    ITALIAN = "it"
    # Auto-detect
    AUTO = "auto"


@dataclass
class SpeechRecognitionConfig:
    """Speech recognition configuration"""
    method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL
    language: LanguageCode = LanguageCode.ENGLISH
    model: str = "small"  # Whisper model size (small provides 2x accuracy over base)
    timeout: int = 0  # Timeout in seconds, 0 for unlimited
    output_format: str = "srt"  # Output format
    enable_timestamps: bool = True  # Enable timestamps
    enable_punctuation: bool = True  # Enable punctuation
    enable_speaker_diarization: bool = False  # Enable speaker diarization
    enable_fallback: bool = True  # Enable fallback mechanism
    fallback_method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL  # Fallback method
    
    # API configuration
    openai_api_key: Optional[str] = None
    azure_speech_key: Optional[str] = None
    azure_speech_region: Optional[str] = None
    google_credentials_path: Optional[str] = None
    aliyun_access_key: Optional[str] = None
    aliyun_access_secret: Optional[str] = None
    custom_api_url: Optional[str] = None
    custom_api_key: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration parameters"""
        # Validate method
        if not isinstance(self.method, SpeechRecognitionMethod):
            try:
                self.method = SpeechRecognitionMethod(self.method)
            except ValueError:
                raise ValueError(f"Unsupported speech recognition method: {self.method}")
        
        # Validate language
        if not isinstance(self.language, LanguageCode):
            try:
                self.language = LanguageCode(self.language)
            except ValueError:
                raise ValueError(f"Unsupported language code: {self.language}")
        
        # Validate model
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if self.model not in valid_models:
            raise ValueError(f"Unsupported Whisper model: {self.model}")
        
        # Validate timeout
        if self.timeout < 0:
            raise ValueError("Timeout cannot be negative")
        
        # Validate output format
        valid_formats = ["srt", "vtt", "txt", "json"]
        if self.output_format not in valid_formats:
            raise ValueError(f"Unsupported output format: {self.output_format}")


class SpeechRecognitionError(Exception):
    """Speech recognition error"""
    pass


def _synthesize_words_from_sentence(text: str, start: float, end: float) -> List[Dict[str, Any]]:
    """Synthesizes approximate word/character timestamps across a time interval."""
    clean_text = text.strip()
    if not clean_text or end <= start:
        return []
    
    # Check if text is predominantly CJK
    cjk_count = sum(1 for ch in clean_text if '\u4e00' <= ch <= '\u9fff')
    if cjk_count > len(clean_text) * 0.3:
        tokens = [ch for ch in clean_text if not ch.isspace()]
    else:
        tokens = clean_text.split()
        
    if not tokens:
        return [{"word": clean_text, "start": start, "end": end}]
        
    total_dur = end - start
    step = total_dur / len(tokens)
    words = []
    for i, token in enumerate(tokens):
        w_start = round(start + i * step, 3)
        w_end = round(start + (i + 1) * step, 3)
        words.append({"word": token, "start": w_start, "end": w_end})
    return words


def transcribe_with_qwen_asr(audio_path: Union[str, Path], api_key: Optional[str] = None, language: str = "auto") -> List[Dict[str, Any]]:
    """
    Transcribes audio using Alibaba Cloud DashScope qwen3-asr-flash-filetrans model.
    Extracts word-level timestamps and formats them into standard segment structures.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise SpeechRecognitionError(f"Audio file does not exist: {audio_path}")

    dash_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
    if not dash_key:
        raise SpeechRecognitionError("DashScope ASR requires DASHSCOPE_API_KEY or API_DASHSCOPE_API_KEY environment variable")

    import dashscope
    from dashscope.audio.asr import Transcription
    from dashscope.utils.oss_utils import check_and_upload_local
    dashscope.api_key = dash_key

    # Upload local audio file to temporary OSS storage if necessary
    file_url = str(audio_path)
    if not str(audio_path).startswith(("http://", "https://", "oss://")):
        try:
            logger.info(f"[AutoClip] Uploading audio {audio_path.name} to DashScope OSS...")
            is_upload, oss_url, _ = check_and_upload_local(
                model="qwen3-asr-flash-filetrans",
                content=str(audio_path),
                api_key=dash_key
            )
            if is_upload and oss_url:
                file_url = oss_url
                logger.info(f"[AutoClip] Audio uploaded to {file_url}")
            else:
                file_url = f"file://{audio_path.resolve()}"
        except Exception as up_err:
            logger.warning(f"[AutoClip] DashScope OSS upload failed ({up_err}), trying direct path: {audio_path}")
            file_url = str(audio_path)

    logger.info(f"[AutoClip] Submitting ASR job to qwen3-asr-flash-filetrans: {file_url}")
    response = Transcription.async_call(
        model="qwen3-asr-flash-filetrans",
        file_urls=[file_url],
        api_key=dash_key,
        enable_words=True
    )

    if response.status_code != 200:
        raise SpeechRecognitionError(f"DashScope ASR submission failed ({response.status_code}): {getattr(response, 'message', 'Unknown error')}")

    task_id = getattr(response, "output", {}).get("task_id") if isinstance(getattr(response, "output", None), dict) else getattr(response, "task_id", None)
    if not task_id:
        raise SpeechRecognitionError("DashScope ASR did not return a valid task_id")

    # Poll for completion with exponential backoff (1s, 2s, 4s... max 30s)
    delay = 1.0
    max_delay = 30.0
    max_total_wait = 600.0
    total_waited = 0.0
    final_output = None

    while total_waited < max_total_wait:
        res = Transcription.fetch(task_id, api_key=dash_key)
        if res.status_code == 200 and res.output:
            status = res.output.get("task_status")
            if status == "SUCCEEDED":
                final_output = res.output
                break
            elif status in ("FAILED", "CANCELED"):
                raise SpeechRecognitionError(f"DashScope ASR task {task_id} failed: {res.output.get('message', 'Unknown error')}")
        time.sleep(delay)
        total_waited += delay
        delay = min(delay * 2.0, max_delay)

    if not final_output:
        raise SpeechRecognitionError(f"DashScope ASR task {task_id} timed out after {max_total_wait}s")

    # Parse response transcripts / transcription_url
    result_data = None
    if "transcription_url" in final_output:
        r = requests.get(final_output["transcription_url"], timeout=30)
        if r.status_code == 200:
            result_data = r.json()
    elif "results" in final_output and isinstance(final_output["results"], list) and final_output["results"]:
        first_res = final_output["results"][0]
        if "transcription_url" in first_res:
            r = requests.get(first_res["transcription_url"], timeout=30)
            if r.status_code == 200:
                result_data = r.json()
        elif "subtask_status" in first_res and first_res.get("subtask_status") == "SUCCEEDED":
            result_data = first_res
    if not result_data and "transcripts" in final_output:
        result_data = final_output

    if not result_data:
        raise SpeechRecognitionError("Failed to retrieve transcription payload from DashScope ASR response")

    segments: List[Dict[str, Any]] = []
    transcripts = result_data.get("transcripts", [result_data]) if isinstance(result_data, dict) else []

    for t in transcripts:
        sentences = t.get("sentences", [])
        for s in sentences:
            s_text = s.get("text", "").strip()
            s_start = float(s.get("begin_time", 0)) / 1000.0
            s_end = float(s.get("end_time", 0)) / 1000.0
            if s_end <= s_start:
                continue

            words_data = s.get("words", [])
            words: List[Dict[str, Any]] = []
            for w in words_data:
                w_text = (w.get("text") or w.get("word") or "").strip()
                if not w_text:
                    continue
                w_start = float(w.get("begin_time", s.get("begin_time", 0))) / 1000.0
                w_end = float(w.get("end_time", s.get("end_time", 0))) / 1000.0
                words.append({"word": w_text, "start": w_start, "end": w_end})

            if not words and s_text:
                words = _synthesize_words_from_sentence(s_text, s_start, s_end)

            segments.append({
                "start": s_start,
                "end": s_end,
                "text": s_text,
                "words": words
            })

    return segments


def transcribe_with_whisper(audio_path: Union[str, Path], model_size: str = "small", language: str = "auto") -> List[Dict[str, Any]]:
    """
    Transcribes audio using local faster-whisper runtime on CPU.
    """
    from backend.services import whisper_runtime
    if not whisper_runtime.is_installed():
        raise SpeechRecognitionError("Local Whisper runtime is not installed.")

    whisper_runtime.ensure_on_path()
    from faster_whisper import WhisperModel

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise SpeechRecognitionError(f"Audio file does not exist: {audio_path}")

    lang = None if language in ("auto", "None", None) else str(language).split("-")[0]
    models_dir = str(whisper_runtime.get_models_dir() / "hub")

    logger.info(f"[AutoClip] Local faster-whisper transcribing: model={model_size}, lang={lang or 'auto'}")
    model = WhisperModel(model_size, device="auto", compute_type="int8", download_root=models_dir)
    seg_iter, _info = model.transcribe(str(audio_path), language=lang, vad_filter=True, word_timestamps=True)
    segments_raw = list(seg_iter)
    if not segments_raw:
        seg_iter, _info = model.transcribe(str(audio_path), language=lang, vad_filter=False, word_timestamps=True)
        segments_raw = list(seg_iter)

    segments: List[Dict[str, Any]] = []
    for s in segments_raw:
        words = []
        if hasattr(s, "words") and s.words:
            for w in s.words:
                words.append({
                    "word": getattr(w, "word", ""),
                    "start": getattr(w, "start", s.start),
                    "end": getattr(w, "end", s.end)
                })
        if not words and s.text.strip():
            words = _synthesize_words_from_sentence(s.text.strip(), s.start, s.end)
        segments.append({
            "start": float(s.start),
            "end": float(s.end),
            "text": s.text.strip(),
            "words": words
        })

    return segments


def transcribe(audio_path: Union[str, Path], backend: Optional[str] = None, language: str = "auto") -> List[Dict[str, Any]]:
    """
    Multi-backend transcription with automatic fallback chain:
    1. Try DashScope qwen3-asr-flash-filetrans (if DASHSCOPE_API_KEY set or backend specified)
    2. If API fails or no key -> try OpenAI/Groq Whisper API (if key set)
    3. If no API keys -> fall back to local faster-whisper (CPU)
    """
    audio_path = Path(audio_path)
    if backend is None:
        backend = os.getenv("TRANSCRIPTION_BACKEND", "qwen3-asr-flash-filetrans")

    backend_str = str(backend).lower().strip()
    dash_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")

    def _finalize_segments(segs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            diarization = diarize_audio(audio_path)
            return assign_speakers_to_segments(segs, diarization)
        except Exception:
            for seg in segs:
                if "speaker" not in seg:
                    seg["speaker"] = "SPEAKER_00"
            return segs

    # 1. DashScope ASR
    if ("qwen" in backend_str or "asr" in backend_str or "dashscope" in backend_str or "aliyun" in backend_str) and dash_key:
        try:
            logger.info("[AutoClip] Attempting transcription with DashScope qwen3-asr-flash-filetrans...")
            segments = transcribe_with_qwen_asr(audio_path, api_key=dash_key, language=language)
            if segments:
                backend_used = "qwen3-asr-flash-filetrans"
                logger.info(f"[AutoClip] Transcription backend: {backend_used}")
                return _finalize_segments(segments)
        except Exception as e:
            logger.warning(f"[AutoClip] DashScope ASR transcription failed ({e}), attempting fallback...")

    # 2. OpenAI / Groq Whisper API (if key set)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and (backend_str in ("openai_api", "whisper_api", "auto") or "qwen" in backend_str):
        try:
            logger.info("[AutoClip] Attempting transcription with OpenAI Whisper API...")
            import openai
            client = openai.OpenAI(api_key=openai_key)
            with open(audio_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )
            words_list = getattr(transcription, "words", []) or []
            segments_list = getattr(transcription, "segments", []) or []
            parsed_segments = []
            if segments_list:
                for s in segments_list:
                    s_dict = s if isinstance(s, dict) else s.model_dump() if hasattr(s, "model_dump") else getattr(s, "__dict__", {})
                    parsed_segments.append({
                        "start": float(s_dict.get("start", 0)),
                        "end": float(s_dict.get("end", 0)),
                        "text": s_dict.get("text", "").strip(),
                        "words": [{"word": w.get("word") if isinstance(w, dict) else getattr(w, "word", ""),
                                   "start": float(w.get("start") if isinstance(w, dict) else getattr(w, "start", 0)),
                                   "end": float(w.get("end") if isinstance(w, dict) else getattr(w, "end", 0))}
                                  for w in (s_dict.get("words") or [])]
                    })
            if parsed_segments:
                backend_used = "openai_whisper_api"
                logger.info(f"[AutoClip] Transcription backend: {backend_used}")
                return _finalize_segments(parsed_segments)
        except Exception as e:
            logger.warning(f"[AutoClip] OpenAI Whisper API failed ({e}), attempting fallback to local faster-whisper...")

    # 3. Fallback to local faster-whisper (CPU)
    try:
        logger.info("[AutoClip] Using local faster-whisper on CPU...")
        model_size = os.getenv("SPEECH_RECOGNITION_MODEL", "small")
        segments = transcribe_with_whisper(audio_path, model_size=model_size, language=language)
        backend_used = "whisper_local"
        logger.info(f"[AutoClip] Transcription backend: {backend_used}")
        return _finalize_segments(segments)
    except Exception as e:
        logger.error(f"[AutoClip] Local Whisper transcription failed: {e}")
        raise SpeechRecognitionError(f"All transcription backends failed: {e}")


def diarize_audio(audio_path: Union[str, Path], num_speakers: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Run speaker diarization on audio. Returns list of:
    {"start": float, "end": float, "speaker": "SPEAKER_00"}
    
    Requires HuggingFace token for pyannote model download.
    Falls back to no-diarization (empty list) if unavailable.
    """
    try:
        from pyannote.audio import Pipeline
        
        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if not hf_token:
            logger.info("[AutoClip] HUGGINGFACE_TOKEN not set, skipping speaker diarization")
            return []
        
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        diarization = pipeline(str(audio_path), num_speakers=num_speakers)
        
        result = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            result.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": str(speaker)
            })
        return result
        
    except (ImportError, ModuleNotFoundError):
        logger.info("[AutoClip] pyannote.audio not installed, skipping speaker diarization")
        return []
    except Exception as e:
        logger.warning(f"[AutoClip] Diarization failed, proceeding without speaker labels: {e}")
        return []


def assign_speakers_to_segments(segments: List[Dict[str, Any]], diarization: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Label each transcription segment with the speaker who covers the most of its duration.
    Segments without a clear speaker assignment get label 'SPEAKER_00'.
    """
    for seg in segments:
        seg_start = float(seg.get('start', 0.0))
        seg_end = float(seg.get('end', 0.0))
        
        speaker_overlap: Dict[str, float] = {}
        if diarization:
            for d in diarization:
                d_start = float(d.get('start', 0.0))
                d_end = float(d.get('end', 0.0))
                overlap_start = max(seg_start, d_start)
                overlap_end = min(seg_end, d_end)
                overlap = max(0.0, overlap_end - overlap_start)
                if overlap > 0:
                    spk = str(d.get('speaker', 'SPEAKER_00'))
                    speaker_overlap[spk] = speaker_overlap.get(spk, 0.0) + overlap
        
        if speaker_overlap:
            seg['speaker'] = max(speaker_overlap, key=speaker_overlap.get)
        else:
            seg['speaker'] = 'SPEAKER_00'
    
    return segments


class SpeechRecognizer:
    """Speech recognizer supporting multiple speech recognition services"""
    
    def __init__(self, config: Optional[SpeechRecognitionConfig] = None):
        self.config = config or SpeechRecognitionConfig()
        self.available_methods = self._check_available_methods()
    
    def _check_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """Check available speech recognition methods"""
        methods = {}
        
        # Check local Whisper
        methods[SpeechRecognitionMethod.WHISPER_LOCAL] = self._check_whisper_availability()
        
        # Check OpenAI API
        methods[SpeechRecognitionMethod.OPENAI_API] = self._check_openai_availability()
        
        # Check Azure Speech Services
        methods[SpeechRecognitionMethod.AZURE_SPEECH] = self._check_azure_speech_availability()
        
        # Check Google Speech-to-Text
        methods[SpeechRecognitionMethod.GOOGLE_SPEECH] = self._check_google_speech_availability()
        
        # Check Alibaba Cloud ASR
        methods[SpeechRecognitionMethod.ALIYUN_SPEECH] = self._check_aliyun_speech_availability()
        
        # Check custom API
        methods[SpeechRecognitionMethod.CUSTOM_API] = self._check_custom_api_availability()
        
        return methods
    
    def _check_whisper_availability(self) -> bool:
        """Check if local Whisper (mlx) runtime is installed."""
        try:
            from backend.services import whisper_runtime
            return whisper_runtime.is_installed()
        except Exception:
            logger.warning("Local Whisper is not installed or unavailable")
            return False
    
    def _check_openai_availability(self) -> bool:
        """Check if OpenAI API is available"""
        api_key = os.getenv("OPENAI_API_KEY")
        return api_key is not None and len(api_key.strip()) > 0
    
    def _check_azure_speech_availability(self) -> bool:
        """Check if Azure Speech Services are available"""
        api_key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        return api_key is not None and region is not None
    
    def _check_google_speech_availability(self) -> bool:
        """Check if Google Speech-to-Text is available"""
        # Check Google Cloud credentials file
        cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_file and Path(cred_file).exists():
            return True
        
        # Check API key
        api_key = os.getenv("GOOGLE_SPEECH_API_KEY")
        return api_key is not None
    
    def _check_aliyun_speech_availability(self) -> bool:
        """Check if Alibaba Cloud ASR / DashScope is available"""
        try:
            access_key = (
                os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("API_DASHSCOPE_API_KEY")
                or os.getenv("ALIYUN_API_KEY")
                or (self.config.aliyun_access_key if hasattr(self, 'config') else None)
            )
            return bool(access_key and str(access_key).strip())
        except Exception:
            return False
    
    def _extract_audio_from_video(self, video_path: Path, output_dir: Path) -> Path:
        """
        Extract audio from video file
        
        Args:
            video_path: Path to video file
            output_dir: Output directory
            
        Returns:
            Extracted audio file path
        """
        try:
            # Check if ffmpeg is available
            ffmpeg_bin = get_ffmpeg_path()
            result = subprocess.run([ffmpeg_bin, '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise SpeechRecognitionError("ffmpeg is unavailable, please install ffmpeg")
            
            # Generate audio file path
            audio_filename = f"{video_path.stem}_audio.wav"
            audio_path = output_dir / audio_filename
            
            # If audio file already exists, return directly
            if audio_path.exists():
                logger.info(f"Audio file already exists: {audio_path}")
                return audio_path
            
            logger.info(f"Extracting audio from video: {video_path} -> {audio_path}")
            
            # Extract audio using ffmpeg
            cmd = [
                ffmpeg_bin,
                '-i', str(video_path),
                '-vn',  # Disable video stream
                '-acodec', 'pcm_s16le',  # PCM 16-bit encoding
                '-ar', '16000',  # 16kHz sampling rate
                '-ac', '1',  # Mono audio
                '-y',  # Overwrite output file
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise SpeechRecognitionError(f"Audio extraction failed: {result.stderr}")
            
            if not audio_path.exists():
                raise SpeechRecognitionError("Audio extraction failed, output file does not exist")
            
            logger.info(f"Audio extraction succeeded: {audio_path}")
            return audio_path
            
        except subprocess.TimeoutExpired:
            raise SpeechRecognitionError("Audio extraction timed out")
        except Exception as e:
            raise SpeechRecognitionError(f"Audio extraction failed: {e}")
    
    def generate_subtitle(self, video_path: Path, output_path: Optional[Path] = None, 
                         config: Optional[SpeechRecognitionConfig] = None) -> Path:
        """
        Generate subtitle file
        
        Args:
            video_path: Path to video file
            output_path: Path to output subtitle file
            config: Speech recognition configuration
            
        Returns:
            Generated subtitle file path
            
        Raises:
            SpeechRecognitionError: Speech recognition failed
        """
        if not video_path.exists():
            raise SpeechRecognitionError(f"Video file does not exist: {video_path}")
        
        # Use provided config or default config
        config = config or self.config
        
        # Determine output path
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}.{config.output_format}"
        
        # Select recognition service based on configured method, supports fallback
        try:
            if config.method == SpeechRecognitionMethod.WHISPER_LOCAL:
                return self._generate_subtitle_whisper_local(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.OPENAI_API:
                return self._generate_subtitle_openai_api(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.AZURE_SPEECH:
                return self._generate_subtitle_azure_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.GOOGLE_SPEECH:
                return self._generate_subtitle_google_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.ALIYUN_SPEECH:
                return self._generate_subtitle_aliyun_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.CUSTOM_API:
                return self._generate_subtitle_custom_api(video_path, output_path, config)
            else:
                raise SpeechRecognitionError(f"Unsupported speech recognition method: {config.method}")
        except SpeechRecognitionError as e:
            # If fallback enabled and current method is not fallback, attempt fallback
            if (config.enable_fallback and 
                config.method != config.fallback_method and 
                self.available_methods.get(config.fallback_method, False)):
                
                logger.warning(f"Primary method {config.method} failed: {e}")
                logger.info(f"Attempting fallback to {config.fallback_method}")
                
                # Create fallback config
                fallback_config = SpeechRecognitionConfig(
                    method=config.fallback_method,
                    language=config.language,
                    model=config.model,
                    timeout=config.timeout,
                    output_format=config.output_format,
                    enable_timestamps=config.enable_timestamps,
                    enable_punctuation=config.enable_punctuation,
                    enable_speaker_diarization=config.enable_speaker_diarization,
                    enable_fallback=False  # Avoid infinite fallback
                )
                
                return self.generate_subtitle(video_path, output_path, fallback_config)
            else:
                raise
    
    def _check_custom_api_availability(self) -> bool:
        """Check if custom API is available"""
        # Check if custom API is configured
        if self.config.custom_api_url and self.config.custom_api_key:
            try:
                # Simple health check
                response = requests.get(f"{self.config.custom_api_url}/health", timeout=5)
                return response.status_code == 200
            except Exception:
                return False
        return False
    
    @staticmethod
    def _save_companion_words(output_path: Path, segments: List[Dict[str, Any]]) -> None:
        """Save companion JSON files containing word-level timestamps alongside the SRT file."""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            words_json_str = json.dumps(segments, ensure_ascii=False, indent=2)
            (output_path.parent / f"{output_path.stem}_words.json").write_text(words_json_str, encoding="utf-8")
            (output_path.parent / "step2_words.json").write_text(words_json_str, encoding="utf-8")
            (output_path.parent / "words.json").write_text(words_json_str, encoding="utf-8")
            logger.info(f"[AutoClip] Saved companion word timestamps: {output_path.parent / 'step2_words.json'}")
        except Exception as w_err:
            logger.warning(f"Could not write companion words JSON file: {w_err}")

    @staticmethod
    def _format_srt_timestamp(seconds: float) -> str:
        if seconds is None or seconds < 0:
            seconds = 0.0
        ms = int(round(seconds * 1000.0))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _is_cjk_char(ch: str) -> bool:
        """Check if a character is CJK."""
        if not ch:
            return False
        cp = ord(ch[0])
        return (
            (0x4E00 <= cp <= 0x9FFF) or   # CJK Unified Ideographs
            (0x3400 <= cp <= 0x4DBF) or   # Extension A
            (0x20000 <= cp <= 0x2A6DF) or # Extension B
            (0xF900 <= cp <= 0xFAFF) or   # CJK Compatibility
            (0x3040 <= cp <= 0x309F) or   # Hiragana
            (0x30A0 <= cp <= 0x30FF) or   # Katakana
            (0xAC00 <= cp <= 0xD7AF)      # Hangul
        )

    @classmethod
    def _join_word_tokens(cls, tokens: List[Dict[str, Any]]) -> str:
        """Join word tokens naturally: spaces between Latin words, no spaces between CJK."""
        if not tokens:
            return ""
        texts = [t['text'] for t in tokens if t.get('text')]
        if not texts:
            return ""
        result = [texts[0]]
        for i in range(1, len(texts)):
            prev = texts[i - 1]
            curr = texts[i]
            prev_is_cjk = cls._is_cjk_char(prev[-1])
            curr_is_cjk = cls._is_cjk_char(curr[0])
            is_punct = bool(re.match(r'^[.,!?:;，。！？；、“”‘’（）\(\)\[\]\<\>]+$', curr))
            prev_is_open_punct = bool(re.match(r'^[“‘（\(\[\<]+$', prev))

            if is_punct or prev_is_open_punct:
                result.append(curr)
            elif prev_is_cjk and curr_is_cjk:
                result.append(curr)
            else:
                result.append(" " + curr)
        return "".join(result).strip()

    @classmethod
    def _words_to_tight_srt(cls, segments: List[Any], max_words_per_line: int = 4, max_cjk_chars_per_line: int = 10, max_duration_sec: float = 3.0) -> str:
        """
        Converts word-level Whisper segments into tight, millisecond-accurate SRT cues.
        Eliminates silence stretching and ensures 100% audio-video subtitle synchronization.
        Handles both Latin/English word spacing and CJK continuous character rendering.
        """
        cues = []
        cue_index = 1
        
        for seg in segments:
            words = getattr(seg, 'words', None) or (seg.get('words') if isinstance(seg, dict) else None)
            
            if not words:
                text = (getattr(seg, 'text', None) or (seg.get('text') if isinstance(seg, dict) else "")).strip()
                if not text:
                    continue
                start = getattr(seg, 'start', 0.0) if hasattr(seg, 'start') else seg.get('start', 0.0)
                end = getattr(seg, 'end', 0.0) if hasattr(seg, 'end') else seg.get('end', 0.0)
                cues.append(f"{cue_index}\n{cls._format_srt_timestamp(start)} --> {cls._format_srt_timestamp(end)}\n{text}\n")
                cue_index += 1
                continue
            
            current_group: List[Dict[str, Any]] = []
            for w in words:
                w_text = (getattr(w, 'word', None) or (w.get('word') if isinstance(w, dict) else "")).strip()
                w_start = getattr(w, 'start', 0.0) if hasattr(w, 'start') else w.get('start', 0.0)
                w_end = getattr(w, 'end', 0.0) if hasattr(w, 'end') else w.get('end', 0.0)
                
                if not w_text:
                    continue
                
                is_cjk = any(cls._is_cjk_char(ch) for ch in w_text)
                
                should_flush = False
                if current_group:
                    prev_end = current_group[-1]['end']
                    group_duration = w_end - current_group[0]['start']
                    group_has_cjk = any(any(cls._is_cjk_char(ch) for ch in item['text']) for item in current_group)
                    
                    if group_has_cjk:
                        group_char_count = sum(len(item['text']) for item in current_group)
                        limit_reached = group_char_count >= max_cjk_chars_per_line
                    else:
                        limit_reached = len(current_group) >= max_words_per_line
                    
                    if (w_start - prev_end > 0.45) or limit_reached or (group_duration >= max_duration_sec):
                        should_flush = True
                
                if should_flush and current_group:
                    line_start = current_group[0]['start']
                    line_end = current_group[-1]['end']
                    line_text = cls._join_word_tokens(current_group)
                    if line_text:
                        cues.append(f"{cue_index}\n{cls._format_srt_timestamp(line_start)} --> {cls._format_srt_timestamp(line_end)}\n{line_text}\n")
                        cue_index += 1
                    current_group = []
                
                current_group.append({'text': w_text, 'start': w_start, 'end': w_end})
                
                if w_text.endswith(('.', '?', '!', '。', '？', '！', '，', ',', '；', ';', '、')):
                    line_start = current_group[0]['start']
                    line_end = current_group[-1]['end']
                    line_text = cls._join_word_tokens(current_group)
                    if line_text:
                        cues.append(f"{cue_index}\n{cls._format_srt_timestamp(line_start)} --> {cls._format_srt_timestamp(line_end)}\n{line_text}\n")
                        cue_index += 1
                    current_group = []
            
            if current_group:
                line_start = current_group[0]['start']
                line_end = current_group[-1]['end']
                line_text = cls._join_word_tokens(current_group)
                if line_text:
                    cues.append(f"{cue_index}\n{cls._format_srt_timestamp(line_start)} --> {cls._format_srt_timestamp(line_end)}\n{line_text}\n")
                    cue_index += 1

        return "\n".join(cues) + "\n" if cues else ""

    @classmethod
    def _segments_to_srt(cls, segments: List[Dict[str, Any]]) -> str:
        lines = []
        for i, seg in enumerate(segments, start=1):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            start = cls._format_srt_timestamp(seg.get("start", 0.0))
            end = cls._format_srt_timestamp(seg.get("end", 0.0))
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines) + "\n"

    def _generate_subtitle_whisper_local(self, video_path: Path, output_path: Path,
                                       config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using local faster-whisper runtime."""
        from backend.services import whisper_runtime

        if not whisper_runtime.is_installed():
            raise SpeechRecognitionError(
                "Local Whisper runtime is not installed. Please go to Settings -> Speech Recognition to install Whisper, "
                "and download a model before trying again."
            )

        if not video_path.exists():
            raise SpeechRecognitionError(f"Video file does not exist: {video_path}")
        if video_path.stat().st_size == 0:
            raise SpeechRecognitionError(f"Video file is empty: {video_path}")
        if output_path.exists():
            logger.info(f"Subtitle file already exists, skipping Whisper: {output_path}")
            return output_path

        try:
            whisper_runtime.ensure_on_path()  # Make faster_whisper importable
            from faster_whisper import WhisperModel  # Lazy import from runtime directory

            language = None if config.language == LanguageCode.AUTO else str(config.language).split("-")[0]
            models_dir = str(whisper_runtime.get_models_dir() / "hub")
            logger.info(f"Generating accurate word-level subtitles with faster-whisper: model={config.model} lang={language or 'auto'}")

            # device=auto: word-level timestamps enabled (word_timestamps=True)
            model = WhisperModel(
                config.model, device="auto", compute_type="int8", download_root=models_dir,
            )
            seg_iter, _info = model.transcribe(str(video_path), language=language, vad_filter=True, word_timestamps=True)
            segments = list(seg_iter)
            
            # If VAD filtered everything, retry without VAD
            if not segments:
                logger.info("VAD filtered all segments, retrying with vad_filter=False...")
                seg_iter, _info = model.transcribe(str(video_path), language=language, vad_filter=False, word_timestamps=True)
                segments = list(seg_iter)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            if segments:
                tight_srt = self._words_to_tight_srt(segments)
                if not tight_srt.strip():
                    tight_srt = self._segments_to_srt([{"start": s.start, "end": s.end, "text": s.text} for s in segments])
                output_path.write_text(tight_srt, encoding="utf-8")
                logger.info(f"Local faster-whisper word-level subtitles generated successfully: {output_path} ({len(segments)} segments)")

                # Extract word-level segments and run speaker assignment
                segments_data = []
                for s in segments:
                    words = []
                    if hasattr(s, "words") and s.words:
                        for w in s.words:
                            words.append({
                                "word": getattr(w, "word", "").strip(),
                                "start": float(getattr(w, "start", s.start)),
                                "end": float(getattr(w, "end", s.end))
                            })
                    if not words and hasattr(s, "text") and s.text.strip():
                        words = _synthesize_words_from_sentence(s.text.strip(), float(s.start), float(s.end))
                    segments_data.append({
                        "start": float(s.start),
                        "end": float(s.end),
                        "text": s.text.strip(),
                        "words": words
                    })

                try:
                    diarization = diarize_audio(video_path)
                    segments_data = assign_speakers_to_segments(segments_data, diarization)
                except Exception as d_err:
                    logger.debug(f"Diarization skipped: {d_err}")
                    for seg in segments_data:
                        seg["speaker"] = "SPEAKER_00"

                self._save_companion_words(output_path, segments_data)
            else:
                # No speech detected: write empty file with marker comment so validator knows no speech was found
                output_path.write_text("# No speech detected by Whisper\n", encoding="utf-8")
                logger.info(f"No speech detected, generated empty marker subtitle: {output_path}")

            return output_path

        except SpeechRecognitionError:
            raise
        except ModuleNotFoundError as e:
            raise SpeechRecognitionError(
                f"Whisper runtime missing dependencies ({e}). Please reinstall Whisper under Settings -> Speech Recognition."
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Local faster-whisper subtitle generation failed: {e}", exc_info=True)
            raise SpeechRecognitionError(f"Local Whisper subtitle generation failed: {e}")
    
    def _generate_subtitle_openai_api(self, video_path: Path, output_path: Path, 
                                    config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using OpenAI API"""
        if not self.available_methods[SpeechRecognitionMethod.OPENAI_API]:
            raise SpeechRecognitionError("OpenAI API is unavailable, please set OPENAI_API_KEY environment variable")
        
        try:
            logger.info(f"Starting subtitle generation with OpenAI API: {video_path}")
            
            # OpenAI API call implementation
            # Raise exception until dependency installed
            raise SpeechRecognitionError("OpenAI API not implemented yet, please use local Whisper")
            
        except Exception as e:
            error_msg = f"Error generating subtitles with OpenAI API: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_azure_speech(self, video_path: Path, output_path: Path, 
                                      config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using Azure Speech Services"""
        if not self.available_methods[SpeechRecognitionMethod.AZURE_SPEECH]:
            raise SpeechRecognitionError("Azure Speech Services unavailable, please set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables")
        
        try:
            logger.info(f"Starting subtitle generation with Azure Speech Services: {video_path}")
            
            # Azure Speech Services call implementation
            raise SpeechRecognitionError("Azure Speech Services not implemented yet, please use local Whisper")
            
        except Exception as e:
            error_msg = f"Error generating subtitles with Azure Speech Services: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_google_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using Google Speech-to-Text"""
        if not self.available_methods[SpeechRecognitionMethod.GOOGLE_SPEECH]:
            raise SpeechRecognitionError("Google Speech-to-Text unavailable, please set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_SPEECH_API_KEY environment variables")
        
        try:
            logger.info(f"Starting subtitle generation with Google Speech-to-Text: {video_path}")
            
            # Google Speech-to-Text call implementation
            raise SpeechRecognitionError("Google Speech-to-Text not implemented yet, please use local Whisper")
            
        except Exception as e:
            error_msg = f"Error generating subtitles with Google Speech-to-Text: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_aliyun_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using Alibaba Cloud DashScope ASR (qwen3-asr-flash-filetrans)"""
        if not self.available_methods[SpeechRecognitionMethod.ALIYUN_SPEECH]:
            if config.enable_fallback:
                logger.warning("Alibaba Cloud ASR unavailable, falling back to local Whisper")
                return self._generate_subtitle_whisper_local(video_path, output_path, config)
            raise SpeechRecognitionError("Alibaba Cloud ASR unavailable, please configure DASHSCOPE_API_KEY")
        
        try:
            logger.info(f"Starting subtitle generation with Alibaba Cloud DashScope ASR: {video_path}")
            if not video_path.exists():
                raise SpeechRecognitionError(f"Video file does not exist: {video_path}")
            
            # Extract audio file
            audio_path = self._extract_audio_from_video(video_path, output_path.parent)
            dash_key = config.aliyun_access_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
            
            segments = transcribe_with_qwen_asr(audio_path, api_key=dash_key, language=config.language.value)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if segments:
                tight_srt = self._words_to_tight_srt(segments)
                if not tight_srt.strip():
                    tight_srt = self._segments_to_srt([{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segments])
                output_path.write_text(tight_srt, encoding="utf-8")
                logger.info(f"DashScope ASR word-level subtitles generated successfully: {output_path} ({len(segments)} segments)")

                try:
                    diarization = diarize_audio(video_path)
                    segments = assign_speakers_to_segments(segments, diarization)
                except Exception as d_err:
                    logger.debug(f"Diarization skipped: {d_err}")
                    for seg in segments:
                        seg["speaker"] = "SPEAKER_00"

                self._save_companion_words(output_path, segments)
            else:
                output_path.write_text("# No speech detected by DashScope ASR\n", encoding="utf-8")
                logger.info(f"No speech detected, generated empty marker subtitle: {output_path}")

            return output_path

        except Exception as e:
            logger.warning(f"DashScope ASR subtitle generation failed: {e}")
            if config.enable_fallback:
                logger.info("Falling back to local Whisper...")
                return self._generate_subtitle_whisper_local(video_path, output_path, config)
            raise SpeechRecognitionError(f"Alibaba Cloud ASR subtitle generation failed: {e}")
    
    def _generate_subtitle_custom_api(self, video_path: Path, output_path: Path, 
                                     config: SpeechRecognitionConfig) -> Path:
        """Generate subtitles using custom API"""
        if not config.custom_api_url or not config.custom_api_key:
            raise SpeechRecognitionError(
                "Custom API configuration incomplete, please configure custom_api_url and custom_api_key"
            )
        
        try:
            logger.info(f"Starting subtitle generation with custom API: {video_path}")
            
            # Check if video file exists
            if not video_path.exists():
                raise SpeechRecognitionError(f"Video file does not exist: {video_path}")
            
            # Extract audio file
            audio_path = self._extract_audio_from_video(video_path, output_path.parent)
            
            # Prepare API request
            headers = {
                'Authorization': f'Bearer {config.custom_api_key}',
                'Content-Type': 'audio/wav'
            }
            
            # Send audio file to API
            with open(audio_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                data = {
                    'language': config.language.value if config.language != LanguageCode.AUTO else 'auto',
                    'format': config.output_format
                }
                
                response = requests.post(
                    f"{config.custom_api_url}/transcribe",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=config.timeout if config.timeout > 0 else 300
                )
            
            if response.status_code == 200:
                # Save subtitle file
                subtitle_content = response.text
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(subtitle_content)
                
                logger.info(f"Custom API subtitles generated successfully: {output_path}")
                return output_path
            else:
                raise SpeechRecognitionError(f"Custom API call failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            error_msg = f"Error generating subtitles with custom API: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def get_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """Get available speech recognition methods"""
        return self.available_methods.copy()
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """Get supported languages list"""
        return list(LanguageCode)
    
    def get_whisper_models(self) -> List[str]:
        """Get available Whisper model list"""
        return ["tiny", "base", "small", "medium", "large"]


def generate_subtitle_for_video(video_path: Path, output_path: Optional[Path] = None, 
                               method: str = "auto", language: str = "auto", 
                               model: str = "small", enable_fallback: bool = True,
                               **kwargs) -> Path:
    """
    Convenience function to generate subtitle file for video
    
    Args:
        video_path: Path to video file
        output_path: Path to output subtitle file
        method: Generation method ("auto", "whisper_local", "openai_api", "azure_speech", "google_speech", "aliyun_speech", "custom_api")
        language: Language code
        model: Whisper model size (only applicable to whisper_local)
        enable_fallback: Whether fallback mechanism is enabled
        **kwargs: Additional parameters passed to SpeechRecognitionConfig
                  (e.g., enable_timestamps, enable_punctuation, enable_speaker_diarization, timeout, api_key)
        
    Returns:
        Generated subtitle file path
        
    Raises:
        SpeechRecognitionError: Speech recognition failed
    """
    # Check TRANSCRIPTION_BACKEND configuration flag
    transcription_backend = os.getenv("TRANSCRIPTION_BACKEND", "qwen3-asr-flash-filetrans").lower().strip()
    is_qwen_backend = any(k in transcription_backend for k in ("qwen", "asr", "dashscope", "aliyun"))
    default_method = SpeechRecognitionMethod.ALIYUN_SPEECH if is_qwen_backend else SpeechRecognitionMethod.WHISPER_LOCAL

    # Create configuration
    config = SpeechRecognitionConfig(
        method=SpeechRecognitionMethod(method) if method != "auto" else default_method,
        language=LanguageCode(language),
        model=model,
        enable_fallback=enable_fallback,
        fallback_method=SpeechRecognitionMethod.WHISPER_LOCAL
    )
    
    if "enable_timestamps" in kwargs and kwargs["enable_timestamps"] is not None:
        config.enable_timestamps = bool(kwargs["enable_timestamps"])
    if "enable_punctuation" in kwargs and kwargs["enable_punctuation"] is not None:
        config.enable_punctuation = bool(kwargs["enable_punctuation"])
    if "enable_speaker_diarization" in kwargs and kwargs["enable_speaker_diarization"] is not None:
        config.enable_speaker_diarization = bool(kwargs["enable_speaker_diarization"])
    if "timeout" in kwargs and kwargs["timeout"] is not None:
        config.timeout = int(kwargs["timeout"])
    if "output_format" in kwargs and kwargs["output_format"] is not None:
        config.output_format = str(kwargs["output_format"])
    if "api_key" in kwargs and kwargs["api_key"]:
        m_str = str(config.method).lower()
        if "openai" in m_str:
            config.openai_api_key = kwargs["api_key"]
        elif "azure" in m_str:
            config.azure_speech_key = kwargs["api_key"]
        elif "aliyun" in m_str:
            config.aliyun_access_key = kwargs["api_key"]
        elif "custom" in m_str:
            config.custom_api_key = kwargs["api_key"]
            
    for k, v in kwargs.items():
        if hasattr(config, k) and v is not None:
            setattr(config, k, v)
    
    recognizer = SpeechRecognizer()
    
    if method == "auto":
        # Auto-select best method
        available_methods = recognizer.get_available_methods()
        
        if is_qwen_backend and available_methods.get(SpeechRecognitionMethod.ALIYUN_SPEECH, False):
            config.method = SpeechRecognitionMethod.ALIYUN_SPEECH
        else:
            # Fallback priority order
            priority_methods = [
                SpeechRecognitionMethod.ALIYUN_SPEECH if is_qwen_backend else SpeechRecognitionMethod.WHISPER_LOCAL,
                SpeechRecognitionMethod.WHISPER_LOCAL if is_qwen_backend else SpeechRecognitionMethod.ALIYUN_SPEECH,
                SpeechRecognitionMethod.OPENAI_API,
                SpeechRecognitionMethod.AZURE_SPEECH,
                SpeechRecognitionMethod.GOOGLE_SPEECH,
                SpeechRecognitionMethod.CUSTOM_API
            ]
            
            for priority_method in priority_methods:
                if available_methods.get(priority_method, False):
                    config.method = priority_method
                    break
            else:
                raise SpeechRecognitionError("No speech recognition service available, please install Whisper or configure an API key")
    
    return recognizer.generate_subtitle(video_path, output_path, config)


def get_available_speech_recognition_methods() -> Dict[str, bool]:
    """
    Get available speech recognition methods
    
    Returns:
        Dict of available methods
    """
    recognizer = SpeechRecognizer()
    available_methods = recognizer.get_available_methods()
    
    return {
        method.value: available 
        for method, available in available_methods.items()
    }


def get_supported_languages() -> List[str]:
    """
    Get list of supported languages
    
    Returns:
        List of supported language codes
    """
    return [lang.value for lang in LanguageCode]


def get_whisper_models() -> List[str]:
    """
    Get list of available Whisper models
    
    Returns:
        List of Whisper models
    """
    return ["tiny", "base", "small", "medium", "large"]


# Compatibility aliases for campaign mode
transcribe_audio = transcribe


def transcribe_video_to_srt(video_path: Union[str, Path], srt_output: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Transcribes video and optionally saves to SRT file, returning segments."""
    segments = transcribe(video_path)
    if srt_output and segments:
        srt_path = Path(srt_output)
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_content = SpeechRecognizer._segments_to_srt(segments)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
    return segments


