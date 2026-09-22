"""
Campaign Service - Handles Creator Bounty & Brand Stitch Workflows (e.g. Kettle & Fire Fasting Campaign).
Manages approved video source catalogs, hook presets, social tagging generation, and 2-part video stitching.
"""
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.video_processor import VideoProcessor
from ..utils.caption_styles import ViralCaptionGenerator

logger = logging.getLogger(__name__)

# Preloaded Approved Source Catalog for Kettle & Fire Fasting Campaign
KETTLE_FIRE_CAMPAIGN = {
    "id": "kettle_fire_fasting",
    "name": "Celebrity Fasting x Kettle & Fire Bone Broth",
    "brand_name": "Kettle & Fire",
    "brand_tag": "@kettleandfire",
    "min_duration_sec": 10.0,
    "description": "Clip celebrities & public figures talking about fasting, then stitch in Kettle & Fire content showing bone broth as the ultimate way to break or support a fast.",
    "preferred_structure": "Celebrity talking about fasting and benefits first (Part A), then Kettle & Fire shown/described as the best way to break or support a fast (Part B).",
    "tagging_requirements": {
        "tiktok": "@kettleandfire",
        "instagram": "@kettleandfire",
        "youtube_shorts": "@kettleandfire"
    },
    "hook_suggestions": [
        "How The Pros Actually Break A Fast (Kettle & Fire)",
        "Why Athletes Swear By Kettle & Fire Bone Broth",
        "The Secret To Fasting Without Feeling Like Garbage",
        "How He Actually Breaks His Fast | Kettle & Fire",
        "The Bone Broth Every Athlete Drinks (Kettle & Fire)",
        "Fasting Benefits + Why Kettle & Fire Bone Broth Is Key"
    ],
    "social_captions": [
        "Breaking an extended fast with @kettleandfire bone broth 🍲 The ultimate gut-friendly way to break a fast without insulin spikes. @kettleandfire #kettleandfire #fasting #bonebroth #biohacking #health #wellness",
        "Why top athletes swear by @kettleandfire bone broth to break a fast 👀 Packed with collagen & electrolytes. @kettleandfire #kettleandfire #fastingprotocol #bonebroth #guthealth #keto",
        "The secret to fasting without feeling like garbage is @kettleandfire bone broth 🔥 @kettleandfire #kettleandfire #intermittentfasting #healthtips #nutrition #biohacking",
        "How the pros actually break a fast with @kettleandfire 🍲 Restores electrolytes and supports gut lining. @kettleandfire #kettleandfire #autophagy #fastingbenefits #longevity"
    ],
    "approved_sources": [
        {
            "id": "kf_founder",
            "category": "sponsor_cta",
            "title": "Kettle & Fire Founder on Bone Broth Benefits (Essential CTA/Outro)",
            "speaker": "Justin Mares (Founder)",
            "url": "https://youtu.be/LBmUk8kD1p8?si=iXn0Ugt2tLz72Umb&t=1705",
            "platform": "youtube",
            "type": "sponsor",
            "recommended_use": "Part B (Solution / CTA)"
        },
        {
            "id": "dana_white_tiktok",
            "category": "celebrity_hook",
            "title": "Dana White on Water Fasting (Top Viral Clip)",
            "speaker": "Dana White",
            "url": "https://www.tiktok.com/@danawhite/video/7301874231401401642",
            "platform": "tiktok",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "dana_white_ig",
            "category": "celebrity_hook",
            "title": "Dana White 86-Hour Fast Transformation",
            "speaker": "Dana White",
            "url": "https://www.instagram.com/danawhite/reel/CzsENAXRSJi/?hl=en",
            "platform": "instagram",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "dana_white_nelk",
            "category": "celebrity_hook",
            "title": "Nelk Boys / Dana White Fasting Discussion",
            "speaker": "Dana White & Nelk Boys",
            "url": "https://www.youtube.com/shorts/_xlNsQe5Xo0",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "joe_rogan_everyday",
            "category": "celebrity_hook",
            "title": "Joe Rogan: 'I Drink Bone Broth Every Day'",
            "speaker": "Joe Rogan",
            "url": "https://www.youtube.com/live/neVsniQdOnM?t=4207s",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "joe_rogan_drinks_broth",
            "category": "celebrity_hook",
            "title": "Joe Rogan Drinking Bone Broth on JRE",
            "speaker": "Joe Rogan",
            "url": "https://www.youtube.com/watch?v=OnWs-_ql-tc",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "gary_brecka_1",
            "category": "celebrity_hook",
            "title": "Gary Brecka on Fasting & Water Fasting Benefits",
            "speaker": "Gary Brecka",
            "url": "https://www.youtube.com/shorts/EJXNr7b7rGc",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "gary_brecka_2",
            "category": "celebrity_hook",
            "title": "Gary Brecka Fasting Protocol (Reels)",
            "speaker": "Gary Brecka",
            "url": "https://www.instagram.com/reels/DP9kebXEnwU/",
            "platform": "instagram",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "mrbeast_fasting",
            "category": "celebrity_hook",
            "title": "MrBeast Fasting Experience",
            "speaker": "MrBeast",
            "url": "https://www.youtube.com/shorts/gI2orlYrQTM",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "two_bears_1",
            "category": "celebrity_hook",
            "title": "2 Bears 1 Cave Fasting Clip 1",
            "speaker": "Tom Segura / Bert Kreischer",
            "url": "https://www.youtube.com/shorts/Ehn0KBxlUZk",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "two_bears_2",
            "category": "celebrity_hook",
            "title": "2 Bears 1 Cave with Gary Brecka",
            "speaker": "Gary Brecka & Tom Segura",
            "url": "https://www.youtube.com/watch?v=JTc6GlkDGxc",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "dr_pompa_1",
            "category": "celebrity_hook",
            "title": "Dr. Pompa on Bone Broth Fasting (Shorts)",
            "speaker": "Dr. Daniel Pompa",
            "url": "https://www.youtube.com/shorts/ACEMYfAAWPQ",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A or Part B"
        },
        {
            "id": "dr_pompa_2",
            "category": "celebrity_hook",
            "title": "Dr. Pompa Complete Bone Broth Fast Breakdown",
            "speaker": "Dr. Daniel Pompa",
            "url": "https://www.youtube.com/watch?v=9X_0IMug2ew",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A or Part B"
        },
        {
            "id": "thomas_delauer",
            "category": "celebrity_hook",
            "title": "Thomas DeLauer Fasting & Breaking a Fast",
            "speaker": "Thomas DeLauer",
            "url": "https://www.youtube.com/watch?v=qfMAwm2oHcA",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "jennifer_aniston_yt",
            "category": "celebrity_hook",
            "title": "Jennifer Aniston on Intermittent Fasting",
            "speaker": "Jennifer Aniston",
            "url": "https://www.youtube.com/watch?v=ZFiytnCvCGM",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        },
        {
            "id": "fasting_context_overview",
            "category": "celebrity_hook",
            "title": "Fasting Scientific Context & Autophagy",
            "speaker": "Health Expert",
            "url": "https://www.youtube.com/watch?v=0PsBxVQNQ_w",
            "platform": "youtube",
            "type": "celebrity",
            "recommended_use": "Part A (Hook / Story)"
        }
    ]
}


