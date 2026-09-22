"""
Configuration file - Manages API keys, file paths, and runtime settings.
Supports unified configuration management and backward compatibility.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from pydantic import BaseModel, validator
from enum import Enum

from . import path_utils
from .duration_config import duration_config

# Video category enumeration
class VideoCategory(str, Enum):
    # Conversation format
    PODCAST = "podcast"
    PODCAST_HIGHLIGHT = "podcast_highlight"
    INTERVIEW = "interview"
    LIVESTREAM = "livestream"
    
    # Topic niches
    BUSINESS_INSIGHT = "business_insight"
    BUSINESS = "business"
    KNOWLEDGE = "knowledge"
    TECH_TAKE = "tech_take"
    AI_MOMENT = "ai_moment"
    
    # Gaming
    GAMING_HIGHLIGHT = "gaming_highlight"
    GAMING_COMMENTARY = "gaming_commentary"
    
    # Entertainment / personality
    HOT_TAKE = "hot_take"
    FUNNY_MOMENT = "funny_moment"
    VLOG = "vlog"
    STORYTELLING = "storytelling"
    
    # Fallback
    DEFAULT = "default"

# Video Categories Configuration
VIDEO_CATEGORIES_CONFIG = {
    VideoCategory.PODCAST: {
        "name": "Podcast",
        "description": "Long-form multi-speaker conversation (2–6 min)",
        "icon": "🎙️",
        "color": "#1890ff"
    },
    VideoCategory.PODCAST_HIGHLIGHT: {
        "name": "Podcast Highlight",
        "description": "Single quotable moment from podcast (30s–2 min)",
        "icon": "⚡",
        "color": "#52c41a"
    },
    VideoCategory.INTERVIEW: {
        "name": "Interview",
        "description": "Structured guest Q&A (1–4 min)",
        "icon": "🎤",
        "color": "#722ed1"
    },
    VideoCategory.LIVESTREAM: {
        "name": "Livestream",
        "description": "Livestream highlights, unscripted rants, chat interactions (30s–3 min)",
        "icon": "🔴",
        "color": "#ff4d4f"
    },
    VideoCategory.BUSINESS_INSIGHT: {
        "name": "Business Insight",
        "description": "Business, entrepreneurship, finance, career (45s–4 min)",
        "icon": "💼",
        "color": "#faad14"
    },
    VideoCategory.BUSINESS: {
        "name": "Business & Finance",
        "description": "Business, startup growth, market breakdown (45s–4 min)",
        "icon": "📈",
        "color": "#faad14"
    },
    VideoCategory.KNOWLEDGE: {
        "name": "Knowledge & Psychology",
        "description": "Educational insights, mental models, explanations (45s–4 min)",
        "icon": "🧠",
        "color": "#722ed1"
    },
    VideoCategory.TECH_TAKE: {
        "name": "Tech Take",
        "description": "Tech product review, opinion, news analysis (45s–3 min)",
        "icon": "💻",
        "color": "#13c2c2"
    },
    VideoCategory.AI_MOMENT: {
        "name": "AI Moment",
        "description": "AI tools, news, implications, demonstrations (30s–4 min)",
        "icon": "🤖",
        "color": "#2f54eb"
    },
    VideoCategory.GAMING_HIGHLIGHT: {
        "name": "Gaming Highlight",
        "description": "Gaming moments, reactions, commentary (15s–90s)",
        "icon": "🎮",
        "color": "#f5222d"
    },
    VideoCategory.GAMING_COMMENTARY: {
        "name": "Gaming Commentary",
        "description": "Gaming opinions, news, analysis, reviews (1–4 min)",
        "icon": "🕹️",
        "color": "#fa541c"
    },
    VideoCategory.HOT_TAKE: {
        "name": "Hot Take",
        "description": "Strong opinion, controversial or contrarian take (30s–90s)",
        "icon": "🔥",
        "color": "#eb2f96"
    },
    VideoCategory.FUNNY_MOMENT: {
        "name": "Funny Moment",
        "description": "Comedic moments from any content type (15s–60s)",
        "icon": "😂",
        "color": "#fa8c16"
    },
    VideoCategory.VLOG: {
        "name": "Vlog",
        "description": "Personal narrative, day-in-life, behind-the-scenes (30s–3 min)",
        "icon": "📹",
        "color": "#a0d911"
    },
    VideoCategory.STORYTELLING: {
        "name": "Storytelling",
        "description": "Personal story with complete arc (1–5 min)",
        "icon": "📖",
        "color": "#13c2c2"
    },
    VideoCategory.DEFAULT: {
        "name": "General",
        "description": "General fallback",
        "icon": "🎬",
        "color": "#4facfe"
    }
}

# Project root directory
PROJECT_ROOT = path_utils.get_project_root()

# Input file paths
INPUT_DIR = PROJECT_ROOT / "input"
INPUT_VIDEO = INPUT_DIR / "input.mp4"
INPUT_SRT = INPUT_DIR / "input.srt"
INPUT_TXT = INPUT_DIR / "input.txt"

# Output directories
DATA_DIR = path_utils.get_data_directory()
OUTPUT_DIR = path_utils.get_output_directory()
CLIPS_DIR = OUTPUT_DIR / "clips"
COLLECTIONS_DIR = OUTPUT_DIR / "collections"
METADATA_DIR = OUTPUT_DIR / "metadata"

# Prompt file paths
PROMPT_DIR = Path(__file__).parent.parent / "prompt"
PROMPT_FILES = {
    "outline": PROMPT_DIR / "outline.txt",
    "timeline": PROMPT_DIR / "timeline.txt", 
    "recommendation": PROMPT_DIR / "recommendation.txt",
    "title": PROMPT_DIR / "title.txt",
    "clustering": PROMPT_DIR / "clustering.txt",
    "collection_title": PROMPT_DIR / "collection_title.txt"
}

# API configuration
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_NAME", os.getenv("API_MODEL_NAME", "qwen-plus"))  # Default to active quota model

# Speech recognition configuration
SPEECH_RECOGNITION_METHOD = os.getenv("SPEECH_RECOGNITION_METHOD", "auto")
SPEECH_RECOGNITION_LANGUAGE = os.getenv("SPEECH_RECOGNITION_LANGUAGE", "en")
SPEECH_RECOGNITION_MODEL = os.getenv("SPEECH_RECOGNITION_MODEL", "small")
SPEECH_RECOGNITION_TIMEOUT = int(os.getenv("SPEECH_RECOGNITION_TIMEOUT", "1000"))
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "qwen3-asr-flash-filetrans")  # 'qwen3-asr-flash-filetrans' or 'whisper'
HOOK_BANNER_STYLE = os.getenv("HOOK_BANNER_STYLE", "static")  # 'static' = stays on screen | 'fade' = fade in/out

# Parallel processing & hardware offloading settings
LLM_MAX_PARALLEL_CHUNKS = int(os.getenv("LLM_MAX_PARALLEL_CHUNKS", "4"))
FFMPEG_MAX_PARALLEL_CUTS = int(os.getenv("FFMPEG_MAX_PARALLEL_CUTS", "2"))  # AMD Vega 7 shares system RAM (capped at 2)
USE_HW_ACCEL = os.getenv("USE_HW_ACCEL", "auto")  # "auto" | "vaapi" | "none"
HW_ACCEL_DEVICE = os.getenv("HW_ACCEL_DEVICE", "/dev/dri/renderD128")

# Processing parameters
CHUNK_SIZE = 5000  # Text chunk size
MIN_SCORE_THRESHOLD = 0.7  # Minimum virality score threshold (default)
MAX_CLIPS_PER_COLLECTION = 5  # Maximum clips per collection

# Borderline scoring thresholds for multi-model evaluation
ENSEMBLE_BORDERLINE_MIN = float(os.getenv("ENSEMBLE_BORDERLINE_MIN", "0.55"))  # Below this: clear reject
ENSEMBLE_BORDERLINE_MAX = float(os.getenv("ENSEMBLE_BORDERLINE_MAX", "0.82"))  # Above this: clear winner

# Calibrated virality score thresholds by video category
MIN_SCORE_BY_CATEGORY = {
    VideoCategory.DEFAULT: 0.70,
    VideoCategory.PODCAST: 0.70,
    VideoCategory.PODCAST_HIGHLIGHT: 0.70,
    VideoCategory.INTERVIEW: 0.70,
    VideoCategory.LIVESTREAM: 0.70,
    VideoCategory.BUSINESS_INSIGHT: 0.72,
    VideoCategory.TECH_TAKE: 0.70,
    VideoCategory.AI_MOMENT: 0.70,
    VideoCategory.GAMING_HIGHLIGHT: 0.68,
    VideoCategory.GAMING_COMMENTARY: 0.70,
    VideoCategory.HOT_TAKE: 0.70,
    VideoCategory.FUNNY_MOMENT: 0.68,
    VideoCategory.VLOG: 0.68,
    VideoCategory.STORYTELLING: 0.72,
}

# Default clip duration bounds (in seconds)
MIN_CLIP_DURATION = 15.0  # Allow punchy short moments
MAX_CLIP_DURATION = 480.0  # Allow long-form clips up to 8 minutes (configurable up to 10 min)

# Configurable duration limits by video category (min_duration_sec, max_duration_sec)
CLIP_DURATION_LIMITS_BY_CATEGORY = {
    VideoCategory.DEFAULT: (45.0, 180.0),
    VideoCategory.PODCAST: (120.0, 360.0),
    VideoCategory.PODCAST_HIGHLIGHT: (30.0, 120.0),
    VideoCategory.INTERVIEW: (60.0, 240.0),
    VideoCategory.LIVESTREAM: (30.0, 180.0),
    VideoCategory.BUSINESS_INSIGHT: (45.0, 240.0),
    VideoCategory.TECH_TAKE: (45.0, 180.0),
    VideoCategory.AI_MOMENT: (30.0, 240.0),
    VideoCategory.GAMING_HIGHLIGHT: (15.0, 90.0),
    VideoCategory.GAMING_COMMENTARY: (60.0, 240.0),
    VideoCategory.HOT_TAKE: (30.0, 90.0),
    VideoCategory.FUNNY_MOMENT: (15.0, 60.0),
    VideoCategory.VLOG: (30.0, 180.0),
    VideoCategory.STORYTELLING: (60.0, 300.0),
}


def get_clip_duration_limits(category: Any = "default") -> Tuple[float, float]:
    """
    Get (min_duration_seconds, max_duration_seconds) for a category from duration_config.
    Allows clips from 30s to 8 minutes based on content category.
    """
    cat_str = category.value if isinstance(category, VideoCategory) else str(category)
    return duration_config.get_duration_range(cat_str)

# Clip Duration Presets (for viral shorts & creator rewards)
DURATION_PRESETS = {
    "tiktok_crp": {
        "name": "TikTok Creator Rewards (60s-90s)",
        "min_duration": 60.0,
        "max_duration": 95.0,
        "target_duration": 75.0,
        "description": "Optimized for TikTok Creator Rewards Program (60s+ payout threshold)"
    },
    "shorts_reels": {
        "name": "Shorts & Reels (30s-60s)",
        "min_duration": 30.0,
        "max_duration": 60.0,
        "target_duration": 45.0,
        "description": "Ultra-punchy viral shorts for YouTube Shorts and Instagram Reels"
    },
    "deep_dive": {
        "name": "Topic Highlights (2m-5m)",
        "min_duration": 120.0,
        "max_duration": 300.0,
        "target_duration": 180.0,
        "description": "Extended highlights and complete thought breakdowns"
    }
}

# Ensure output directories exist
for dir_path in [CLIPS_DIR, COLLECTIONS_DIR, METADATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Configuration management system
class Settings(BaseModel):
    """System settings"""
    dashscope_api_key: Optional[str] = ""
    model_name: str = os.getenv("MODEL_NAME", os.getenv("API_MODEL_NAME", "qwen-plus"))
    chunk_size: int = 5000
    min_score_threshold: float = 0.7
    max_clips_per_collection: int = 5
    max_retries: int = 3
    timeout_seconds: int = 30
    min_topic_duration_minutes: int = 2
    max_topic_duration_minutes: int = 12
    target_topic_duration_minutes: int = 5
    min_topics_per_chunk: int = 3
    max_topics_per_chunk: int = 8
    speech_recognition_method: str = "whisper_local"
    speech_recognition_language: str = "en"
    speech_recognition_model: str = "small"
    speech_recognition_timeout: int = 1000
    
    @validator('min_score_threshold')
    def validate_score_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Score threshold must be between 0 and 1')
        return v
    
    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0:
            raise ValueError('Chunk size must be greater than 0')
        return v

@dataclass
class APIConfig:
    """API configuration"""
    model_name: str = os.getenv("MODEL_NAME", os.getenv("API_MODEL_NAME", "qwen-plus"))
    api_key: Optional[str] = None
    base_url: str = "https://dashscope.aliyuncs.com"
    max_tokens: int = 4096

@dataclass
class ProcessingConfig:
    """Processing configuration"""
    chunk_size: int = 5000
    min_score_threshold: float = 0.7
    max_clips_per_collection: int = 5
    max_retries: int = 3
    timeout_seconds: int = 30

@dataclass
class PathConfig:
    """Paths configuration"""
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    data_dir: Path = field(default_factory=path_utils.get_data_directory)
    uploads_dir: Path = field(default_factory=path_utils.get_uploads_directory)
    output_dir: Path = field(default_factory=path_utils.get_output_directory)
    prompt_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "prompt")
    temp_dir: Path = field(default_factory=path_utils.get_temp_directory)

class ConfigManager:
    """Configuration manager"""
    
    def __init__(self):
        self.settings = Settings()
        self._load_settings()
        self._setup_prompt_files()
    
    def _load_settings(self):
        """Load settings from environment and file"""
        if os.getenv("DASHSCOPE_API_KEY"):
            self.settings.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        
        config_file = path_utils.get_settings_file_path()
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    for key, value in config_data.items():
                        if hasattr(self.settings, key):
                            setattr(self.settings, key, value)
            except Exception as e:
                print(f"Failed to load settings file: {e}")
    
    def _setup_prompt_files(self):
        """Setup default prompt files if missing"""
        self.prompt_files = PROMPT_FILES.copy()
        PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        
        default_prompts = {
            "outline.txt": "Analyze the following video content and extract the main viral topics and structure:\n\n{content}",
            "timeline.txt": "Locate specific start and end timestamps for the following topics:\n\n{content}",
            "recommendation.txt": "Evaluate the quality and virality potential of the following content:\n\n{content}",
            "title.txt": "Generate engaging, high-converting titles for the following content:\n\n{content}",
            "clustering.txt": "Group the following topics into thematic collections:\n\n{content}"
        }
        
        for filename, content in default_prompts.items():
            file_path = PROMPT_DIR / filename
            if not file_path.exists():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                except Exception as e:
                    print(f"Failed to create prompt file {filename}: {e}")
    
    def get_api_config(self) -> APIConfig:
        """Get API configuration"""
        return APIConfig(
            model_name=self.settings.model_name,
            api_key=self.settings.dashscope_api_key
        )
    
    def get_processing_config(self) -> ProcessingConfig:
        """Get processing configuration"""
        return ProcessingConfig(
            chunk_size=self.settings.chunk_size,
            min_score_threshold=self.settings.min_score_threshold,
            max_clips_per_collection=self.settings.max_clips_per_collection,
            max_retries=self.settings.max_retries,
            timeout_seconds=self.settings.timeout_seconds
        )
    
    def get_path_config(self) -> PathConfig:
        """Get paths configuration"""
        return PathConfig()
    
    def ensure_project_directories(self, project_id: str):
        """Ensure project directory structure exists"""
        paths = self.get_project_paths(project_id)
        for path in paths.values():
            if isinstance(path, Path):
                path.mkdir(parents=True, exist_ok=True)
    
    def get_project_paths(self, project_id: str) -> Dict[str, Path]:
        """Get project paths configuration"""
        data_dir = self.get_path_config().data_dir
        projects_dir = data_dir / "projects"
        project_base = projects_dir / project_id
        
        return {
            "project_base": project_base,
            "input_dir": project_base / "raw",
            "output_dir": project_base / "output",
            "clips_dir": project_base / "output" / "clips",
            "collections_dir": project_base / "output" / "collections",
            "metadata_dir": project_base / "output" / "metadata",
            "logs_dir": project_base / "logs",
            "temp_dir": project_base / "temp"
        }
    
    def update_api_key(self, api_key: str):
        """Update API key"""
        self.settings.dashscope_api_key = api_key
        os.environ["DASHSCOPE_API_KEY"] = api_key
        self._save_settings()
    
    def update_settings(self, **kwargs):
        """Update settings"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self._save_settings()
    
    def _save_settings(self):
        """Save settings to file"""
        config_file = path_utils.get_settings_file_path()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings.dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save settings file: {e}")
    
    def export_config(self) -> Dict[str, Any]:
        """Export configuration"""
        return {
            "api_config": {
                "model_name": self.settings.model_name,
                "api_key": self.settings.dashscope_api_key[:8] + "..." if self.settings.dashscope_api_key else None
            },
            "processing_config": {
                "chunk_size": self.settings.chunk_size,
                "min_score_threshold": self.settings.min_score_threshold,
                "max_clips_per_collection": self.settings.max_clips_per_collection,
                "max_retries": self.settings.max_retries,
                "timeout_seconds": self.settings.timeout_seconds
            },
            "paths": {
                "project_root": str(self.get_path_config().project_root),
                "data_dir": str(self.get_path_config().data_dir),
                "uploads_dir": str(self.get_path_config().uploads_dir),
                "output_dir": str(self.get_path_config().output_dir),
                "prompt_dir": str(self.get_path_config().prompt_dir)
            }
        }

