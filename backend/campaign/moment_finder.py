"""
Find exact timestamps for named campaign moments in a transcript.
Uses fuzzy string matching when start_line is provided.
Falls back to LLM for description-only moments.
"""
import logging
import difflib
import json
import re
from typing import List, Optional
from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

def find_moments_in_transcript(
    segments: List[dict],          # [{start, end, text}, ...]
    priority_moments: List[dict],  # from CampaignSchema
    duration_min: float,
    duration_max: float
) -> List[dict]:
    """
    For each priority moment, find its start/end timestamps in the transcript.
    
    Returns list of:
    {
      "moment_name": str,
      "start_sec": float,
      "end_sec": float,
      "confidence": "high" | "low",
      "matched_text": str
    }
    """
    # Universal duration sanity clamp: prevent absurd 1s-2s clips
    if duration_max < 15.0:
        duration_max = 90.0
    if duration_min < 5.0:
        duration_min = 15.0
    if duration_min >= duration_max:
        duration_max = duration_min + 45.0

    results = []
    full_text = " ".join(s['text'] for s in segments)
    
    for moment in priority_moments:
        name        = moment.get('name', 'Unknown Moment')
        description = moment.get('description', '')
        start_line  = moment.get('start_line')
        
        found = None
        
        # Method 1: Fuzzy match on start_line
        if start_line:
            found = _fuzzy_find_start_line(
                segments, start_line, duration_min, duration_max,
                moment_name=name, description=description or ""
            )
            if found:
                found['moment_name'] = name
                found['confidence']  = 'high'
        
        # Method 2: LLM fallback for description-only moments
        if not found and description:
            found = _llm_find_moment(
                segments, name, description, duration_min, duration_max
            )
            if found:
                found['moment_name'] = name
                found['confidence']  = 'low'
        
        if found:
            results.append(found)
            logger.info(f"Found moment '{name}' at {found['start_sec']:.1f}s–{found['end_sec']:.1f}s "
                       f"(confidence: {found['confidence']})")
        else:
            logger.warning(f"Could not locate moment '{name}' in transcript")
    
    return results


def _normalize_segments(segments: List[dict]) -> List[dict]:
    """Normalize segments to ensure 'start', 'end', and 'text' keys are present with float seconds."""
    if not segments:
        return []
    normalized = []
    from backend.utils.text_processor import TextProcessor
    for s in segments:
        st = s.get('start')
        et = s.get('end')
        if st is None and 'start_time' in s:
            try:
                st = TextProcessor.time_to_seconds(str(s['start_time']))
            except Exception:
                st = 0.0
        if et is None and 'end_time' in s:
            try:
                et = TextProcessor.time_to_seconds(str(s['end_time']))
            except Exception:
                et = float(st or 0.0) + 1.0
        normalized.append({
            'start': float(st if st is not None else 0.0),
            'end': float(et if et is not None else 0.0),
            'text': str(s.get('text', '')).strip()
        })
    return normalized


def find_thought_end(
    segments:     List[dict],   # full transcript segments
    start_sec:    float,        # where this moment starts
    moment_name:  str,          # e.g. "The ant and the cookie"
    description:  str,          # e.g. "bacteria buildup explanation"
    duration_min: float,        # minimum clip length (seconds)
    duration_max: float,        # maximum clip length (seconds — ceiling only)
) -> float:
    """
    Find where the speaker's thought ends — not just when the timer runs out.
    
    Layer 1: LLM analysis of transcript from start_sec onward
    Layer 2: Silence-gap snapping at the LLM-suggested end
    Layer 3: Fallback to duration_max if LLM fails
    
    Always returns a value in [start_sec + duration_min, start_sec + duration_max].
    Never cuts mid-sentence.
    """
    segments = _normalize_segments(segments)
    if duration_max < 15.0:
        duration_max = 90.0
    if duration_min < 5.0:
        duration_min = 15.0
    if duration_min >= duration_max:
        duration_max = duration_min + 45.0

    # Collect segments from start_sec forward up to duration_max + 10.0
    window_segs = [
        s for s in segments
        if s['start'] >= start_sec and s['start'] <= start_sec + duration_max + 10.0
    ]
    
    if not window_segs:
        return start_sec + duration_min

    # === Layer 1: LLM thought-completion detection ===
    llm_end = _llm_find_thought_end(
        window_segments=window_segs,
        moment_name=moment_name,
        description=description,
        start_sec=start_sec,
        duration_min=duration_min,
        duration_max=duration_max
    )

    # === Layer 2: Snap to nearest segment boundary (never cut mid-word) ===
    if llm_end is not None:
        snapped = _snap_to_segment_end(window_segs, llm_end, tolerance=3.0)
        result  = max(start_sec + duration_min, min(start_sec + duration_max, snapped))
        logger.info(f"  Content-aware end: LLM={llm_end:.1f}s → snapped={snapped:.1f}s → clamped={result:.1f}s")
        return result

    # === Layer 3: Fallback — extend to fill duration_max using transcript segments ===
    end_sec = start_sec + duration_min
    for seg in window_segs:
        if seg['end'] <= start_sec + duration_max:
            end_sec = seg['end']
        else:
            end_sec = min(seg['end'], start_sec + duration_max)
            break

    return max(start_sec + duration_min, min(start_sec + duration_max, end_sec))


