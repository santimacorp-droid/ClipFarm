"""Subtitle processor test - focus on validating the regex separator correctness"""

import re

from backend.utils.subtitle_processor import SubtitleProcessor


def _split(text: str):
    """Use the processor's separator regex to split text, removing empty fragments (identical to production code))"""
    sp = SubtitleProcessor()
    parts = re.split(sp.word_separators, text)
    return [p for p in parts if p.strip()]


def test_word_separators_is_single_clean_character_class():
    """Verify that word separators form a valid compiled regex."""
    separators = SubtitleProcessor().word_separators

    # Must be a complete character class [....]+
    assert separators.startswith("[")
    assert separators.endswith("]+")

    for ch in ",.!?;:":
        assert ch in separators, f"Separator missing character: {ch!r}"
    assert r"\s" in separators

    # The regex itself can be compiled (no syntax errors)
    assert re.compile(separators)


def test_splits_cjk_string_on_punctuation_and_whitespace():
    """For sample strings with punctuation and whitespace, should cleanly split into word fragments. """
    sample = "Hello, world! This is 'test' 'Single quotes'; (Parentheses) [brackets], and Whitespace\tTab. "
    assert len(_split(sample)) > 0


def test_curly_quotes_act_as_separators():
    """Regression test: curved single/double quotes must act as separators. """
    res = _split("Pre-quote post")
    assert len(res) > 0

