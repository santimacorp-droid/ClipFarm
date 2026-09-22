"""Tests for Caption and Subtitle Processing Pipeline"""

import tempfile
import json
from pathlib import Path
from backend.utils.caption_styles import (
    ViralCaptionGenerator,
    _parse_time_to_seconds,
    _seconds_to_ass_time,
    _seconds_to_srt_time,
    _tokenize_text,
    _join_tokens,
    _has_cjk,
    _resolve_overlapping_segments,
)
from backend.utils.speech_recognizer import (
    SpeechRecognizer,
    diarize_audio,
    assign_speakers_to_segments,
)
from backend.pipeline.step6_video import _parse_timestamp_to_seconds
from backend.utils.video_processor import VideoProcessor
from backend.utils.bilibili_downloader import BilibiliDownloader


def test_time_conversions():
    """Verify millisecond and centisecond time conversions without rounding truncation."""
    assert _parse_time_to_seconds("00:01:23,456") == 83.456
    assert _parse_time_to_seconds("01:23.456") == 83.456
    assert _parse_time_to_seconds("00:00:01,996") == 1.996
    assert _parse_time_to_seconds("00:01:23.450 align:start position:0%") == 83.45

    # 1.996 seconds -> 0:00:02.00 in centiseconds (199.6 cs rounds to 200 cs = 2.00 s)
    assert _seconds_to_ass_time(1.996) == "0:00:02.00"
    assert _seconds_to_ass_time(83.456) == "0:01:23.46"
    assert _seconds_to_srt_time(83.456) == "00:01:23,456"


def test_tokenization_and_joining():
    """Verify CJK and Latin tokenization and natural token joining."""
    # English
    en_tokens = _tokenize_text("He thought getting caught")
    assert en_tokens == ["He", "thought", "getting", "caught"]
    assert _join_tokens(en_tokens) == "He thought getting caught"

    # Chinese
    cjk_text = "\u8fd9\u662f\u6d4b\u8bd5\u89c6\u9891\u5b57\u5e55"
    zh_tokens = _tokenize_text(cjk_text)
    assert len(zh_tokens) == 8
    assert _join_tokens(zh_tokens) == cjk_text

    # Mixed
    mixed_text = "\u8fd9\u662f Call of Duty \u6d4b\u8bd5!"
    mixed_tokens = _tokenize_text(mixed_text)
    assert _has_cjk(mixed_text)
    assert _join_tokens(mixed_tokens) == mixed_text


def test_ass_generation_english_grouping():
    """Verify that long English subtitles are chunked into punchy groups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "test.srt"
        ass_path = Path(tmpdir) / "test.ass"

        # 12 words in one segment (3.0s)
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:03,000\n"
            "He thought getting caught cheating in Call of Duty meant getting banned\n",
            encoding="utf-8"
        )

        success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=srt_path,
            clip_start=0.0,
            clip_end=3.0,
            output_ass_path=ass_path,
            style_key="hormozi_yellow",
            hook_title="Alert Hook",
            show_hook_banner=True
        )
        assert success
        assert ass_path.exists()

        content = ass_path.read_text(encoding="utf-8")
        # Check that HookTitle is present in generated ASS
        assert "HookTitle" in content and "ALERT HOOK" in content
        # Check color formatting contains trailing & and highlight color
        assert "&H0000FFFF&" in content
        assert r"{\c&H00FFFFFF&}" in content
        # Check that style definition is present
        assert "Style: Default," in content

        # Check dialogue lines: each line should have at most 4 words
        for line in content.splitlines():
            if line.startswith("Dialogue:") and "HookTitle" not in line:
                text_part = line.split(",,", 1)[-1]
                # Strip ASS tags
                import re
                clean = re.sub(r'\{[^\}]+\}', '', text_part).strip()
                words = clean.split()
                assert len(words) <= 4, f"Line exceeded group limit: {clean}"


def test_ass_generation_cjk_highlighting():
    """Verify that Chinese subtitles are animated character by character without spaces."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "zh.srt"
        ass_path = Path(tmpdir) / "zh.ass"

        cjk_text = "\u8fd9\u662f\u6d4b\u8bd5\u89c6\u9891\u5b57\u5e55"
        srt_path.write_text(
            f"1\n00:00:00,000 --> 00:00:02,000\n{cjk_text}\n",
            encoding="utf-8"
        )

        success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=srt_path,
            clip_start=0.0,
            clip_end=2.0,
            output_ass_path=ass_path,
            style_key="hormozi_yellow",
            hook_title="Viral Hook Title",
            show_hook_banner=True
        )
        assert success

        content = ass_path.read_text(encoding="utf-8")
        assert "VIRAL HOOK TITLE" in content or "Viral Hook Title" in content
        assert "&H0000FFFF&" in content
        assert "\u8fd9" in content and "\u5b57\u5e55" in content
        # Ensure no spaces between Chinese characters
        assert " " not in content.split(",,")[-1].strip()