def _llm_find_thought_end(
    window_segments: List[dict],
    moment_name:     str,
    description:     str,
    start_sec:       float,
    duration_min:    float,
    duration_max:    float
) -> Optional[float]:
    """
    Ask the LLM: given this portion of transcript, where does THIS specific
    thought end? Return a timestamp in seconds.
    """
    # Build transcript text with relative timestamps
    transcript_lines = []
    for seg in window_segments:
        rel_time = seg['start'] - start_sec
        transcript_lines.append(f"[+{rel_time:.1f}s] {seg['text']}")
    transcript_text = "\n".join(transcript_lines)

    prompt = f"""You are analyzing a video transcript segment to find where a specific topic ends.

The speaker starts talking about: "{moment_name}" - {description}

The transcript below starts at the moment this topic BEGINS (marked as [+0.0s]).
Find the timestamp (in seconds from the start) where the speaker finishes this specific topic and either:
- Pauses naturally (end of a thought/explanation)
- Transitions to a different topic
- Wraps up with a conclusion sentence

Constraints:
- Minimum clip length: {duration_min} seconds
- Maximum clip length: {duration_max} seconds
- The clip must end at a natural sentence break - never mid-sentence

Transcript:
{transcript_text}

Return ONLY a JSON object:
{{"end_offset_seconds": <float - seconds from the start of THIS clip where the topic naturally ends>}}

If you cannot determine a clear end, return {{"end_offset_seconds": null}}.
Return ONLY the JSON object."""

    try:
        client = LLMClient()
        response = client.call_with_retry(prompt, None, task="summarization")
        if not response:
            return None

        match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group())
        offset = data.get("end_offset_seconds")
        if offset is None:
            return None

        # Convert relative offset back to absolute
        return start_sec + float(offset)

    except Exception as e:
        logger.warning(f"LLM thought-end detection failed: {e}")
        return None


def _snap_to_segment_end(
    segments:   List[dict],
    target_sec: float,
    tolerance:  float = 3.0
) -> float:
    """
    Snap target_sec to the nearest segment END time within ±tolerance seconds.
    This ensures we never cut mid-word or mid-sentence.
    """
    best_end  = target_sec
    best_dist = float('inf')

    for seg in segments:
        dist = abs(seg['end'] - target_sec)
        if dist < best_dist and dist <= tolerance:
            best_dist = dist
            best_end  = seg['end']

    return best_end


def _fuzzy_find_start_line(
    segments: List[dict],
    start_line: str,
    duration_min: float,
    duration_max: float,
    moment_name: str = "",
    description: str = ""
) -> Optional[dict]:
    """
    Sliding-window fuzzy search across concatenated adjacent segments.
    Handles start_line phrases that span multiple Whisper segments.
    Uses content-aware thought completion for end timestamp.
    """
    if not segments or not start_line:
        return None

    start_words = len(start_line.split())
    best_ratio    = 0.0
    best_start_sec = None
    best_text      = ""

    for i in range(len(segments)):
        # Build window: accumulate segments until word count >= start_line word count
        window_text  = ""
        for j in range(i, min(i + 6, len(segments))):
            window_text += " " + segments[j]['text']
            if len(window_text.split()) >= start_words:
                break

        window_text = window_text.strip()
        ratio = difflib.SequenceMatcher(
            None,
            start_line.lower().strip(),
            window_text.lower()
        ).ratio()

        if ratio > best_ratio:
            best_ratio     = ratio
            best_start_sec = segments[i]['start']
            best_text      = window_text

    if best_ratio < 0.28 or best_start_sec is None:
        return None

    # Content-aware end detection
    end_sec = find_thought_end(
        segments=segments,
        start_sec=best_start_sec,
        moment_name=moment_name,
        description=description,
        duration_min=duration_min,
        duration_max=duration_max
    )

    return {
        'start_sec':    best_start_sec,
        'end_sec':      end_sec,
        'matched_text': best_text[:300]
    }


