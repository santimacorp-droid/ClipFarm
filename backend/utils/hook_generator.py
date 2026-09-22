"""
AI Viral Hook & Headline Generator (2026 Creative Reels Edition)
Analyzes transcript content and clip distinctiveness to generate high-converting,
curiosity-gap top hook headlines tailored specifically to video categories:
Podcasts, Interviews, Vlogs, Storytelling, Business/Knowledge, Tech, and Entertainment.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pathlib import Path

from .llm_client import LLMClient

logger = logging.getLogger(__name__)

# Comprehensive emoji matching regex: supports single emojis, pictographs, symbols,
# dingbats, variation selectors, skin tone modifiers, and ZWJ sequence combinations.
EMOJI_PATTERN = re.compile(
    r'(?:'
    r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]'
    r')(?:[\ufe00-\ufe0f]|[\U0001f3fb-\U0001f3ff]|'
    r'\u200d(?:[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff])(?:[\ufe00-\ufe0f]|[\U0001f3fb-\U0001f3ff])*)*'
)

HIGHLIGHT_TAG_PATTERN = re.compile(r'</?hl>', re.IGNORECASE)

CATEGORY_HOOK_ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "podcast": {
        "label": "Podcast Conversation",
        "vibe": "Unscripted tension, stunned silence, guest pushback, raw admissions, and contrarian debates.",
        "formulas": [
            "The question that stunned him 😳🎤",
            "What guests never say on camera 🤫🎙️",
            "The exact second the room went silent 🤐👀",
            "He just admitted this out loud 💀🗣️",
            "Why 99% of people have this backwards 🤯🧠",
            "He refused to answer this question 🤐🎙️"
        ],
        "emojis": ["🎙️", "👀", "😳", "🤐", "🤯", "💀", "🤫", "🔥"]
    },
    "podcast_highlight": {
        "label": "Podcast Highlight",
        "vibe": "Single sharpest moment, memorable punchline, or debate climax from a podcast.",
        "formulas": [
            "Wait for his reaction to this 😳👀",
            "He said the quiet part out loud 💀🎙️",
            "The moment the debate got heated 🔥🗣️",
            "This stopped everyone in their tracks 🤐⚡"
        ],
        "emojis": ["🎙️", "⚡", "👀", "🤯", "🔥", "💀"]
    },
    "interview": {
        "label": "Structured Interview",
        "vibe": "High-stakes direct Q&A, executive secrets, life turning points, and vulnerability.",
        "formulas": [
            "The one question nobody dared to ask 🤐🎤",
            "What top CEOs never say on camera 🤫💼",
            "The $10M mistake he never recovered from 💸💀",
            "The moment his whole mindset shifted 💡🤯",
            "He called out the entire industry 🚨🗣️"
        ],
        "emojis": ["🎤", "🤫", "👀", "💡", "🤯", "💀", "🚨"]
    },
    "vlog": {
        "label": "Vlog / Lifestyle",
        "vibe": "In-media-res stakes, relatable chaotic moments, unfiltered travel/life reality, and high-stakes transformation.",
        "formulas": [
            "I wasn't supposed to say yes to this 💀🌴",
            "3 seconds before everything went wrong 🚨🏃",
            "What Instagram hides about this place 😭☕",
            "Never make this travel mistake 🚨✈️",
            "I tried living like this for 30 days 🤯✨",
            "Tell me this isn't the most chaotic day 💀😂"
        ],
        "emojis": ["✈️", "☕", "🌴", "😭", "💀", "🤯", "🚨", "✨"]
    },
    "storytelling": {
        "label": "Narrative Storytelling",
        "vibe": "Narrative climax, unexpected twists, personal stakes, and life-changing turns.",
        "formulas": [
            "The decision that cost me everything 💸💀",
            "Nobody believed me until this happened 🤯👀",
            "I found out the hard way 😭⚡",
            "How 1 minute changed the next 10 years ⏳💡"
        ],
        "emojis": ["📖", "🤯", "💀", "😭", "⏳", "💡", "⚡"]
    },
    "experience": {
        "label": "Personal Experience / How-To",
        "vibe": "Hands-on testing, raw personal trials, mistakes, and real-world results.",
        "formulas": [
            "I tested this so you don't have to 🤯🛠️",
            "What happened when I actually tried it 👀🔥",
            "The mistake that ruined my first attempt 💀😭"
        ],
        "emojis": ["🛠️", "👀", "🤯", "🔥", "💀", "💡"]
    },
    "business": {
        "label": "Business & Finance",
        "vibe": "Pattern interrupts, stop-doing warnings, high-stakes dollar insights, and founder realities.",
        "formulas": [
            "Stop doing this if you want to grow 🛑📈",
            "Why 90% of businesses fail at this 💀📉",
            "The exact playbook that scaled to $1M 📈💡",
            "This 1 mistake costs founders millions 💸💀",
            "What billionaires do that you don't 🤫💰"
        ],
        "emojis": ["💡", "📈", "💰", "🤫", "🛑", "💸", "🔥"]
    },
    "business_insight": {
        "label": "Business Insight",
        "vibe": "Asymmetric leverage, contrarian market truths, negotiation secrets, and consumer psychology.",
        "formulas": [
            "They are not just selling a product 📈💡",
            "The psychological trick that closed the deal 🧠🤫",
            "Why smart founders avoid this trap 🛑💡",
            "The hidden revenue model nobody sees 🤫💰"
        ],
        "emojis": ["💡", "📈", "🧠", "🤫", "💰", "🔥"]
    },
    "tech_take": {
        "label": "Tech & Engineering",
        "vibe": "Benchmark realities, developer hot takes, silent disruptions, and architectural traps.",
        "formulas": [
            "Why everyone is quietly abandoning this 💀💻",
            "This update changes everything we know ⚡🤖",
            "The dirty secret behind this architecture 🤫💻",
            "We benchmarked this and the results were insane 🤯📊"
        ],
        "emojis": ["💻", "⚡", "🤖", "🤯", "🤫", "📊", "🔥"]
    },
    "ai_moment": {
        "label": "AI & Future Tech",
        "vibe": "Mind-blowing AI breakthroughs, workflow disruptions, existential questions, and live demos.",
        "formulas": [
            "AI just crossed the line with this 🤯🤖",
            "They didn't want the public to see this 🤫⚡",
            "The AI workflow that replaced 5 people ⚡💻",
            "Watch what happens when you prompt this 🤖👀"
        ],
        "emojis": ["🤖", "🤯", "⚡", "🤫", "💻", "👀"]
    },
    "entertainment": {
        "label": "Entertainment & Pop Culture",
        "vibe": "Unbelievable moments, anticipation, crowd shock, and instant hilarity.",
        "formulas": [
            "Bro said this with 100% confidence 💀🔥",
            "3 seconds before disaster struck 💀🚨",
            "There is NO WAY he just pulled that off 🤯🍿",
            "They played him so dirty 🤯😂"
        ],
        "emojis": ["🍿", "💀", "😂", "🤯", "🔥", "🚨"]
    },
    "funny_moment": {
        "label": "Comedy & Fails",
        "vibe": "Chaotic humor, unhinged fails, absurd comebacks, and pure comedy.",
        "formulas": [
            "BRO COULD NOT HOLD IT TOGETHER 😭💀",
            "The moment he realized he messed up 💀😂",
            "She thought she was slick 😭👀",
            "I'm crying at his reaction 😭💀"
        ],
        "emojis": ["💀", "😭", "😂", "👀", "🔥"]
    },
    "hot_take": {
        "label": "Hot Takes & Opinions",
        "vibe": "Controversial opinions, unpopular truths, fierce debate triggers.",
        "formulas": [
            "The most controversial take of the year 🌶️🔥",
            "I don't care who gets mad at this 🚨😤",
            "Someone finally said it out loud 🗣️🔥",
            "Why everyone is completely wrong about this 🤯🌶️"
        ],
        "emojis": ["🌶️", "🔥", "🚨", "🤯", "🗣️", "😤"]
    },
    "knowledge": {
        "label": "Knowledge & Psychology",
        "vibe": "Counter-intuitive insights, mental models, cognitive illusions, and 'aha!' realizations.",
        "formulas": [
            "The mental trick that changes how you think 🧠💡",
            "Why your brain tricks you into this 🤯🧠",
            "The dark side of this psychological rule 🤫💡",
            "Stop believing this common myth 🛑🧠"
        ],
        "emojis": ["💡", "🧠", "🤯", "🤫", "🛑", "👀"]
    },
    "speech": {
        "label": "Speech & Keynote",
        "vibe": "Inspirational power, climactic life advice, perspective shifts.",
        "formulas": [
            "The advice that saved my entire life 🎯💡",
            "Listen carefully to what he says next ⚡👀",
            "The uncomfortable truth about growing up 🧠⚡"
        ],
        "emojis": ["🎯", "⚡", "💡", "🔥", "👀"]
    },
    "gaming_highlight": {
        "label": "Gaming Highlight",
        "vibe": "Clutch plays, rage quits, epic fails, insane RNG.",
        "formulas": [
            "The 1 in a million clutch play 🎮🔥",
            "Bro raged so hard at this 💀🎮",
            "He had NO RIGHT winning that round 🤯🎮"
        ],
        "emojis": ["🎮", "💀", "🔥", "🤯", "⚡"]
    }
}

# Fast emoji lookup table per category
CATEGORY_EMOJIS = {k: v["emojis"] for k, v in CATEGORY_HOOK_ARCHETYPES.items()}
CATEGORY_EMOJIS["general"] = ["🔥", "👀", "💡", "🚨", "💀", "🤯"]


def clean_hook_markup(text: str) -> str:
    """Strips <hl> and </hl> highlight tags from text."""
    if not text:
        return ""
    return HIGHLIGHT_TAG_PATTERN.sub("", text).strip()


def build_hook_system_prompt(category: str = "general") -> str:
    """
    Builds a category-tailored viral Reels/Shorts/Meme hook system prompt.
    Emphasizes natural storytelling setups, narrative context (8–25 words), and non-cringe tone.
    """
    cat_key = (category or "general").lower().replace("-", "_").strip()
    archetype = CATEGORY_HOOK_ARCHETYPES.get(cat_key, {
        "label": "Viral Narrative Highlight",
        "vibe": "Genuine human stakes, situational context, unexpected turns, or candid observations.",
        "formulas": [
            "The day Robin Williams made Koko laugh, a gorilla mourning her son",
            "When super nanny realizes this little boy wasn't misbehaving",
            "When the performer stopped singing to record the crowd",
            "It hits different when you realize what actually happened"
        ],
        "emojis": []
    })

    formulas_text = "\n".join(f"- {f}" for f in archetype["formulas"])

    return f"""You are an elite short-form video director specializing in authentic, high-retention Instagram Reels, TikTok, and YouTube Shorts top narrative hooks.
