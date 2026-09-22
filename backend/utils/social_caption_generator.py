"""
Social Media Post Caption & Hashtag Generator
Generates high-retention, search-optimized posting captions and hashtags for TikTok, Instagram Reels, and YouTube Shorts.
Grounded in:
1. Local Scene Context: What specifically happens in this clip (quotes, jokes, tech verdict, story turning point).
2. Global Video Context: The overarching video topic, channel/speaker, and discussion themes.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from .llm_client import LLMClient
from .text_processor import TextProcessor

logger = logging.getLogger(__name__)

CATEGORY_HASHTAG_BANKS = {
    "podcast": [
        "#podcast", "#podcastclips", "#interview", "#podcastersofinstagram",
        "#unfiltered", "#conversations", "#deepdive", "#mustwatch"
    ],
    "interview": [
        "#interview", "#interviewclips", "#exclusive", "#candid",
        "#realtalk", "#behindthescenes", "#spotlight"
    ],
    "tech_take": [
        "#techtok", "#techreview", "#gadgets", "#artificialintelligence",
        "#technews", "#apple", "#innovation", "#futuretech"
    ],
    "ai_moment": [
        "#ai", "#artificialintelligence", "#aitools", "#chatgpt",
        "#techtrends", "#machinelearning", "#innovation"
    ],
    "funny_moment": [
        "#funny", "#comedy", "#humor", "#funnymoments",
        "#laugh", "#relatable", "#viralcomedy", "#hilarious"
    ],
    "entertainment": [
        "#entertainment", "#popculture", "#viral", "#funnymoments",
        "#trending", "#mustwatch"
    ],
    "storytelling": [
        "#storytime", "#truestory", "#lifelessons", "#motivation",
        "#storyteller", "#inspirational", "#wisdom", "#perspective"
    ],
    "experience": [
        "#experience", "#lessonslearned", "#reallife", "#growth",
        "#journey", "#motivation"
    ],
    "business": [
        "#business", "#entrepreneur", "#startups", "#marketing",
        "#founders", "#businessgrowth", "#mindset", "#success"
    ],
    "business_insight": [
        "#businessstrategy", "#entrepreneurship", "#marketingtips", "#founders",
        "#businesstips", "#scaleup", "#venture"
    ],
    "knowledge": [
        "#learning", "#knowledge", "#didyouknow", "#education",
        "#insights", "#facts", "#mindblown"
    ],
    "vlog": [
        "#vlog", "#vlogger", "#dayinthelife", "#travelvlog",
        "#lifestyle", "#behindthescenes", "#dailyvlog"
    ],
    "default": [
        "#shorts", "#reels", "#tiktok", "#viral",
        "#trending", "#contentcreator"
    ]
}

CAPTION_SYSTEM_PROMPT = """You are an elite short-form video copywriter and social media growth strategist for YouTube Shorts, Instagram Reels, and TikTok.

Your goal is to write high-retention, search-optimized social posting captions and hashtags for a short-form video clip.

CRITICAL DUAL-CONTEXT GROUNDING:
1. WHAT IS HAPPENING IN THIS CLIP (LOCAL SCENE CONTEXT):
   - Anchor the caption in what actually happens in this specific clip (the key quote, the sudden twist, the tech benchmark, the punchline, or the turning point).
   - Never write generic, vacuous fluff. Speak to the exact moment the viewer is watching.

2. WHOLE VIDEO CONTEXT (GLOBAL BACKSTORY & THEME):
   - You have access to the overarching video title, category, and outline themes of the full source video.
   - Use this global context to anchor the moment — state who is speaking, what the broader topic or background experiment is, and why this moment occurred.
   - This provides crucial backstory so the viewer instantly understands the stakes.

