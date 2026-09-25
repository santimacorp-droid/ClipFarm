"""
Viral Caption Generator for Short-Form Video Clips
Supports modern social media caption styles (Hormozi Yellow, Neon Green, Neon Cyan, Clean Minimalist).
Produces Advanced SubStation Alpha (.ass) files with word/character-level highlight styling and time-shifted .srt files.
"""

import os
import re
import math
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

def get_system_font_name() -> str:
    """Find a high-quality bold sans-serif font available on the host system."""
    import shutil
    import subprocess
    candidates = ["Montserrat", "Arial", "DejaVu Sans", "Helvetica", "Noto Sans", "Noto Sans CJK SC", "sans-serif"]
    if shutil.which("fc-list"):
        try:
            res = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, errors="ignore")
            installed = set(f.strip() for line in res.stdout.splitlines() for f in line.split(","))
            for cand in candidates:
                if cand in installed:
                    return cand
        except Exception:
            pass
    return "DejaVu Sans"

DEFAULT_FONT_NAME = get_system_font_name()

# Preset Caption Styles for ASS
CAPTION_STYLES = {
    "hormozi_yellow": {
        "name": "Hormozi Yellow",
        "font_name": DEFAULT_FONT_NAME,
        "font_size": 72,
        "primary_color": "&H00FFFFFF&",     # Pure White
        "highlight_color": "&H0000FFFF&",   # Electric Golden Yellow (BGR: 0x0000FFFF)
        "outline_color": "&H00000000&",     # Solid Black
        "back_color": "&H80000000&",        # Semi-transparent Shadow
        "bold": -1,                         # 1 = True in ASS
        "italic": 0,
        "outline": 5.0,
        "shadow": 2.0,
        "border_style": 1,                  # 1 = Outline + Shadow
        "alignment": 2,                     # 2 = Bottom-Center
        "margin_v": 90,
        "uppercase": True,
        "words_per_group": 4,               # 3-5 words per punchy line
        "cjk_chars_per_group": 8,           # 6-10 CJK chars per punchy line
    },
    "neon_green": {
        "name": "Neon Green",
        "font_name": DEFAULT_FONT_NAME,
        "font_size": 72,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H0000FF00&",   # Neon Green
        "outline_color": "&H00000000&",
        "back_color": "&H80000000&",
        "bold": -1,
        "italic": 0,
        "outline": 5.0,
        "shadow": 2.0,
        "border_style": 1,
        "alignment": 2,
        "margin_v": 90,
        "uppercase": True,
        "words_per_group": 4,
        "cjk_chars_per_group": 8,
    },
    "neon_cyan": {
        "name": "Neon Cyan",
        "font_name": DEFAULT_FONT_NAME,
        "font_size": 72,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H00FFFF00&",   # Electric Cyan (BGR)
        "outline_color": "&H00000000&",
        "back_color": "&H80000000&",
        "bold": -1,
        "italic": 0,
        "outline": 5.0,
        "shadow": 2.0,
        "border_style": 1,
        "alignment": 2,
        "margin_v": 90,
        "uppercase": True,
        "words_per_group": 4,
        "cjk_chars_per_group": 8,
    },
    "minimal_box": {
        "name": "Clean Minimalist Box",
        "font_name": DEFAULT_FONT_NAME,
        "font_size": 52,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H00FFFFFF&",
        "outline_color": "&H00000000&",
        "back_color": "&HA0000000&",        # Dark Translucent Box
        "bold": 0,
        "italic": 0,
        "outline": 1.0,
        "shadow": 0.0,
        "border_style": 3,                  # 3 = Opaque/Translucent Bounding Box
        "alignment": 2,
        "margin_v": 60,
        "uppercase": False,
        "words_per_group": 6,
        "cjk_chars_per_group": 12,
    },
    "none": {
        "name": "Clean Subtitles (No Animation)",
        "font_name": DEFAULT_FONT_NAME,
        "font_size": 56,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H00FFFFFF&",
        "outline_color": "&H00000000&",
        "back_color": "&H80000000&",
        "bold": -1,
        "italic": 0,
        "outline": 4.0,
        "shadow": 1.5,
        "border_style": 1,
        "alignment": 2,
        "margin_v": 80,
        "uppercase": False,
        "words_per_group": 5,
        "cjk_chars_per_group": 10,
    }
}