Your task is to craft a compelling, non-cringe TOP HOOK HEADLINE for a video clip in the **{archetype['label']}** category.

## Content Category Context:
- **Category**: {archetype['label']}
- **Core Energy & Vibe**: {archetype['vibe']}

## Proven Storytelling & Hook Principles:
1. **Unconfined Narrative Setup (8 to 25 words)**:
   - Do NOT artificially restrict hooks to 3–4 words! Provide enough narrative context so the viewer instantly understands what makes this scene historic, hilarious, heartbreaking, or mind-blowing.
   - Ideal formats:
     * Situational premise: "When [Subject] realizes [Emotional/Shocking truth]..."
     * Storytelling event: "The day [Subject] did [Unusual/Moving action]..."
     * Candid observation: "When [Person] stopped [X] to [Y]..."
     * Reflective/relatable setup: "It hits different when [Relatable emotional struggle]..."
2. **Ground in What's Actually Happening**: Directly anchor in the specific scene, spoken dialogue, or revelation in the transcript.
3. **Banned Cringe Clichés**: NEVER use cheap generic hype like "Bro said this with 100% confidence", "Watch until the end", "You won't believe this", "MUST WATCH", or screaming emoji walls.
4. **Emojis are Strictly Optional**:
   - Do NOT force emojis. A clean, text-only headline is often the most professional and viral format (0 emojis is preferred).
   - If an emoji is used, at most 1 subtle, genuinely fitting emoji (e.g. 🥺, 😂, 😳) at the very end.