3. ALGORITHMIC VIRALITY & RETENTION RULES:
   - Line 1 Hook: Must stop the feed scroll (<120 characters). Compelling, curiosity-inducing, or relatable dilemma. Avoid cringe slogans.
   - Caption Body: 2-3 short, punchy paragraphs with clean whitespace explaining the context and key takeaway.
   - Engagement Question / CTA: Close with an open-ended debate or opinion question that triggers comments (comments are the #1 algorithmic distribution signal).
   - Targeted Hashtags:
     * 2-3 High-volume broad discovery tags (#shorts, #reels, #tiktok, #viral)
     * 3-4 Category & niche community tags
     * 2-3 Ultra-specific topical/entity tags based on actual names, products, or subjects mentioned

OUTPUT FORMAT:
Return ONLY a valid JSON object with the following structure:
{
  "hook_line": "Opening scroll-stopping sentence (<120 chars)",
  "post_caption": "Full formatted caption with line breaks, context, and engagement question",
  "hashtags": ["#shorts", "#reels", "#topic1", "#topic2", "#entity1"],
  "engagement_question": "Open-ended question asking for viewer opinion or reaction",
  "search_keywords": ["search query 1", "search query 2", "search query 3"],
  "platforms": {
    "tiktok": {
      "caption": "TikTok-optimized caption with keyword search phrases and CTA",
      "hashtags": "#fyp #viral #topic1 #topic2"
    },
    "instagram": {
      "caption": "Instagram Reels-optimized caption formatted with clean line breaks and question prompt",
      "hashtags": "#reels #topic1 #topic2 #topic3"
    },
    "youtube_shorts": {
      "title": "Search-friendly title under 70 characters",
      "description": "YouTube Shorts description with search terms, summary, and links",
      "hashtags": "#shorts #topic1 #topic2"
    }
  }
}
"""


class SocialCaptionGenerator:
    """
    Generates intelligent social media post captions, descriptions, conversation hooks,
    and platform-targeted hashtags for short-form clips.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    @staticmethod
    def extract_clip_transcript(srt_path: Optional[Path], start_sec: float, end_sec: float) -> str:
        """Extract all spoken subtitle text within [start_sec, end_sec] from an SRT file."""
        if not srt_path or not Path(srt_path).exists():
            return ""

        try:
            from .video_processor import VideoProcessor
            subs = TextProcessor.parse_srt(Path(srt_path))
            if not subs:
                return ""

            lines = []
            for s in subs:
                t_start = VideoProcessor.convert_ffmpeg_time_to_seconds(s.get('start_time', 0))
                t_end = VideoProcessor.convert_ffmpeg_time_to_seconds(s.get('end_time', 0))
                # Check overlap
                if t_end >= start_sec and t_start <= end_sec:
                    clean_text = re.sub(r'<[^>]+>', '', s.get('text', '')).strip()
                    if clean_text and clean_text not in lines:
                        lines.append(clean_text)

            return " ".join(lines)
        except Exception as e:
            logger.debug(f"Failed to slice clip transcript from {srt_path}: {e}")
            return ""

    @staticmethod
    def extract_core_entities(text: str, max_entities: int = 4) -> List[str]:
        """Extract meaningful topic entities and capitalized proper nouns for hashtag formation."""
        if not text:
            return []
        
        # Look for capitalized words or acronyms (e.g. Robin Williams, M4, Intel, AI)
        candidates = re.findall(r'\b[A-Z][a-zA-Z0-9_]{2,}\b', text)
        stop_words = {
            'The', 'This', 'That', 'What', 'When', 'Where', 'Why', 'How', 'And',
            'For', 'With', 'From', 'Your', 'Some', 'More', 'Then', 'Just', 'About',
            'Clip', 'Video', 'Watch', 'Short', 'True', 'Real', 'There', 'They'
        }
        filtered = []
        for c in candidates:
            if c not in stop_words and c.lower() not in [f.lower() for f in filtered]:
                filtered.append(c.lower())
                if len(filtered) >= max_entities:
                    break
        return filtered

    @staticmethod
    def build_hashtags(category: str, entities: List[str] = None, max_tags: int = 8) -> List[str]:
        """Generate a well-balanced hashtag set combining broad, niche, and entity tags."""
        tags = ["#shorts", "#reels"]
        
        # Category specific tags
        cat_key = category.lower().replace(" ", "_") if category else "default"
        cat_tags = CATEGORY_HASHTAG_BANKS.get(cat_key, CATEGORY_HASHTAG_BANKS["default"])
        for ct in cat_tags[:3]:
            if ct not in tags:
                tags.append(ct)
        
        # Entity tags
        if entities:
            for ent in entities:
                ent_clean = re.sub(r'[^a-zA-Z0-9]', '', ent).lower()
                if ent_clean and len(ent_clean) >= 3:
                    tag = f"#{ent_clean}"
                    if tag not in tags:
                        tags.append(tag)
        
        # Fill with additional category tags if needed
        for ct in cat_tags[3:]:
            if len(tags) >= max_tags:
                break
            if ct not in tags:
                tags.append(ct)
                
        return tags[:max_tags]

    def _generate_fallback_caption(
        self,
        clip_data: Dict[str, Any],
        global_context: Dict[str, Any],
        clip_transcript: str = ""
    ) -> Dict[str, Any]:
        """
        Deterministic, robust fallback caption generator that synthesizes:
        - Hook line
        - Scene context referencing the whole video
        - Content highlights
        - Discussion question
        - Category and entity hashtags
        """
        title = clip_data.get('generated_title') or clip_data.get('title') or "Clip Highlight"
        hook_text = clip_data.get('hook_text') or clip_data.get('hook_title') or title
        category = clip_data.get('category') or global_context.get('video_category', 'general')
        video_title = global_context.get('video_title') or global_context.get('project_name', 'Full Video')
        
        # Extract entities from title, transcript, and content
        combined_text = f"{title} {hook_text} {clip_transcript}"
        entities = self.extract_core_entities(combined_text)
        hashtags = self.build_hashtags(category, entities=entities, max_tags=8)
        hashtags_str = " ".join(hashtags)
        
        # Determine appropriate engagement question based on category
        cat_lower = category.lower()
        if "tech" in cat_lower or "ai" in cat_lower:
            question = "What's your take on this? Drop your thoughts below 👇"
        elif "funny" in cat_lower or "entertainment" in cat_lower:
            question = "How would you have reacted here? Let me know below 😂👇"
        elif "story" in cat_lower or "experience" in cat_lower:
            question = "Have you ever experienced something like this? Share below 👇"
        elif "business" in cat_lower or "podcast" in cat_lower or "interview" in cat_lower:
            question = "Do you agree with this take? Let's discuss in the comments 👇"
        else:
            question = "What do you think about this? Share your perspective below 👇"

        # Construct scene body referencing the whole video
        body_lines = []
        if video_title and video_title not in ["input.mp4", "Full Video", "video.mp4"]:
            body_lines.append(f"From '{video_title}': {title}.")
        else:
            body_lines.append(f"{title}.")

        # Add concrete details from content bullet points or transcript snippet
        content = clip_data.get('content') or []
        if isinstance(content, list) and content:
            body_lines.append(" ".join(str(c).strip() for c in content[:2]))
        elif clip_transcript:
            snippet = clip_transcript[:180].strip()
            if len(clip_transcript) > 180:
                snippet += "..."
            body_lines.append(f'"{snippet}"')

        body_lines.append(question)
        body_text = "\n\n".join(body_lines)
        post_caption = f"{hook_text}\n\n{body_text}\n\n{hashtags_str}"

        # Platform specific fallbacks
        tiktok_tags = f"#fyp #viral {' '.join(hashtags[:4])}"
        tiktok_caption = f"{hook_text}\n\n{title} — {question}\n\n{tiktok_tags}"

        ig_tags = " ".join(hashtags)
        ig_caption = f"{hook_text}\n\n{body_text}\n\n.\n.\n{ig_tags}"

        yt_title = title[:68]
        yt_desc = f"{title}\n\n{body_text}\n\n{hashtags_str}"

        search_kw = [title.lower()] + [e for e in entities if len(e) > 3]

        return {
            "hook_line": hook_text,
            "post_caption": post_caption,
            "hashtags": hashtags,
            "hashtags_str": hashtags_str,
            "engagement_question": question,
            "search_keywords": search_kw[:4],
            "platforms": {
                "tiktok": {
                    "caption": tiktok_caption,
                    "hashtags": tiktok_tags
                },
                "instagram": {
                    "caption": ig_caption,
                    "hashtags": ig_tags
                },
                "youtube_shorts": {
                    "title": yt_title,
                    "description": yt_desc,
                    "hashtags": f"#shorts {' '.join(hashtags[:3])}"
                }
            }
        }

    def generate_social_caption(
        self,
        clip_data: Dict[str, Any],
        global_context: Dict[str, Any],
        srt_path: Optional[Path] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate rich posting caption and hashtags for a single clip.
        
        Args:
            clip_data: Clip dictionary containing id, title, hook_text, start_time, end_time, etc.
            global_context: Dictionary with video_title, video_category, outlines, speaker/channel.
            srt_path: Optional path to project SRT file to slice exact speech transcript.
            model: Optional LLM model override.
            
        Returns:
            Structured dictionary with hook_line, post_caption, hashtags, engagement_question, platforms.
        """
        # 1. Resolve start/end seconds and slice transcript
        start_time = clip_data.get('start_time', 0.0)
        end_time = clip_data.get('end_time', 0.0)
        from .video_processor import VideoProcessor
        start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(start_time)
        end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(end_time)
        
        clip_transcript = clip_data.get('transcript') or ""
        if not clip_transcript and srt_path:
            clip_transcript = self.extract_clip_transcript(srt_path, start_sec, end_sec)

        # 2. Assemble LLM prompt inputs
        category = clip_data.get('category') or global_context.get('video_category', 'general')
        video_title = global_context.get('video_title') or global_context.get('project_name', 'Full Video')
        video_outlines = global_context.get('outlines') or []
        outline_summary = ""
        if isinstance(video_outlines, list) and video_outlines:
            outline_titles = [
                str(o.get('title') or o.get('outline', '')) for o in video_outlines[:6]
                if (isinstance(o, dict) and (o.get('title') or o.get('outline')))
            ]
            if outline_titles:
                outline_summary = f"Full Video Topics: {', '.join(outline_titles)}"

        input_data = {
            "clip_id": clip_data.get('id'),
            "clip_title": clip_data.get('generated_title') or clip_data.get('title'),
            "hook_text": clip_data.get('hook_text') or clip_data.get('hook_title'),
            "clip_transcript": clip_transcript[:1200] if clip_transcript else "Transcript segment not available",
            "content_points": clip_data.get('content', []),
            "recommend_reason": clip_data.get('recommend_reason', ''),
            "category": category,
            "whole_video_title": video_title,
            "whole_video_context": outline_summary or f"Category: {category}",
            "speaker_or_channel": global_context.get('channel_or_speaker', '')
        }

        # 3. Query LLM
        try:
            logger.info(f"Generating social posting caption for clip {clip_data.get('id')} ({input_data['clip_title']})...")
            response = self.llm_client.call_with_retry(
                CAPTION_SYSTEM_PROMPT,
                input_data,
                task="titling",
                model=model
            )
            parsed = self.llm_client.parse_json_response(response) if response else None

            if isinstance(parsed, dict) and parsed.get("post_caption"):
                # Normalize hashtags
                raw_tags = parsed.get("hashtags", [])
                if isinstance(raw_tags, str):
                    raw_tags = [t.strip() for t in raw_tags.split() if t.strip()]
                elif not isinstance(raw_tags, list):
                    raw_tags = []

                # Ensure tags have '#' prefix
                clean_tags = []
                for t in raw_tags:
                    t_str = str(t).strip()
                    if not t_str.startswith("#"):
                        t_str = f"#{t_str}"
                    if t_str not in clean_tags:
                        clean_tags.append(t_str)

                # Ensure at least #shorts and #reels
                for base_tag in ["#shorts", "#reels"]:
                    if base_tag not in clean_tags:
                        clean_tags.insert(0, base_tag)

                parsed["hashtags"] = clean_tags[:10]
                parsed["hashtags_str"] = " ".join(parsed["hashtags"])

                # Ensure platforms dict exists
                if not isinstance(parsed.get("platforms"), dict):
                    fallback_plat = self._generate_fallback_caption(clip_data, global_context, clip_transcript)
                    parsed["platforms"] = fallback_plat["platforms"]

                logger.info(f"Generated social caption successfully for clip {clip_data.get('id')}")
                return parsed

        except Exception as err:
            logger.warning(f"LLM social caption generation failed for clip {clip_data.get('id')}: {err}")

        # 4. Fallback if LLM fails or is unavailable
        logger.info(f"Using deterministic fallback social caption for clip {clip_data.get('id')}")
        return self._generate_fallback_caption(clip_data, global_context, clip_transcript)

    def batch_generate_social_captions(
        self,
        clips: List[Dict[str, Any]],
        global_context: Dict[str, Any],
        srt_path: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch generate social captions for a list of clips.
        Modifies clips in-place and returns the list.
        """
        for clip in clips:
            try:
                social_copy = self.generate_social_caption(
                    clip_data=clip,
                    global_context=global_context,
                    srt_path=srt_path
                )
                clip['social_copy'] = social_copy
                clip['post_caption'] = social_copy.get('post_caption', '')
                clip['hashtags'] = social_copy.get('hashtags', [])
            except Exception as e:
                logger.warning(f"Failed to generate social copy for clip {clip.get('id')}: {e}")
                fallback = self._generate_fallback_caption(clip, global_context)
                clip['social_copy'] = fallback
                clip['post_caption'] = fallback['post_caption']
                clip['hashtags'] = fallback['hashtags']

        return clips
