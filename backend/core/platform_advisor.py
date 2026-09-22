"""
Platform Duration Advisor
Tags clips with platform suitability based on their duration.
No clips are cut — this is advisory only.
"""
from typing import Dict, List, Any

PLATFORM_DURATION_WINDOWS = {
    "youtube_shorts": {"optimal": (30, 55), "acceptable": (15, 60), "hard_max": 60},
    "tiktok": {"optimal": (30, 180), "acceptable": (15, 600), "hard_max": 600},
    "instagram_reels": {"optimal": (15, 60), "acceptable": (10, 90), "hard_max": 90},
    "facebook_reels": {"optimal": (15, 60), "acceptable": (10, 90), "hard_max": 90},
    "twitter_x": {"optimal": (30, 90), "acceptable": (15, 140), "hard_max": 140},
    "linkedin": {"optimal": (60, 180), "acceptable": (30, 600), "hard_max": None},
    "youtube_full": {"optimal": (180, 600), "acceptable": (60, None), "hard_max": None},
}


def get_platform_advisory(duration_sec: float) -> Dict[str, Any]:
    """
    Given a clip duration in seconds, return:
    - recommended_platforms: platforms where this clip is in the optimal range
    - acceptable_platforms: platforms where this clip works but isn't optimal
    - too_long_for: platforms this clip exceeds the hard limit for
    - duration_label: human-readable tag ('short', 'medium', 'long', 'extended')
    """
    recommended = []
    acceptable = []
    too_long = []

    for platform, windows in PLATFORM_DURATION_WINDOWS.items():
        hard_max = windows["hard_max"]
        opt_min, opt_max = windows["optimal"]
        acc_min, acc_max = windows["acceptable"]

        if hard_max and duration_sec > hard_max:
            too_long.append(platform)
        elif opt_min <= duration_sec <= opt_max:
            recommended.append(platform)
        elif acc_min <= duration_sec <= (acc_max or float('inf')):
            acceptable.append(platform)

    if duration_sec <= 60:
        label = "short"
    elif duration_sec <= 180:
        label = "medium"
    elif duration_sec <= 480:
        label = "long"
    else:
        label = "extended"

    return {
        "recommended_platforms": recommended,
        "acceptable_platforms": acceptable,
        "too_long_for": too_long,
        "duration_label": label,
        "duration_sec": round(duration_sec, 1),
    }