5. **Optional Keyword Accent**: You may wrap 1–2 key punch words in `<hl>...</hl>` tags for visual emphasis (e.g. "When super nanny realizes he was <hl>just missing his mom</hl> 🥺").

## Example Formulas:
{formulas_text}

## Output Format:
Return ONLY a valid JSON object:
{{
  "hook_headline": "Narrative premise or situational setup (8–25 words, clean text, optional 0–1 emoji)",
  "clip_title": "Descriptive, engaging feed title for the clip"
}}
"""


def build_batch_hook_system_prompt(category: str = "general") -> str:
    """
    Builds a category-tailored batch viral Reels/Shorts narrative hook system prompt.
    """
    cat_key = (category or "general").lower().replace("-", "_").strip()
    archetype = CATEGORY_HOOK_ARCHETYPES.get(cat_key, {
        "label": "Viral Narrative Highlight",
        "vibe": "Genuine human stakes, situational context, unexpected turns, or candid observations.",
        "formulas": [
            "The day Robin Williams made Koko laugh, a gorilla mourning her son",
            "When super nanny realizes this little boy wasn't misbehaving",
            "When the performer stopped singing to record the crowd"
        ],
        "emojis": []
    })

    formulas_text = "\n".join(f"- {f}" for f in archetype["formulas"])

    return f"""You are an elite short-form video director specializing in authentic Instagram Reels, TikTok, and YouTube Shorts top narrative hooks.
