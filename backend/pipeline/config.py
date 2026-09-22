"""
Pipeline module configuration file
"""

import os
from pathlib import Path

# Project root directories
PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "output" / "metadata"

# Prompt file paths
PROMPT_DIR = PROJECT_ROOT / "prompt"
PROMPT_FILES = {
    'outline': PROMPT_DIR / "outline.txt",
    'timeline': PROMPT_DIR / "timeline.txt", 
    'scoring': PROMPT_DIR / "recommendation.txt",
    'recommendation': PROMPT_DIR / "recommendation.txt",
    'title': PROMPT_DIR / "title.txt",
    'clustering': PROMPT_DIR / "clustering.txt"
}

# Ensure directories exist
METADATA_DIR.mkdir(parents=True, exist_ok=True)
PROMPT_DIR.mkdir(parents=True, exist_ok=True)

# API key configuration
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Default API key
DEFAULT_API_KEY = DASHSCOPE_API_KEY or OPENAI_API_KEY

# Scoring threshold
MIN_SCORE_THRESHOLD = 7.0

# Clustering configuration
MAX_CLIPS_PER_COLLECTION = 10