def _llm_find_moment(
    segments: List[dict],
    name: str,
    description: str,
    duration_min: float,
    duration_max: float
) -> Optional[dict]:
    """
    Use LLM to locate a moment in the transcript when no start_line is available.
    Returns approximate start_sec and content-aware end_sec.
    """
    if duration_max < 15.0:
        duration_max = 90.0
    if duration_min < 5.0:
        duration_min = 15.0
    if duration_min >= duration_max:
        duration_max = duration_min + 45.0

    transcript_text = "\n".join(
        f"[{s['start']:.1f}s] {s['text']}" for s in segments
    )
    
    prompt = f"""You are analyzing a video transcript to find a specific moment.

Transcript (with timestamps in seconds):
{transcript_text}

Find the moment described as: "{name}" - {description}

Return ONLY a JSON object with:
{{"start_sec": <float seconds where this moment begins>, "end_sec": <float seconds where it ends>}}

The clip should be between {duration_min} and {duration_max} seconds long.
If you cannot find this moment, return {{"start_sec": null, "end_sec": null}}.
Return ONLY the JSON object."""

    try:
        client = LLMClient()
        response = client.call_with_retry(prompt, None, task="summarization")
        if not response:
            return None
        
        cleaned = re.search(r'\{.*\}', response, re.DOTALL)
        if not cleaned:
            return None
        
        data = json.loads(cleaned.group())
        if data.get('start_sec') is None:
            return None
        
        start_sec = float(data['start_sec'])
        end_sec = find_thought_end(
            segments=segments,
            start_sec=start_sec,
            moment_name=name,
            description=description,
            duration_min=duration_min,
            duration_max=duration_max
        )
        
        # Find matched text around start_sec
        matched = next(
            (s['text'] for s in segments if abs(s['start'] - start_sec) < 2.0),
            ""
        )
        
        return {
            'start_sec':    start_sec,
            'end_sec':      end_sec,
            'matched_text': matched
        }
    except Exception as e:
        logger.error(f"LLM moment finding failed: {e}")
        return None


