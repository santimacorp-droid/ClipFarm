"""
Match pre-written campaign caption options to specific clip moments.
Uses keyword overlap scoring — no LLM required.
"""
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

def match_captions_to_moment(
    moment_name:    str,
    matched_text:   str,
    caption_options: List[str],
    top_n:          int = 3
) -> List[dict]:
    """
    Score and rank caption_options by relevance to the clip's moment.
    Returns top_n captions with rank and text.
    """
    if not caption_options:
        return []
    
    # Build keyword set from moment name + matched transcript text
    combined = f"{moment_name} {matched_text}".lower()
    keywords = set(re.findall(r'\b[a-z]{3,}\b', combined))
    # Remove stop words
    stop_words = {'the', 'and', 'for', 'are', 'was', 'its', 'you', 'this', 'that', 
                  'with', 'from', 'your', 'what', 'just', 'now', 'can', 'has', 'not'}
    keywords -= stop_words
    
    scored = []
    for i, caption in enumerate(caption_options):
        caption_words = set(re.findall(r'\b[a-z]{3,}\b', caption.lower()))
        overlap = len(keywords & caption_words)
        scored.append({'caption': caption, 'score': overlap, 'original_index': i})
    
    # Sort by overlap score descending, then by original order for tie-breaking
    scored.sort(key=lambda x: (-x['score'], x['original_index']))
    
    return [
        {'rank': rank + 1, 'text': item['caption']}
        for rank, item in enumerate(scored[:top_n])
    ]