# Get prompt file paths according to video category
def get_prompt_files(video_category: str = VideoCategory.DEFAULT) -> Dict[str, Path]:
    """
    Get corresponding prompt file paths based on video category.
    If category-specific prompt file does not exist, fall back to default prompt file.
    """
    category_prompt_dir = PROMPT_DIR / video_category
    default_prompt_files = PROMPT_FILES.copy()
    
    if category_prompt_dir.exists():
        category_prompt_files = {}
        for key, default_path in default_prompt_files.items():
            category_file = category_prompt_dir / default_path.name
            if category_file.exists():
                category_prompt_files[key] = category_file
            else:
                category_prompt_files[key] = default_path
        return category_prompt_files
    
    return default_prompt_files

# Global configuration manager instance
config_manager = ConfigManager()

def get_legacy_config() -> Dict[str, Any]:
    """Get backward-compatible configuration dictionary"""
    return {
        'PROJECT_ROOT': PROJECT_ROOT,
        'INPUT_DIR': INPUT_DIR,
        'INPUT_VIDEO': INPUT_VIDEO,
        'INPUT_SRT': INPUT_SRT,
        'INPUT_TXT': INPUT_TXT,
        'OUTPUT_DIR': OUTPUT_DIR,
        'CLIPS_DIR': CLIPS_DIR,
        'COLLECTIONS_DIR': COLLECTIONS_DIR,
        'METADATA_DIR': METADATA_DIR,
        'PROMPT_DIR': PROMPT_DIR,
        'PROMPT_FILES': PROMPT_FILES,
        'DASHSCOPE_API_KEY': DASHSCOPE_API_KEY,
        'HUGGINGFACE_TOKEN': HUGGINGFACE_TOKEN,
        'MODEL_NAME': MODEL_NAME,
        'CHUNK_SIZE': CHUNK_SIZE,
        'MIN_SCORE_THRESHOLD': MIN_SCORE_THRESHOLD,
        'MAX_CLIPS_PER_COLLECTION': MAX_CLIPS_PER_COLLECTION
    }


# CTA Overlay defaults (main pipeline)
DEFAULT_CTA_STYLE    = "pill"         # "pill" (modern standalone button) | "card" (channel badge) | "follow_tap"
DEFAULT_CTA_PLATFORM = "tiktok"       # default platform when not specified
DEFAULT_CTA_HANDLE   = ""             # e.g. "@yourhandle"
DEFAULT_CTA_POSITION = "lower_center" # "lower_center" (safe viewer zone) | "bottom_center" | "center"