def auto_discover_moments(
    segments: List[dict],
    total_duration: float,
    duration_min: float = 20.0,
    duration_max: float = 90.0,
    max_clips: Optional[int] = None
) -> List[dict]:
    """
    Auto-discover high-value, coherent clip moments across the video footage
    when no priority moments are mandated or matched.
    
    Guarantees:
    - Multiple clips across long footage (e.g. 15-minute video gets 6-12 clips)
    - Clips respect duration bounds [duration_min, duration_max]
    - Thought completion using find_thought_end
    - Respects max_clips if specified
    """
    segments = _normalize_segments(segments)
    if duration_max < 15.0:
        duration_max = 90.0
    if duration_min < 5.0:
        duration_min = 15.0
    if duration_min >= duration_max:
        duration_max = duration_min + 45.0

    # Case 1: Short video (<= duration_max) -> return full video as single clip
    if total_duration <= duration_max:
        return [{
            "moment_name": "Full Video Clip",
            "start_sec": 0.0,
            "end_sec": total_duration,
            "confidence": "high",
            "matched_text": segments[0].get("text", "") if segments else ""
        }]

    # Determine target number of clips
    if max_clips and isinstance(max_clips, int) and max_clips > 0:
        target_count = max_clips
    else:
        # Calculate sensible clip count based on duration (aim for ~60-75s segments)
        target_count = max(2, min(12, int(round(total_duration / 75.0))))

    logger.info(f"Auto-discovering {target_count} moments for {total_duration:.1f}s footage (bounds: {duration_min}s-{duration_max}s)")

    discovered: List[dict] = []

    # Strategy 1: LLM-powered moment identification if transcript is available
    if segments and len(segments) >= 3:
        try:
            transcript_sample = []
            for s in segments:
                transcript_sample.append(f"[{s['start']:.1f}s] {s['text']}")
            
            transcript_text = "\n".join(transcript_sample)
            # If transcript is very large, truncate safely to fit prompt context
            if len(transcript_text) > 25000:
                transcript_text = transcript_text[:25000] + "\n[...remaining transcript truncated...]"

            prompt = f"""You are an expert short-form video editor. Analyze this transcript from a {total_duration:.1f}-second video.
Identify the {target_count} most engaging, coherent, standalone moments suitable for TikTok, Reels, and YouTube Shorts.
Spread your selections across the entire duration of the video.

Transcript:
{transcript_text}

Rules:
1. Each moment should be between {duration_min:.0f} and {duration_max:.0f} seconds.
2. Select standalone thoughts, punchlines, insightful stories, or surprising facts.
3. Start seconds should be spread across the video (not all clustered at the beginning).
4. Return ONLY a JSON array of objects with this schema:
[
  {{
    "moment_name": "Catchy 3-6 word title",
    "start_sec": <float seconds>,
    "end_sec": <float seconds>,
    "description": "Brief description of why this moment is engaging"
  }}
]"""
            client = LLMClient()
            response = client.call_with_retry(prompt, None, task="summarization")
            if response:
                cleaned = re.search(r'\[.*\]', response, re.DOTALL)
                if cleaned:
                    items = json.loads(cleaned.group())
                    if isinstance(items, list) and len(items) > 0:
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            raw_start = float(item.get('start_sec', 0.0))
                            if raw_start < 0 or raw_start >= total_duration - 5.0:
                                continue
                            
                            m_name = item.get('moment_name', f"Moment at {int(raw_start)}s")
                            m_desc = item.get('description', '')

                            # Snap to exact sentence start from segments
                            nearest_seg = min(segments, key=lambda s: abs(s['start'] - raw_start))
                            start_sec = max(0.0, float(nearest_seg['start']))

                            end_sec = find_thought_end(
                                segments=segments,
                                start_sec=start_sec,
                                moment_name=m_name,
                                description=m_desc,
                                duration_min=duration_min,
                                duration_max=duration_max
                            )
                            end_sec = min(total_duration, end_sec)

                            # Prevent excessive overlap with previously added moments
                            is_overlapping = any(
                                abs(d['start_sec'] - start_sec) < 20.0
                                for d in discovered
                            )
                            if not is_overlapping and (end_sec - start_sec) >= (duration_min * 0.8):
                                matched = nearest_seg.get('text', '')
                                discovered.append({
                                    "moment_name": m_name,
                                    "start_sec": round(start_sec, 2),
                                    "end_sec": round(end_sec, 2),
                                    "confidence": "high",
                                    "matched_text": matched
                                })
        except Exception as e:
            logger.warning(f"LLM auto-discovery failed ({e}), falling back to timeline partition")

    # Strategy 2: Timeline partition fallback (or if LLM returned fewer than target_count)
    if len(discovered) < min(target_count, 2):
        logger.info(f"Using timeline partition to discover moments (current count: {len(discovered)}/{target_count})")
        step_interval = total_duration / float(target_count)
        
        for i in range(target_count):
            ideal_start = i * step_interval
            
            # Check if an LLM discovered moment already covers this window
            window_covered = any(
                abs(d['start_sec'] - ideal_start) < (step_interval * 0.5)
                for d in discovered
            )
            if window_covered:
                continue

            if segments:
                # Find the segment closest to ideal_start
                candidates = [s for s in segments if s['start'] >= max(0.0, ideal_start - 10.0)]
                seg = candidates[0] if candidates else segments[-1]
                start_sec = max(0.0, float(seg['start']))
                if start_sec >= total_duration - 10.0:
                    continue

                moment_title = f"Highlight {len(discovered) + 1}"
                if seg.get('text'):
                    # Pick first 4-5 words of the sentence for a readable name
                    words = seg['text'].strip().split()
                    if words:
                        moment_title = " ".join(words[:5]).capitalize()
                        if len(words) > 5:
                            moment_title += "..."

                end_sec = find_thought_end(
                    segments=segments,
                    start_sec=start_sec,
                    moment_name=moment_title,
                    description="Auto-partitioned moment",
                    duration_min=duration_min,
                    duration_max=duration_max
                )
                end_sec = min(total_duration, end_sec)
                matched = seg.get('text', '')
            else:
                start_sec = ideal_start
                end_sec = min(total_duration, start_sec + min(duration_max, 60.0))
                moment_title = f"Moment {len(discovered) + 1}"
                matched = ""

            if (end_sec - start_sec) >= (duration_min * 0.7):
                discovered.append({
                    "moment_name": moment_title,
                    "start_sec": round(start_sec, 2),
                    "end_sec": round(end_sec, 2),
                    "confidence": "high" if segments else "low",
                    "matched_text": matched
                })

    # Sort all discovered moments by chronological start_sec
    discovered.sort(key=lambda m: m['start_sec'])
    if max_clips and isinstance(max_clips, int) and max_clips > 0:
        discovered = discovered[:max_clips]

    logger.info(f"Auto-discovery completed: found {len(discovered)} moments across {total_duration:.1f}s")
    return discovered