class CampaignStitchService:
    """Service for stitching celebrity hook + sponsor solution clips into 9:16 vertical videos."""

    @staticmethod
    def get_campaign_info(campaign_id: str = "kettle_fire_fasting") -> Dict[str, Any]:
        """Returns campaign specifications, source catalog, and guidelines."""
        return KETTLE_FIRE_CAMPAIGN

    @staticmethod
    def get_video_duration(video_path: Path) -> float:
        """Get duration of video in seconds using ffprobe."""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration for {video_path}: {e}")
            return 0.0

    @classmethod
    def stitch_campaign_clip(
        cls,
        part_a_video: Path,
        part_b_video: Path,
        output_path: Path,
        part_a_srt: Optional[Path] = None,
        part_b_srt: Optional[Path] = None,
        hook_title: Optional[str] = "How The Pros Actually Break A Fast",
        caption_style: str = "hormozi_yellow"
    ) -> bool:
        """
        Stitches Part A (Celebrity Fasting Clip) and Part B (Kettle & Fire Sponsor Clip)
        into a seamless 1080x1920 9:16 vertical short with non-jitter captions and timed hook headline.
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                norm_a = tmp_path / "norm_a.mp4"
                norm_b = tmp_path / "norm_b.mp4"
                combined_raw = tmp_path / "combined_raw.mp4"
                combined_ass = tmp_path / "combined.ass"

                # 1. Normalize Part A to standard 1080x1920 30fps with 9:16 blurred canvas
                logger.info(f"Standardizing Part A (Celebrity Clip): {part_a_video}")
                filter_a = (
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
                    "[0:v]scale=1080:-2:flags=lanczos[fg];"
                    "[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]"
                )
                cmd_a = [
                    'ffmpeg', '-y', '-i', str(part_a_video),
                    '-filter_complex', filter_a,
                    '-map', '[vout]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
                    '-r', '30',
                    str(norm_a)
                ]
                subprocess.run(cmd_a, capture_output=True, text=True, check=True)

                # 2. Normalize Part B to standard 1080x1920 30fps with 9:16 blurred canvas
                logger.info(f"Standardizing Part B (Kettle & Fire CTA): {part_b_video}")
                filter_b = (
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
                    "[0:v]scale=1080:-2:flags=lanczos[fg];"
                    "[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]"
                )
                cmd_b = [
                    'ffmpeg', '-y', '-i', str(part_b_video),
                    '-filter_complex', filter_b,
                    '-map', '[vout]', '-map', '0:a?',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
                    '-r', '30',
                    str(norm_b)
                ]
                subprocess.run(cmd_b, capture_output=True, text=True, check=True)

                dur_a = cls.get_video_duration(norm_a)
                dur_b = cls.get_video_duration(norm_b)
                total_dur = dur_a + dur_b
                logger.info(f"Normalized segments - Part A: {dur_a:.2f}s, Part B: {dur_b:.2f}s, Total: {total_dur:.2f}s")

                # 3. Concatenate video and audio streams seamlessly
                concat_list = tmp_path / "concat.txt"
                concat_list.write_text(f"file '{norm_a.resolve()}'\nfile '{norm_b.resolve()}'\n", encoding="utf-8")

                cmd_concat = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', str(concat_list),
                    '-c', 'copy',
                    str(combined_raw)
                ]
                subprocess.run(cmd_concat, capture_output=True, text=True, check=True)

                # 4. Generate Unified Timestamp-Offset ASS Subtitles
                combined_segs = []
                if part_a_srt and part_a_srt.exists():
                    segs_a = ViralCaptionGenerator.parse_srt_file(part_a_srt)
                    for s in segs_a:
                        if s['start'] < dur_a:
                            combined_segs.append({
                                'start': s['start'],
                                'end': min(dur_a, s['end']),
                                'text': s['text']
                            })

                if part_b_srt and part_b_srt.exists():
                    segs_b = ViralCaptionGenerator.parse_srt_file(part_b_srt)
                    for s in segs_b:
                        combined_segs.append({
                            'start': s['start'] + dur_a,
                            'end': s['end'] + dur_a,
                            'text': s['text']
                        })

                # Write temporary combined SRT
                from ..utils.caption_styles import _seconds_to_srt_time
                combined_srt = tmp_path / "combined.srt"
                srt_cues = []
                for idx, seg in enumerate(combined_segs, 1):
                    start_str = _seconds_to_srt_time(seg['start'])
                    end_str = _seconds_to_srt_time(seg['end'])
                    srt_cues.append(f"{idx}\n{start_str} --> {end_str}\n{seg['text']}\n")
                combined_srt.write_text("\n".join(srt_cues), encoding="utf-8")

                # Generate styled ASS captions
                active_style = caption_style if caption_style and caption_style.lower() != "none" else "hormozi_yellow"
                ViralCaptionGenerator.generate_clip_ass(
                    source_srt_path=combined_srt,
                    clip_start=0.0,
                    clip_end=total_dur,
                    output_ass_path=combined_ass,
                    style_key=active_style,
                    hook_title=hook_title,
                    show_hook_banner=bool(hook_title),
                    video_width=1080,
                    video_height=1920
                )

                # Ensure Kettle & Fire is featured prominently on screen during Part B
                if combined_ass.exists():
                    from ..utils.caption_styles import _seconds_to_ass_time
                    brand_start = _seconds_to_ass_time(dur_a)
                    brand_end = _seconds_to_ass_time(min(total_dur, dur_a + 5.0))
                    brand_banner = (
                        f"Dialogue: 2,{brand_start},{brand_end},Default,,0,0,0,,"
                        r"{\pos(540,160)\an8\fad(250,400)\fs54\b1\c&H0000FFFF&\bord4\3c&H00000000&}KETTLE & FIRE BONE BROTH"
                        "\n"
                    )
                    with open(combined_ass, 'a', encoding='utf-8') as f:
                        f.write(brand_banner)

                # 5. Burn ASS captions into final 9:16 video
                escaped_ass = VideoProcessor._escape_ffmpeg_filter_path(combined_ass)
                cmd_burn = [
                    'ffmpeg', '-y', '-i', str(combined_raw),
                    '-vf', f"ass='{escaped_ass}'",
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                    '-c:a', 'copy',
                    str(output_path)
                ]
                subprocess.run(cmd_burn, capture_output=True, text=True, check=True)

                logger.info(f"Successfully created stitched campaign clip: {output_path} ({total_dur:.2f}s)")
                return True

        except Exception as e:
            logger.error(f"Failed to stitch campaign clip: {e}")
            return False