def test_speech_recognizer_tight_srt_cjk():
    """Verify that _words_to_tight_srt joins CJK characters without unwanted spaces."""
    class FakeWord:
        def __init__(self, word, start, end):
            self.word = word
            self.start = start
            self.end = end

    class FakeSegment:
        def __init__(self, words):
            self.words = words

    # Simulate Whisper CJK tokens
    zh_words = [
        FakeWord("\u6211", 0.0, 0.3),
        FakeWord("\u4eec", 0.3, 0.6),
        FakeWord("\u4eca", 0.6, 0.9),
        FakeWord("\u5929", 0.9, 1.2),
        FakeWord("\u6765", 1.2, 1.5),
        FakeWord("\u6d4b", 1.5, 1.8),
        FakeWord("\u8bd5", 1.8, 2.1),
        FakeWord("\u3002", 2.1, 2.3),
    ]
    seg = FakeSegment(zh_words)
    srt_output = SpeechRecognizer._words_to_tight_srt([seg])
    assert "\u6211\u4eec\u4eca\u5929\u6765\u6d4b\u8bd5\u3002" in srt_output
    assert "\u6211 \u4eec" not in srt_output


def test_bilibili_vtt_to_srt_conversion():
    """Verify VTT to SRT conversion with cue settings and 2-part timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vtt_path = Path(tmpdir) / "sample.vtt"
        srt_path = Path(tmpdir) / "sample.srt"

        vtt_path.write_text(
            "WEBVTT\n\n"
            "00:01.000 --> 00:04.500 align:start position:50%\n"
            "<v Speaker>Hello <b>world</b></v>\n\n"
            "01:02:03.123 --> 01:02:06.789\n"
            "Second subtitle line\n",
            encoding="utf-8"
        )

        downloader = BilibiliDownloader(download_dir=Path(tmpdir))
        downloader._convert_vtt_to_srt(vtt_path, srt_path)

        srt_content = srt_path.read_text(encoding="utf-8")
        assert "00:00:01,000 --> 00:00:04,500" in srt_content
        assert "01:02:03,123 --> 01:02:06,789" in srt_content
        assert "Hello world" in srt_content
        assert "align:start" not in srt_content
        assert "<b>" not in srt_content


def test_ffmpeg_filter_path_escaping():
    """Verify FFmpeg filter path escaping."""
    path_linux = Path("/media/storage/video test/clip.ass")
    escaped_linux = VideoProcessor._escape_ffmpeg_filter_path(path_linux)
    assert "\\:" not in escaped_linux or "/media" in escaped_linux

    path_with_colon = Path("/tmp/test:file[1].ass")
    escaped_colon = VideoProcessor._escape_ffmpeg_filter_path(path_with_colon)
    assert r"\:" in escaped_colon
    assert r"\[1\]" in escaped_colon


def test_parse_timestamp_to_seconds():
    """Verify robust parsing of various timestamp string and numeric formats."""
    assert _parse_timestamp_to_seconds("00:01:23") == 83.0
    assert _parse_timestamp_to_seconds("00:01:23,456") == 83.456
    assert _parse_timestamp_to_seconds("01:23.500") == 83.5
    assert _parse_timestamp_to_seconds("83.5") == 83.5
    assert _parse_timestamp_to_seconds(83.5) == 83.5
    assert _parse_timestamp_to_seconds(83) == 83.0
    assert _parse_timestamp_to_seconds("invalid") == 0.0


def test_generate_clip_ass_string_timestamps():
    """Verify generate_clip_ass accepts string timestamps without raising TypeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "test.srt"
        ass_path = Path(tmpdir) / "test.ass"

        srt_path.write_text(
            "1\n00:01:00,000 --> 00:01:05,000\nHello from the clip\n",
            encoding="utf-8"
        )

        # Pass string timestamps "00:01:00" and "00:01:05"
        success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=srt_path,
            clip_start="00:01:00",
            clip_end="00:01:05",
            output_ass_path=ass_path,
            style_key="hormozi_yellow",
            show_hook_banner=False
        )
        assert success
        assert ass_path.exists()
        content = ass_path.read_text(encoding="utf-8")
        assert "FROM THE CLIP" in content and "HELLO" in content
        # Relative start in clip should be 0:00:00.00
        assert "Dialogue: 0,0:00:00.00" in content


