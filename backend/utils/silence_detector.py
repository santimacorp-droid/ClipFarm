"""
Audio Boundary & Silence Snapper
Detects natural speech pauses and sentence boundaries using FFmpeg silencedetect
and subtitle analysis to prevent cutting speakers mid-sentence or mid-word.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Configurable boundary snap windows
BOUNDARY_SNAP_START_WINDOW = 1.5   # seconds — stay tight at start
BOUNDARY_SNAP_END_WINDOW = 8.0     # seconds — look further at end to complete sentences


def extend_to_sentence_boundary(
    end_sec: float,
    srt_words: Any,
    tolerance_sec: float = 12.0
) -> float:
    """
    Given an end timestamp, look ahead up to tolerance_sec in the word-level transcript
    to find the nearest sentence-ending punctuation or natural pause.
    Returns the adjusted end time. Never shortens the clip.
    
    srt_words: list of dicts with keys ('word'/'text', 'start', 'end') or Path to an SRT file
    """
    sentence_enders = {'.', '?', '!', '...', '。', '！', '？'}
    search_end = end_sec + tolerance_sec
    best_end = end_sec

    parsed_words = []
    if isinstance(srt_words, (str, Path)):
        p = Path(srt_words)
        if p.exists():
            try:
                import pysrt
                subs = pysrt.open(str(p), encoding='utf-8')
                for sub in subs:
                    st = sub.start.ordinal / 1000.0
                    et = sub.end.ordinal / 1000.0
                    raw_text = (sub.text or "").strip()
                    tokens = [w for w in re.split(r'(\s+)', raw_text) if w and not w.isspace()]
                    if tokens:
                        token_dur = max(0.05, (et - st) / len(tokens))
                        for i, tok in enumerate(tokens):
                            w_st = st + (i * token_dur)
                            w_et = min(et, w_st + token_dur)
                            parsed_words.append({'word': tok, 'start': w_st, 'end': w_et})
            except Exception as parse_err:
                logger.debug(f"Failed to parse SRT file in extend_to_sentence_boundary: {parse_err}")
    elif isinstance(srt_words, list):
        for item in srt_words:
            if isinstance(item, dict):
                w_text = item.get('word') or item.get('text') or ''
                w_start = item.get('start', item.get('startTime', 0.0))
                w_end = item.get('end', item.get('endTime', 0.0))
                parsed_words.append({'word': str(w_text), 'start': float(w_start), 'end': float(w_end)})

    if not parsed_words:
        return end_sec

    for i, word_entry in enumerate(parsed_words):
        word_start = word_entry.get('start', 0.0)
        word_end = word_entry.get('end', 0.0)
        word_text = word_entry.get('word', '').strip()

        # Only look within tolerance window
        if word_start < end_sec - 1.0:
            continue
        if word_start > search_end:
            break

        # If this word ends with sentence-ending punctuation, this is a valid stop point
        if any(word_text.endswith(p) for p in sentence_enders):
            best_end = word_end + 0.15  # tiny buffer after the last word
            break

        # If there is a natural pause >= 0.4s between consecutive words in lookahead window
        if i + 1 < len(parsed_words):
            next_start = parsed_words[i + 1].get('start', 0.0)
            if word_start >= end_sec and (next_start - word_end) >= 0.4:
                best_end = word_end + 0.15
                break

    return max(end_sec, round(best_end, 3))


class AudioBoundarySnapper:
    """Snaps raw timestamps to the nearest natural audio silence or sentence end."""

    @staticmethod
    def detect_silence_intervals(
        video_path: Any,
        search_start_sec: float,
        search_duration_sec: float,
        noise_threshold_db: int = -30,
        min_silence_duration: float = 0.25
    ) -> List[Tuple[float, float]]:
        """
        Uses FFmpeg silencedetect to find silence intervals [start, end] in seconds
        within the specified window of the video.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return []

        search_start = max(0.0, search_start_sec)
        cmd = [
            "ffmpeg", "-v", "info",
            "-ss", str(search_start),
            "-t", str(search_duration_sec),
            "-i", str(video_path),
            "-af", f"silencedetect=n={noise_threshold_db}dB:d={min_silence_duration}",
            "-f", "null", "-"
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            output = res.stderr

            silence_starts = []
            silence_ends = []

            for line in output.splitlines():
                if "silence_start:" in line:
                    m = re.search(r"silence_start:\s*([0-9.]+)", line)
                    if m:
                        silence_starts.append(search_start + float(m.group(1)))
                elif "silence_end:" in line:
                    m = re.search(r"silence_end:\s*([0-9.]+)", line)
                    if m:
                        silence_ends.append(search_start + float(m.group(1)))

            intervals = []
            for s, e in zip(silence_starts, silence_ends):
                if e > s:
                    intervals.append((s, e))
            return intervals
        except Exception as e:
            logger.warning(f"Silence detection failed on {video_path}: {e}")
            return []

    @classmethod
    def snap_start_time(
        cls,
        video_path: Any,
        raw_start_sec: float,
        search_window: float = BOUNDARY_SNAP_START_WINDOW,
        noise_threshold_db: int = -30
    ) -> float:
        """
        Snaps start_time forward or backward to the nearest silence pause or sentence start.
        """
        video_path = Path(video_path)
        window_start = max(0.0, raw_start_sec - search_window)
        window_dur = search_window * 2.0

        intervals = cls.detect_silence_intervals(
            video_path=video_path,
            search_start_sec=window_start,
            search_duration_sec=window_dur,
            noise_threshold_db=noise_threshold_db
        )

        if not intervals:
            return raw_start_sec

        # Find the silence interval closest to raw_start_sec
        best_time = raw_start_sec
        min_dist = float("inf")

        for s_start, s_end in intervals:
            # When cutting in, starting right as silence ends (speech begins) is ideal
            dist = abs(s_end - raw_start_sec)
            if dist < min_dist and dist <= search_window:
                min_dist = dist
                best_time = s_end

        return round(best_time, 3)

    @classmethod
    def snap_end_time(
        cls,
        video_path: Any,
        raw_end_sec: float,
        search_window: float = BOUNDARY_SNAP_END_WINDOW,
        noise_threshold_db: int = -28
    ) -> float:
        """
        Snaps end_time to the nearest following silence (after sentence conclusion).
        Uses wider lookahead (up to BOUNDARY_SNAP_END_WINDOW) to avoid cutting speech mid-sentence.
        """
        video_path = Path(video_path)
        window_start = max(0.0, raw_end_sec - 0.5)
        window_dur = search_window + 1.0

        intervals = cls.detect_silence_intervals(
            video_path=video_path,
            search_start_sec=window_start,
            search_duration_sec=window_dur,
            noise_threshold_db=noise_threshold_db
        )

        if not intervals:
            return raw_end_sec

        # Pick the silence start that immediately follows raw_end_sec (without cutting speech)
        for s_start, s_end in intervals:
            if s_start >= (raw_end_sec - 0.05):
                # Add safe 0.12s pad into silence, bounded before silence ends
                pad = min(0.15, max(0.05, (s_end - s_start) * 0.5))
                return round(s_start + pad, 3)

        # If no silence after raw_end_sec, check if raw_end_sec is already inside a silence interval
        for s_start, s_end in intervals:
            if s_start <= raw_end_sec <= s_end:
                return round(raw_end_sec, 3)

        return raw_end_sec

    @classmethod
    def snap_to_sentence_punctuation(
        cls,
        srt_segments: List[Dict],
        raw_end_sec: float,
        search_window: float = BOUNDARY_SNAP_END_WINDOW
    ) -> Optional[float]:
        """
        Fallback: Snaps end_time to the nearest sentence punctuation terminator (., !, ?) in SRT.
        """
        if not srt_segments:
            return None

        best_diff = float("inf")
        best_end = None

        for seg in srt_segments:
            text = (seg.get("text") or "").strip()
            end = float(seg.get("end") or seg.get("endTime") or 0.0)
            if not text or end <= 0:
                continue

            if text[-1] in ".!?。！？":
                diff = abs(end - raw_end_sec)
                if diff <= search_window and diff < best_diff:
                    best_diff = diff
                    best_end = end + 0.15

        return round(best_end, 3) if best_end is not None else None

    @classmethod
    def refine_clip_boundaries(
        cls,
        video_path: Any,
        start_sec: float,
        end_sec: float,
        enable_snapping: bool = True,
        srt_segments: Optional[Any] = None
    ) -> Tuple[float, float]:
        """
        Calculates refined start and end times with natural conversational padding.
        """
        video_path = Path(video_path)
        if not enable_snapping or not video_path.exists():
            return start_sec, end_sec

        try:
            snapped_start = cls.snap_start_time(video_path, start_sec, search_window=BOUNDARY_SNAP_START_WINDOW)
            snapped_end = cls.snap_end_time(video_path, end_sec, search_window=BOUNDARY_SNAP_END_WINDOW)

            # Look ahead in transcript to complete sentence boundaries
            if srt_segments:
                ext_end = extend_to_sentence_boundary(snapped_end, srt_segments, tolerance_sec=12.0)
                if ext_end > snapped_end:
                    snapped_end = ext_end
                elif snapped_end == end_sec:
                    punc_end = cls.snap_to_sentence_punctuation(srt_segments, end_sec, search_window=BOUNDARY_SNAP_END_WINDOW)
                    if punc_end:
                        snapped_end = punc_end

            # Ensure minimum duration
            if snapped_end - snapped_start < 5.0:
                snapped_end = snapped_start + 5.0

            return snapped_start, snapped_end
        except Exception as e:
            logger.warning(f"Error refining clip boundaries: {e}")
            return start_sec, end_sec