def _is_cjk_char(ch: str) -> bool:
    """Check if a character belongs to CJK unicode ranges."""
    if not ch:
        return False
    cp = ord(ch[0])
    return (
        (0x4E00 <= cp <= 0x9FFF) or   # CJK Unified Ideographs
        (0x3400 <= cp <= 0x4DBF) or   # CJK Unified Ideographs Extension A
        (0x20000 <= cp <= 0x2A6DF) or # Extension B
        (0xF900 <= cp <= 0xFAFF) or   # CJK Compatibility Ideographs
        (0x3040 <= cp <= 0x309F) or   # Hiragana
        (0x30A0 <= cp <= 0x30FF) or   # Katakana
        (0xAC00 <= cp <= 0xD7AF)      # Hangul Syllables
    )


def _has_cjk(text: str) -> bool:
    """Check if text contains any CJK character."""
    return any(_is_cjk_char(ch) for ch in text)


def _tokenize_text(text: str) -> List[str]:
    """
    Tokenize text into words/characters with proper punctuation binding.
    - Keeps English/Latin words intact with their trailing punctuation attached (e.g., 'Depot,' not 'Depot' + ',')
    - Breaks CJK into character tokens, attaching punctuation to preceding characters.
    """
    if not text:
        return []
    
    # If text has no CJK characters, simple whitespace splitting keeps words and trailing punctuation together
    if not _has_cjk(text):
        return [w for w in text.split() if w]

    # For mixed / CJK text: break into tokens while keeping trailing punctuation attached
    raw_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]|[a-zA-Z0-9_\'-]+|[^\s\w]'
    raw_tokens = [t.strip() for t in re.findall(raw_pattern, text) if t.strip()]
    if not raw_tokens:
        return [w for w in text.split() if w]
    
    # Merge trailing punctuation into previous token
    merged = []
    punct_regex = re.compile(r'^[.,!?:;，。！？；、“”‘’（）\(\)\[\]\<\>…\-]+$')
    for tok in raw_tokens:
        if merged and punct_regex.match(tok):
            merged[-1] += tok
        else:
            merged.append(tok)
    return merged


def _resolve_overlapping_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolves segment overlaps:
    1. If segments belong to different speakers, allows simultaneous dual-track playback.
    2. Within the same speaker (or without diarization):
       - If cues start virtually simultaneously (<= 0.15s), merge them if short, or split interval.
       - If cues overlap, clamp the earlier segment's display end time to the start of the next segment.
         Start timestamps are strictly anchored to the audio timestamp when the speaker spoke,
         preventing artificial delay drift.
    3. Preserves 'speaker' and 'words' metadata.
    4. Enforces strictly non-overlapping intervals within each speaker track.
    """
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda s: (float(s.get('start', 0)), float(s.get('end', 0))))
    resolved: List[Dict[str, Any]] = []

    for seg in sorted_segs:
        raw_start = max(0.0, float(seg.get('start', 0.0)))
        raw_end = max(raw_start + 0.1, float(seg.get('end', 0.0)))
        text = str(seg.get('text', '')).strip()
        if not text or raw_end <= raw_start:
            continue

        spk = seg.get('speaker', 'SPEAKER_00')

        # Find the most recent segment on the SAME speaker track
        prev_same_spk = None
        for r in reversed(resolved):
            if r.get('speaker', 'SPEAKER_00') == spk:
                prev_same_spk = r
                break

        if prev_same_spk and raw_start < prev_same_spk['end']:
            prev = prev_same_spk
            # Case 1: Starts at virtually the same timestamp (simultaneous cues on same speaker)
            if raw_start <= prev['start'] + 0.15:
                # Merge into a single line if short enough
                if len(prev['text'].split()) + len(text.split()) <= 6:
                    prev['text'] = f"{prev['text']} {text}".strip()
                    prev['end'] = max(prev['end'], raw_end)
                    if 'words' in prev and 'words' in seg:
                        prev['words'] = prev.get('words', []) + seg.get('words', [])
                    continue
                else:
                    span = max(0.4, max(prev['end'], raw_end) - prev['start'])
                    mid = prev['start'] + (span / 2.0)
                    prev['end'] = round(mid, 3)
                    start = round(mid, 3)
                    end = round(max(mid + 0.2, raw_end), 3)
            else:
                # Sequential cues from the same speaker:
                # The speaker begins speaking the new cue at raw_start.
                # Clamp previous cue's display end to the start of the new cue.
                # Ensure previous cue has a minimal visible duration of at least 0.1s.
                prev['end'] = round(min(prev['end'], max(prev['start'] + 0.1, raw_start)), 3)
                start = round(max(raw_start, prev['end']), 3)
                end = round(max(start + 0.2, raw_end), 3)
                if 'words' in prev:
                    for w in prev['words']:
                        w['end'] = min(float(w.get('end', 0.0)), prev['end'])
        else:
            start = round(raw_start, 3)
            end = round(raw_end, 3)

        # Shift word timestamps if start was shifted
        seg_words = seg.get('words')
        if seg_words:
            delta = start - raw_start
            if abs(delta) > 0.001:
                shifted = []
                for w in seg_words:
                    shifted.append({
                        'word': w.get('word', ''),
                        'start': round(float(w.get('start', 0.0)) + delta, 3),
                        'end': round(float(w.get('end', 0.0)) + delta, 3)
                    })
                seg_words = shifted

        if end > start + 0.05:
            entry = {
                'start': round(start, 3),
                'end': round(end, 3),
                'text': text
            }
            if 'speaker' in seg:
                entry['speaker'] = seg['speaker']
            if seg_words:
                entry['words'] = seg_words
            resolved.append(entry)

    # Final enforcement within each speaker track
    for spk_val in set(r.get('speaker', 'SPEAKER_00') for r in resolved):
        spk_indices = [i for i, r in enumerate(resolved) if r.get('speaker', 'SPEAKER_00') == spk_val]
        for idx in range(len(spk_indices) - 1):
            curr_idx = spk_indices[idx]
            next_idx = spk_indices[idx + 1]
            if resolved[curr_idx]['end'] > resolved[next_idx]['start']:
                resolved[curr_idx]['end'] = resolved[next_idx]['start']
            if resolved[curr_idx]['end'] <= resolved[curr_idx]['start']:
                resolved[curr_idx]['end'] = round(resolved[curr_idx]['start'] + 0.05, 3)
                resolved[next_idx]['start'] = max(resolved[next_idx]['start'], resolved[curr_idx]['end'])

    return [r for r in resolved if r['end'] > r['start'] + 0.05]


def _clean_emojis_for_ass(text: str) -> str:
    """
    Sanitizes raw multi-byte Unicode emojis and symbols that corrupt libass font rasterization.
    Converts common viral emojis into clean universal typographic marks or strips them cleanly.
    """
    if not text:
        return ""
    # Map high-frequency viral emojis to clean typographic symbols
    emoji_map = {
        '🔥': '★',
        '⚡': '★',
        '✨': '★',
        '💥': '★',
        '🚨': '▶',
        '👉': '▶',
        '👇': '▼',
        '👆': '▲',
        '💀': '',
        '😳': '',
        '🤯': '',
        '👀': '',
        '🎬': '',
        '💯': ' 100 ',
    }
    cleaned = text
    for em, replacement in emoji_map.items():
        cleaned = cleaned.replace(em, replacement)
    
    # Strip any remaining unmapped multi-byte surrogate / supplemental emojis
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)
    cleaned = re.sub(r'[\u2600-\u26ff\u2700-\u27bf]', '', cleaned)
    # Clean up double spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _clean_ass_tags(text: str) -> str:
    """Strip ASS override tags {\\...}."""
    return re.sub(r'\{[^\}]*\}', '', text)


def _join_tokens(tokens: List[str]) -> str:
    """
    Joins tokens naturally:
    - Adds spaces between Latin words
    - Adds spaces between CJK and Latin boundaries (pangu spacing)
    - No spaces between adjacent CJK characters or trailing punctuation
    - Strips ASS override tags when inspecting token boundaries
    """
    if not tokens:
        return ""
    result = [tokens[0]]
    for i in range(1, len(tokens)):
        prev = tokens[i - 1]
        curr = tokens[i]
        clean_prev = _clean_ass_tags(prev)
        clean_curr = _clean_ass_tags(curr)
        prev_char = clean_prev[-1] if clean_prev else ""
        curr_char = clean_curr[0] if clean_curr else ""

        prev_is_cjk = _is_cjk_char(prev_char)
        curr_is_cjk = _is_cjk_char(curr_char)
        is_punct = bool(re.match(r'^[.,!?:;，。！？；、“”‘’（）\(\)\[\]\<\>]+$', clean_curr))
        prev_is_open_punct = bool(re.match(r'^[“‘（\(\[\<]+$', clean_prev))

        if is_punct or prev_is_open_punct:
            result.append(curr)
        elif prev_is_cjk and curr_is_cjk:
            result.append(curr)
        else:
            result.append(" " + curr)
    return "".join(result)


def _normalize_ass_color(color: str) -> str:
    """Ensure ASS color tag has standard &H...& formatting."""
    c = color.strip()
    if c.startswith('&H') and not c.endswith('&'):
        return c + '&'
    return c


def _parse_time_to_seconds(t_str: Any) -> float:
    """Converts '00:01:23,456' or '00:01:23.456' or '01:23.456' or float string to seconds."""
    if isinstance(t_str, (int, float)):
        return max(0.0, float(t_str))
    s = str(t_str).strip().replace(',', '.')
    # Strip any trailing cue settings like "align:start position:0%"
    s = s.split()[0]
    parts = s.split(':')
    try:
        if len(parts) == 3:
            return max(0.0, int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2]))
        elif len(parts) == 2:
            return max(0.0, int(parts[0]) * 60 + float(parts[1]))
        return max(0.0, float(s))
    except ValueError:
        return 0.0


def _seconds_to_ass_time(sec: float) -> str:
    """Converts seconds (float) to ASS time format: H:MM:SS.cs (centiseconds)."""
    if sec < 0:
        sec = 0.0
    total_cs = int(round(sec * 100.0))
    h = total_cs // 360000
    m = (total_cs % 360000) // 6000
    s = (total_cs % 6000) // 100
    cs = total_cs % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _seconds_to_srt_time(sec: float) -> str:
    """Converts seconds (float) to SRT time format: HH:MM:SS,mmm."""
    if sec < 0:
        sec = 0.0
    total_ms = int(round(sec * 1000.0))
    h = total_ms // 3600000
    m = (total_ms % 3600000) // 60000
    s = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ViralCaptionGenerator:
    """Generates ASS & SRT caption files tailored for viral short-form clips."""

    @staticmethod
    def parse_srt_file(srt_path: Path) -> List[Dict[str, Any]]:
        """Parses an SRT file into a list of subtitle segments."""
        if not srt_path.exists():
            return []
        
        segments = []
        try:
            with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            raw_blocks = re.split(r'\n\s*\n', content.strip())
            for block in raw_blocks:
                lines = [line.strip() for line in block.splitlines() if line.strip()]
                if len(lines) >= 2:
                    time_line_idx = -1
                    for idx, line in enumerate(lines[:3]):
                        if '-->' in line:
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
                        segments.append({
                            'start': start_sec,
                            'end': end_sec,
                            'text': clean_text
                        })
        except Exception as e:
            logger.error(f"Failed to parse SRT file {srt_path}: {e}")

        return segments

    @staticmethod
    def get_clip_segments(
        all_segments: List[Dict[str, Any]],
        clip_start_sec: Any,
        clip_end_sec: Any
    ) -> List[Dict[str, Any]]:
        """
        Filters, shifts, and deduplicates subtitle segments to be relative to the clip start (00:00:00).
        Preserves speaker and word timestamps. Discards pre-clip/post-clip words to eliminate 0.00ms bursts.
        """
        clip_start = _parse_time_to_seconds(clip_start_sec)
        clip_end = _parse_time_to_seconds(clip_end_sec)
        if clip_end <= clip_start:
            return []

        raw_clip_segments = []
        for seg in all_segments:
            seg_start = _parse_time_to_seconds(seg.get('start', 0.0))
            seg_end = _parse_time_to_seconds(seg.get('end', 0.0))

            # Segment is entirely outside the clip window
            if seg_end <= clip_start + 0.05 or seg_start >= clip_end - 0.05:
                continue

            raw_words = seg.get('words') or []
            if raw_words:
                shifted_words = []
                for w in raw_words:
                    w_s = _parse_time_to_seconds(w.get('start', 0.0))
                    w_e = _parse_time_to_seconds(w.get('end', 0.0))

                    # Drop words that ended before clip start or start after clip end
                    if w_e <= clip_start + 0.05 or w_s >= clip_end - 0.05:
                        continue

                    # Clip boundaries
                    rel_w_s = max(0.0, w_s - clip_start)
                    rel_w_e = min(clip_end - clip_start, max(rel_w_s + 0.05, w_e - clip_start))

                    word_text = str(w.get('word', '')).strip()
                    if word_text:
                        shifted_words.append({
                            'word': word_text,
                            'start': round(rel_w_s, 3),
                            'end': round(rel_w_e, 3)
                        })

                if not shifted_words:
                    continue

                rel_start = shifted_words[0]['start']
                rel_end = shifted_words[-1]['end']
                clean_text = _join_tokens([w['word'] for w in shifted_words])
                if not clean_text:
                    continue

                item = {
                    'start': rel_start,
                    'end': rel_end,
                    'text': clean_text,
                    'words': shifted_words
                }
                if 'speaker' in seg:
                    item['speaker'] = seg['speaker']
                raw_clip_segments.append(item)
            else:
                # SRT cues without word-level timestamps
                overlap_dur = min(seg_end, clip_end) - max(seg_start, clip_start)
                if overlap_dur < 0.2:
                    continue

                rel_start = max(0.0, seg_start - clip_start)
                rel_end = min(clip_end - clip_start, seg_end - clip_start)
                if rel_end <= rel_start + 0.05:
                    continue

                clean_text = str(seg.get('text', '')).strip()
                if not clean_text:
                    continue

                item = {
                    'start': round(rel_start, 3),
                    'end': round(rel_end, 3),
                    'text': clean_text
                }
                if 'speaker' in seg:
                    item['speaker'] = seg['speaker']
                raw_clip_segments.append(item)

        return _resolve_overlapping_segments(raw_clip_segments)

    @classmethod
    def generate_clip_srt(
        cls,
        source_srt_path: Optional[Path],
        clip_start: Any,
        clip_end: Any,
        output_srt_path: Path,
        words_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Extracts and writes a time-shifted SRT file for a single clip."""
        try:
            if words_data:
                all_segs = words_data
            else:
                all_segs = cls.parse_srt_file(Path(source_srt_path)) if source_srt_path else []
            clip_segs = cls.get_clip_segments(all_segs, clip_start, clip_end)
            output_srt_path = Path(output_srt_path)
            output_srt_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                for idx, seg in enumerate(clip_segs, 1):
                    f.write(f"{idx}\n")
                    f.write(f"{_seconds_to_srt_time(seg['start'])} --> {_seconds_to_srt_time(seg['end'])}\n")
                    f.write(f"{seg['text']}\n\n")
            return True
        except Exception as e:
            logger.error(f"Failed to generate clip SRT: {e}")
            return False

    @classmethod
    def generate_clip_ass(
        cls,
        source_srt_path: Optional[Path] = None,
        clip_start: Any = 0.0,
        clip_end: Any = 999999.0,
        output_ass_path: Optional[Path] = None,
        style_key: str = "hormozi_yellow",
        hook_title: Optional[str] = None,
        show_hook_banner: bool = True,
        video_width: int = 1920,
        video_height: int = 1080,
        words_data: Optional[List[Dict[str, Any]]] = None,
        word_segments: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> bool:
        """
        Generates a viral styled ASS subtitle file with dynamic active-word highlights,
        group chunking to prevent horizontal overflow, multi-speaker dual track rendering,
        and an optional Top Hook Headline Banner.
        """
        try:
            if source_srt_path is None and 'srt_path' in kwargs:
                source_srt_path = kwargs['srt_path']
            if 'clip_start_seconds' in kwargs:
                clip_start = kwargs['clip_start_seconds']
            if 'clip_end_seconds' in kwargs:
                clip_end = kwargs['clip_end_seconds']
            if 'style' in kwargs:
                style_key = kwargs['style']
            if output_ass_path is None and 'output_ass_path' in kwargs:
                output_ass_path = kwargs['output_ass_path']
            if words_data is None:
                words_data = word_segments or kwargs.get('word_segments')

            if output_ass_path is None:
                raise ValueError("output_ass_path is required")
            output_ass_path = Path(output_ass_path)
            cfg = CAPTION_STYLES.get(style_key, CAPTION_STYLES["hormozi_yellow"])
            clip_start_sec = _parse_time_to_seconds(clip_start)
            clip_end_sec = _parse_time_to_seconds(clip_end)

            if words_data is None and source_srt_path:
                source_srt_path = Path(source_srt_path)
                candidate_files = [
                    source_srt_path.parent / f"{source_srt_path.stem}_words.json",
                    source_srt_path.parent / "step2_words.json",
                    source_srt_path.parent / "words.json",
                    source_srt_path.parent.parent / "metadata" / "step2_words.json",
                    source_srt_path.parent.parent / "metadata" / "words.json",
                ]
                for cand in candidate_files:
                    if cand.exists():
                        try:
                            with open(cand, 'r', encoding='utf-8') as f:
                                loaded_data = json.load(f)
                                if isinstance(loaded_data, list) and loaded_data:
                                    words_data = loaded_data
                                    logger.info(f"[AutoClip] Loaded companion words data from {cand}")
                                    break
                        except Exception as e:
                            logger.debug(f"Failed to read companion words {cand}: {e}")

            if words_data:
                all_segs = words_data
            elif source_srt_path and Path(source_srt_path).exists():
                all_segs = cls.parse_srt_file(Path(source_srt_path))
            else:
                all_segs = []

            clip_segs = cls.get_clip_segments(all_segs, clip_start_sec, clip_end_sec)
            
            # Responsive font size & margin adjustment based on vertical (9:16) vs landscape
            is_vertical = video_height > video_width
            if is_vertical:
                scale_factor = video_width / 1080.0
                base_font_size = max(32, int(cfg.get("font_size", 68) * scale_factor))
                # Safe-Zone positioning: Elevate dialogue above TikTok/Reels/Shorts bottom 400px UI overlay
                margin_v = max(240, int(580 * (video_height / 1920.0)))
                hook_font_size = max(32, int(52 * scale_factor))
                # Top Safe-Zone: Below mobile notch/status bar and top search/feed tabs
                hook_margin_v = max(80, int(220 * (video_height / 1920.0)))
            else:
                scale_factor = video_height / 1080.0
                base_font_size = max(28, int(cfg.get("font_size", 68) * scale_factor))
                margin_v = max(40, int(cfg.get("margin_v", 90) * scale_factor))
                hook_font_size = max(28, int(52 * scale_factor))
                hook_margin_v = max(30, int(60 * scale_factor))

            second_speaker_margin_v = margin_v + base_font_size + 20

            primary_color = _normalize_ass_color(cfg["primary_color"])
            highlight_color = _normalize_ass_color(cfg["highlight_color"])
            outline_color = _normalize_ass_color(cfg["outline_color"])
            back_color = _normalize_ass_color(cfg["back_color"])

            header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{cfg['font_name']},{base_font_size},{primary_color},{highlight_color},{outline_color},{back_color},{cfg['bold']},{cfg['italic']},0,0,100,100,1,0,{cfg['border_style']},{cfg['outline']},{cfg['shadow']},{cfg['alignment']},40,40,{margin_v},1
Style: SecondSpeaker,{cfg['font_name']},{base_font_size},{primary_color},{highlight_color},{outline_color},{back_color},{cfg['bold']},{cfg['italic']},0,0,100,100,1,0,{cfg['border_style']},{cfg['outline']},{cfg['shadow']},{cfg['alignment']},40,40,{second_speaker_margin_v},1
Style: HookTitle,{cfg['font_name']},{hook_font_size},&H00FFFFFF&,&H00FFFFFF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,1,0,1,5.0,2.0,8,40,40,{hook_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            dialogue_lines = []
            words_per_group = cfg.get("words_per_group", 3)
            cjk_chars_per_group = cfg.get("cjk_chars_per_group", 6)
            is_uppercase = cfg.get("uppercase", True)
            clip_total_duration = max(1.0, clip_end_sec - clip_start_sec)

            # Emit HookTitle dialogue line if hook banner is requested in ASS
            if show_hook_banner and hook_title:
                clean_hook = _clean_emojis_for_ass(hook_title.strip())
                if clean_hook:
                    if is_uppercase and not _has_cjk(clean_hook):
                        clean_hook = clean_hook.upper()
                    hook_end_time = min(clip_total_duration, 3.0)
                    dialogue_lines.append(
                        f"Dialogue: 1,{_seconds_to_ass_time(0.0)},{_seconds_to_ass_time(hook_end_time)},HookTitle,,0,0,0,,{clean_hook}"
                    )

            for seg in clip_segs:
                seg_text = _clean_emojis_for_ass(seg['text'].strip())
                if not seg_text:
                    continue
                
                has_cjk = _has_cjk(seg_text)
                if is_uppercase and not has_cjk:
                    seg_text = seg_text.upper()

                tokens = _tokenize_text(seg_text)
                if not tokens:
                    continue

                # Deduplicate consecutive repeating tokens (e.g. Whisper stutter/hallucination loops)
                deduped_tokens: List[str] = []
                for tok in tokens:
                    if len(deduped_tokens) >= 2 and deduped_tokens[-1].lower() == tok.lower() and deduped_tokens[-2].lower() == tok.lower():
                        continue
                    deduped_tokens.append(tok)
                tokens = deduped_tokens if deduped_tokens else tokens

                # Select style based on speaker label
                style = "Default"
                if seg.get('speaker') and seg['speaker'] != 'SPEAKER_00':
                    style = "SecondSpeaker"

                seg_start = float(seg['start'])
                seg_end = max(seg_start + 0.2, float(seg['end']))
                seg_duration = max(0.2, seg_end - seg_start)
                total_tokens = len(tokens)
                seg_words = seg.get('words') or []

                # Group chunking: 3-4 words for natural, readable short-form captions
                group_limit = cjk_chars_per_group if has_cjk else words_per_group
                groups = [tokens[i:i + group_limit] for i in range(0, total_tokens, group_limit)]

                # Check if word timestamps match tokens 1:1
                has_word_timing = bool(seg_words and len(seg_words) == total_tokens)

                current_group_start = seg_start
                token_cursor = 0
                for group in groups:
                    group_len = len(group)
                    group_words_slice = seg_words[token_cursor:token_cursor + group_len] if has_word_timing else []
                    
                    if has_word_timing and group_words_slice:
                        raw_g_start = float(group_words_slice[0]['start'])
                        raw_g_end = float(group_words_slice[-1]['end'])
                        g_start = max(current_group_start, raw_g_start)
                        g_end = max(g_start + 0.2, min(seg_end, max(raw_g_end, g_start + (group_len * 0.1))))
                    else:
                        group_dur = max(0.2, seg_duration * (group_len / total_tokens))
                        g_start = current_group_start
                        g_end = min(seg_end, current_group_start + group_dur)
                        if g_end <= g_start + 0.1:
                            g_end = g_start + 0.2

                    # If plain subtitles or single token: render cleanly without per-word cycling
                    if highlight_color == primary_color or group_len <= 1:
                        line_text = _join_tokens(group)
                        dialogue_lines.append(
                            f"Dialogue: 0,{_seconds_to_ass_time(g_start)},{_seconds_to_ass_time(g_end)},{style},,0,0,0,,{line_text}"
                        )
                    else:
                        # Build strictly partition-based word intervals [t_start, t_end]
                        # guaranteeing ZERO overlap between words in the same group
                        word_starts: List[float] = []
                        if has_word_timing and group_words_slice:
                            cur_w_start = g_start
                            for w_idx in range(group_len):
                                raw_w_s = float(group_words_slice[w_idx]['start'])
                                if w_idx == 0:
                                    w_s = max(g_start, raw_w_s)
                                else:
                                    w_s = max(cur_w_start + 0.08, raw_w_s)
                                # Ensure room for remaining words
                                remaining_words = group_len - 1 - w_idx
                                max_allowed = g_end - (remaining_words * 0.08)
                                if w_s > max_allowed:
                                    w_s = max(cur_w_start + 0.05, max_allowed)
                                word_starts.append(w_s)
                                cur_w_start = w_s
                        else:
                            token_dur = (g_end - g_start) / group_len
                            for w_idx in range(group_len):
                                word_starts.append(g_start + (w_idx * token_dur))

                        for w_idx, current_tok in enumerate(group):
                            w_start = word_starts[w_idx]
                            w_end = word_starts[w_idx + 1] if w_idx < group_len - 1 else g_end
                            if w_end <= w_start:
                                w_end = w_start + 0.08

                            rendered_tokens = []
                            for j, tok in enumerate(group):
                                if j == w_idx:
                                    rendered_tokens.append(f"{{\\c{highlight_color}}}{tok}{{\\c{primary_color}}}")
                                else:
                                    rendered_tokens.append(tok)

                            line_text = _join_tokens(rendered_tokens)
                            dialogue_lines.append(
                                f"Dialogue: 0,{_seconds_to_ass_time(w_start)},{_seconds_to_ass_time(w_end)},{style},,0,0,0,,{line_text}"
                            )

                    token_cursor += group_len
                    current_group_start = g_end

            output_ass_path = Path(output_ass_path)
            output_ass_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_ass_path, 'w', encoding='utf-8') as f:
                f.write(header)
                f.write('\n'.join(dialogue_lines) + '\n')

            logger.info(f"Successfully generated viral ASS captions: {output_ass_path} ({len(dialogue_lines)} cues)")
            return True

        except Exception as e:
            logger.error(f"Failed to generate ASS caption file: {e}")
            return False