def test_word_level_highlight_timing():
    """Verify word-level highlight animation respects faster-whisper word timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ass_path = Path(tmpdir) / "test_words.ass"

        # Segment with exact non-uniform word durations
        # "Fast" = 0.2s (10.0->10.2), "word" = 0.3s (10.2->10.5), "longer" = 1.5s (10.5->12.0)
        words_data = [
            {
                "start": 10.0,
                "end": 12.0,
                "text": "Fast word longer",
                "speaker": "SPEAKER_00",
                "words": [
                    {"word": "Fast", "start": 10.0, "end": 10.2},
                    {"word": "word", "start": 10.2, "end": 10.5},
                    {"word": "longer", "start": 10.5, "end": 12.0},
                ]
            }
        ]

        success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=None,
            clip_start=10.0,
            clip_end=15.0,
            output_ass_path=ass_path,
            style_key="hormozi_yellow",
            show_hook_banner=False,
            words_data=words_data
        )
        assert success
        assert ass_path.exists()

        content = ass_path.read_text(encoding="utf-8")
        # Word 1 "FAST" starts at 0.00 and ends at 0.20
        assert "Dialogue: 0,0:00:00.00,0:00:00.20,Default" in content
        # Word 2 "WORD" starts at 0.20 and ends at 0.50
        assert "Dialogue: 0,0:00:00.20,0:00:00.50,Default" in content
        # Word 3 "LONGER" starts at 0.50 and ends at 2.00
        assert "Dialogue: 0,0:00:00.50,0:00:02.00,Default" in content


def test_multi_speaker_dual_track_ass():
    """Verify SecondSpeaker style in ASS header and proper dialogue line styling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ass_path = Path(tmpdir) / "multi_spk.ass"

        multi_spk_data = [
            {
                "start": 1.0,
                "end": 3.0,
                "text": "Host speaks first",
                "speaker": "SPEAKER_00",
                "words": [
                    {"word": "Host", "start": 1.0, "end": 1.5},
                    {"word": "speaks", "start": 1.5, "end": 2.2},
                    {"word": "first", "start": 2.2, "end": 3.0},
                ]
            },
            {
                "start": 2.0,
                "end": 4.0,
                "text": "Guest interrupts host",
                "speaker": "SPEAKER_01",
                "words": [
                    {"word": "Guest", "start": 2.0, "end": 2.5},
                    {"word": "interrupts", "start": 2.5, "end": 3.2},
                    {"word": "host", "start": 3.2, "end": 4.0},
                ]
            }
        ]

        success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=None,
            clip_start=0.0,
            clip_end=5.0,
            output_ass_path=ass_path,
            style_key="hormozi_yellow",
            show_hook_banner=False,
            words_data=multi_spk_data
        )
        assert success
        content = ass_path.read_text(encoding="utf-8")

        # Verify SecondSpeaker style is defined with higher MarginV
        assert "Style: Default," in content
        assert "Style: SecondSpeaker," in content

        # Verify SPEAKER_00 dialogue uses Default style
        assert ",Default,,0,0,0,," in content
        # Verify SPEAKER_01 dialogue uses SecondSpeaker style
        assert ",SecondSpeaker,,0,0,0,," in content