Evaluate the batch of video clips in the **{archetype['label']}** category and generate a natural top hook headline and title for each clip.

## Category Energy & Archetype:
{archetype['vibe']}

## Proven Narrative Formats:
{formulas_text}

## Core Rules:
1. Natural narrative length (8 to 25 words). Do NOT confine to 3–4 words; give viewers enough premise to care about the moment.
2. Ground directly in what uniquely occurs in that segment.
3. Emojis are completely optional (0 to 1 subtle emoji max; no forced emojis).
4. Ban cringe hype like "Bro said this with 100% confidence" or "Wait till the end".
5. Optional Keyword Accent: You may wrap 1–2 key punch words in `<hl>...</hl>` tags.
6. Return ONLY a valid JSON array of objects.

## Output Format:
[
  {{
    "id": "1",
    "hook_headline": "Narrative premise (8–25 words, clean text, optional 0–1 emoji)",
    "clip_title": "Descriptive feed title"
  }}
]
"""


def ensure_hook_has_color_emojis(text: str, category: str = "general", force: bool = False) -> str:
    """
    Sanitizes hook text and preserves clean text without forcing emojis unless explicitly requested.
    Preserves <hl>...</hl> tags.
    """
    clean = str(text or "").strip().strip('"\'')
    if not clean:
        return "Must Watch"
    
    # If not forced and text has no emoji, respect user preference for clean text without forced emojis
    if not force:
        return clean

    # If force=True and text has no emoji, append a contextually relevant emoji
    if EMOJI_PATTERN.search(clean):
        return clean

    cat_key = (category or "general").lower().replace("-", "_").strip()
    emojis = CATEGORY_EMOJIS.get(cat_key, CATEGORY_EMOJIS["general"])
    selected_emoji = emojis[0] if emojis else "🔥"
    return f"{clean} {selected_emoji}"


class ViralHookGenerator:
    @staticmethod
    def batch_generate_hooks(
        clips_data: List[Dict[str, Any]],
        video_title: Optional[str] = None,
        category: str = "general"
    ) -> Dict[str, Dict[str, str]]:
        """
        Batch generate category-aware viral hooks for multiple clips in a single LLM call.
        Returns a dict mapping clip_id -> {"hook_headline": ..., "clip_title": ...}
        """
        if not clips_data:
            return {}

        # Resolve primary category from input or clip items
        effective_category = category
        if not effective_category or effective_category == "general":
            for c in clips_data:
                c_cat = c.get("category")
                if c_cat and c_cat != "general" and c_cat != "default":
                    effective_category = c_cat
                    break

        results: Dict[str, Dict[str, str]] = {}
        input_items = []

        for clip in clips_data:
            cid = str(clip.get("id") or clip.get("clip_id") or len(input_items) + 1)
            raw_text = str(clip.get("transcript") or clip.get("content") or "").strip()
            title = clip.get("title") or clip.get("outline") or ""
            reason = str(clip.get("recommend_reason") or clip.get("what_makes_this_distinctive") or "").strip()
            clip_cat = clip.get("category") or effective_category
            if not raw_text and not reason and not title:
                continue
            input_items.append({
                "id": cid,
                "title": title,
                "video_title": video_title or "",
                "category": clip_cat,
                "distinctive_reason": reason,
                "transcript_excerpt": (raw_text or reason or title)[:800]
            })

        if not input_items:
            return {}

        system_prompt = build_batch_hook_system_prompt(effective_category)

        try:
            llm = LLMClient()
            raw_res = llm.call_with_retry(system_prompt, input_items)
            if raw_res:
                parsed = llm.parse_json_response(raw_res)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("id"):
                            cid = str(item["id"])
                            hook = str(item.get("hook_headline") or "").strip().strip('"\'')
                            title = str(item.get("clip_title") or clean_hook_markup(hook)).strip().strip('"\'')
                            if hook:
                                results[cid] = {
                                    "hook_headline": ensure_hook_has_color_emojis(hook, category=effective_category),
                                    "clip_title": clean_hook_markup(title)
                                }
        except Exception as e:
            logger.warning(f"Batch hook generation failed, falling back to individual: {e}")

        # Fallback for any missing items
        for item in input_items:
            cid = item["id"]
            if cid not in results:
                results[cid] = ViralHookGenerator.generate_hook_from_transcript(
                    item["transcript_excerpt"],
                    video_title=item.get("title") or video_title,
                    category=item.get("category") or effective_category,
                    recommend_reason=item.get("distinctive_reason")
                )

        return results

    @staticmethod
    def generate_hook_from_transcript(
        transcript_text: str,
        video_title: Optional[str] = None,
        category: str = "general",
        recommend_reason: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate a viral top hook headline and title from transcript dialogue,
        tailored strictly to content category.
        """
        clean_text = (transcript_text or "").strip()
        clean_reason = (recommend_reason or "").strip()
        cat_key = (category or "general").lower().replace("-", "_").strip()

        if (not clean_text or len(clean_text) < 10) and not clean_reason:
            fallback_title = clean_hook_markup(video_title or "Viral Highlight")
            fallback_hook = ensure_hook_has_color_emojis(video_title or "Must Watch", category=cat_key)
            return {
                "hook_headline": fallback_hook,
                "clip_title": fallback_title
            }

        prompt_input = [
            {
                "category": cat_key,
                "video_context": video_title or "",
                "distinctive_reason": clean_reason,
                "transcript_excerpt": clean_text[:1200] if clean_text else clean_reason[:1200]
            }
        ]

        system_prompt = build_hook_system_prompt(cat_key)

        try:
            llm = LLMClient()
            raw_res = llm.call_with_retry(system_prompt, prompt_input)
            if raw_res:
                parsed = llm.parse_json_response(raw_res)
                if isinstance(parsed, dict) and parsed.get("hook_headline"):
                    hook = ensure_hook_has_color_emojis(str(parsed["hook_headline"]).strip().strip('"\''), category=cat_key)
                    raw_title = str(parsed.get("clip_title") or clean_hook_markup(hook)).strip().strip('"\'')
                    title = clean_hook_markup(raw_title)
                    logger.info(f"AI Generated Viral Hook [{cat_key}]: \"{hook}\" (Title: \"{title}\")")
                    return {
                        "hook_headline": hook,
                        "clip_title": title
                    }
        except Exception as e:
            logger.warning(f"Failed to generate AI hook via LLM for category {cat_key}: {e}")

        # Category-aware heuristic fallback
        archetype = CATEGORY_HOOK_ARCHETYPES.get(cat_key)
        if archetype and archetype.get("formulas"):
            base_fallback = archetype["formulas"][0]
            return {
                "hook_headline": ensure_hook_has_color_emojis(base_fallback, category=cat_key),
                "clip_title": clean_hook_markup(base_fallback)
            }

        # Sentence extraction fallback
        lines = [line.strip() for line in clean_text.splitlines() if line.strip() and not line.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))]
        text_body = " ".join(lines)
        sentences = re.split(r"[.!?。！？]", text_body)
        first_sentence = sentences[0].strip() if sentences else ""
        if len(first_sentence) > 10:
            words = first_sentence.split()[:7]
            heuristic_hook = " ".join(words)
            if len(heuristic_hook) > 40:
                heuristic_hook = heuristic_hook[:40] + "..."
            heuristic_hook = ensure_hook_has_color_emojis(heuristic_hook, category=cat_key)
            return {
                "hook_headline": heuristic_hook,
                "clip_title": clean_hook_markup(heuristic_hook)
            }

        fallback = ensure_hook_has_color_emojis(video_title or "Must Watch Highlight", category=cat_key)
        return {
            "hook_headline": fallback,
            "clip_title": clean_hook_markup(fallback)
        }