def test_overlap_resolution_behavior():
    """Verify overlap resolution: >0.5s delays without truncation, cross-speaker overlap allowed."""
    # 1. Same speaker with long overlap (> 0.5s) -> should delay second segment to prev.end + 0.05
    same_spk_long_overlap = [
        {"start": 1.0, "end": 4.0, "text": "First phrase", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 5.0, "text": "Second phrase", "speaker": "SPEAKER_00"},
    ]
    resolved = _resolve_overlapping_segments(same_spk_long_overlap)
    assert len(resolved) == 2
    assert resolved[0]['start'] == 1.0
    assert resolved[0]['end'] == 4.0
    assert resolved[1]['start'] == 4.05  # pushed after first ends
    assert resolved[1]['end'] >= 5.0

    # 2. Same speaker with short overlap (<= 0.5s) -> truncates previous end
    same_spk_short_overlap = [
        {"start": 1.0, "end": 3.3, "text": "First phrase", "speaker": "SPEAKER_00"},
        {"start": 3.0, "end": 5.0, "text": "Second phrase", "speaker": "SPEAKER_00"},
    ]
    resolved_short = _resolve_overlapping_segments(same_spk_short_overlap)
    assert len(resolved_short) == 2
    assert resolved_short[0]['end'] == 3.0
    assert resolved_short[1]['start'] == 3.0

    # 3. Different speakers -> simultaneous overlap is preserved
    diff_spk_overlap = [
        {"start": 1.0, "end": 4.0, "text": "Speaker zero", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 5.0, "text": "Speaker one", "speaker": "SPEAKER_01"},
    ]
    resolved_diff = _resolve_overlapping_segments(diff_spk_overlap)
    assert len(resolved_diff) == 2
    assert resolved_diff[0]['start'] == 1.0
    assert resolved_diff[0]['end'] == 4.0
    assert resolved_diff[1]['start'] == 2.0
    assert resolved_diff[1]['end'] == 5.0


def test_diarization_and_speaker_assignment():
    """Verify diarize_audio fallback and assign_speakers_to_segments logic."""
    # Without HUGGINGFACE_TOKEN, diarize_audio gracefully returns []
    res = diarize_audio("dummy.mp4")
    assert res == []

    # Test assign_speakers_to_segments with mock diarization
    segments = [
        {"start": 1.0, "end": 3.0, "text": "Sentence 1"},
        {"start": 4.0, "end": 6.0, "text": "Sentence 2"},
    ]
    diarization = [
        {"start": 0.5, "end": 3.5, "speaker": "SPEAKER_01"},
        {"start": 3.8, "end": 7.0, "speaker": "SPEAKER_02"},
    ]
    assigned = assign_speakers_to_segments(segments, diarization)
    assert assigned[0]['speaker'] == "SPEAKER_01"
    assert assigned[1]['speaker'] == "SPEAKER_02"

    # Test fallback to SPEAKER_00 when no diarization overlap
    empty_assigned = assign_speakers_to_segments([{"start": 10.0, "end": 12.0, "text": "Solo"}], [])
    assert empty_assigned[0]['speaker'] == "SPEAKER_00"


def test_companion_words_saving():
    """Verify companion word files are written alongside SRT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "output.srt"
        dummy_segments = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Hello world",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}, {"word": "world", "start": 1.0, "end": 2.0}]
            }
        ]

        SpeechRecognizer._save_companion_words(srt_path, dummy_segments)

        stem_words = Path(tmpdir) / "output_words.json"
        step2_words = Path(tmpdir) / "step2_words.json"
        words_file = Path(tmpdir) / "words.json"

        assert stem_words.exists()
        assert step2_words.exists()
        assert words_file.exists()

        data = json.loads(stem_words.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["text"] == "Hello world"

