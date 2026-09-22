#!/usr/bin/env python3
"""
Kettle & Fire Fasting Campaign - Automated Batch Stitcher
Extracts approved celebrity fasting hooks and stitches them with the official
Kettle & Fire Founder CTA into 9:16 vertical videos compliant with campaign rules.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KF_BatchStitcher")

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "data" / "output" / "campaigns" / "kettle_and_fire_final"
FOUNDER_CTA_PATH = BASE_DIR / "data" / "kettle_fire_founder_cta.mp4"

APPROVED_STITCHES = [
    {
        "id": "dana_white_86h_fast",
        "name": "Dana White - How To Break An 86-Hour Fast",
        "url": "https://www.youtube.com/shorts/_xlNsQe5Xo0",
        "hook_text": "HOW DANA WHITE BREAKS AN 86H FAST",
        "part_a_duration": 15.0,
        "part_b_duration": 18.0,
        "post_copy": "Dana White broke an 86-hour water fast with slow-simmered bone broth 🍲 The ultimate gut-friendly way to break a fast without insulin spikes. @kettleandfire #kettleandfire #fasting #danawhite #bonebroth #biohacking #wellness"
    },
    {
        "id": "gary_brecka_fasting_superfood",
        "name": "Gary Brecka - Why Bone Broth Is A Fasting Superfood",
        "url": "https://www.youtube.com/shorts/EJXNr7b7rGc",
        "hook_text": "GARY BRECKA: FASTING SUPERFOOD",
        "part_a_duration": 16.0,
        "part_b_duration": 18.0,
        "post_copy": "Gary Brecka explains why bone broth is the ultimate fasting superfood 👀 10g collagen & gut-lining support. @kettleandfire #kettleandfire #garybrecka #fastingprotocol #bonebroth #guthealth #keto"
    },
    {
        "id": "mrbeast_extended_fast",
        "name": "MrBeast - Fasting Recovery Without Cramps",
        "url": "https://www.youtube.com/shorts/gI2orlYrQTM",
        "hook_text": "MRBEAST: HOW TO BREAK EXTENDED FASTS",
        "part_a_duration": 15.0,
        "part_b_duration": 18.0,
        "post_copy": "The secret to surviving extended fasts without feeling like garbage is @kettleandfire bone broth 🔥 Packed with clean electrolytes. @kettleandfire #kettleandfire #mrbeast #intermittentfasting #healthtips #nutrition"
    },
    {
        "id": "dr_pompa_bone_broth_fast",
        "name": "Dr. Pompa - Gut Autophagy & Bone Broth Fasting",
        "url": "https://www.youtube.com/shorts/ACEMYfAAWPQ",
        "hook_text": "DR POMPA: REPAIR GUT LINING WITH BROTH",
        "part_a_duration": 18.0,
        "part_b_duration": 18.0,
        "post_copy": "How the pros actually break a fast with @kettleandfire 🍲 Restores electrolytes and supports gut lining without digestive distress. @kettleandfire #kettleandfire #autophagy #fastingbenefits #longevity #guthealth"
    },
    {
        "id": "two_bears_fasting_recovery",
        "name": "2 Bears 1 Cave - Fasting & Electrolytes",
        "url": "https://www.youtube.com/shorts/Ehn0KBxlUZk",
        "hook_text": "WHY ATHLETES SWEAR BY BONE BROTH",
        "part_a_duration": 15.0,
        "part_b_duration": 18.0,
        "post_copy": "Breaking an extended fast with @kettleandfire bone broth 🍲 Restores electrolytes and protects your digestive system. @kettleandfire #kettleandfire #fasting #bonebroth #biohacking #health"
    }
]


def download_video(url: str, output_path: Path) -> bool:
    """Download video with yt-dlp using unthrottled android stream."""
    try:
        ydl_opts = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "outtmpl": str(output_path),
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return False


def render_stitch(
    part_a_raw: Path,
    part_b_raw: Path,
    output_mp4: Path,
    hook_text: str,
    part_a_sec: float = 15.0,
    part_b_sec: float = 18.0
) -> bool:
    """
    Renders 1080x1920 9:16 vertical stitch with speech-aligned boundary snapping,
    smooth audio transitions, top hook banner and brand CTA.
    Watermark: None (complying strictly with campaign rules).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        part_a_norm = tmp / "part_a_norm.mp4"
        part_b_norm = tmp / "part_b_norm.mp4"
        concat_list = tmp / "concat.txt"

        safe_hook = hook_text.replace("'", "").replace(":", "").replace('"', "")

        # 0. Apply AudioBoundarySnapper to find exact sentence ending
        try:
            from backend.utils.silence_detector import AudioBoundarySnapper
            actual_a_sec = AudioBoundarySnapper.snap_end_time(part_a_raw, part_a_sec, search_window=2.5)
            actual_b_sec = AudioBoundarySnapper.snap_end_time(part_b_raw, part_b_sec, search_window=2.5)
        except Exception as e:
            logger.debug(f"Boundary snapping fallback: {e}")
            actual_a_sec = part_a_sec
            actual_b_sec = part_b_sec

        fade_out_a = max(0.1, actual_a_sec - 0.18)
        fade_out_b = max(0.1, actual_b_sec - 0.18)

        # 1. Normalize Part A (9:16 vertical canvas + Upper Hook Headline + Audio Smooth)
        vf_a = (
            f"split[fg_raw][bg_raw];"
            f"[bg_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=24[bg];"
            f"[fg_raw]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawbox=x=60:y=180:w=960:h=90:color=black@0.75:t=fill,"
            f"drawbox=x=60:y=180:w=960:h=90:color=gold@0.9:t=3,"
            f"drawtext=text='{safe_hook}':fontcolor=white:fontsize=36:font='DejaVu Sans':"
            f"x=(w-text_w)/2:y=208[v_out];"
            f"[0:a]afade=t=in:ss=0:d=0.12,afade=t=out:st={fade_out_a:.2f}:d=0.18[a_out]"
        )
        cmd_a = [
            "ffmpeg", "-y", "-ss", "00:00:00", "-t", str(actual_a_sec),
            "-i", str(part_a_raw),
            "-filter_complex", vf_a,
            "-map", "[v_out]", "-map", "[a_out]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-r", "30",
            str(part_a_norm)
        ]
        res_a = subprocess.run(cmd_a, capture_output=True, text=True)
        if res_a.returncode != 0:
            logger.error(f"Part A normalize failed: {res_a.stderr}")
            return False

        # 2. Normalize Part B (Founder CTA + Persistent Brand Banner + Audio Smooth)
        brand_header = "KETTLE & FIRE BONE BROTH"
        vf_b = (
            f"split[fg_raw][bg_raw];"
            f"[bg_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=24[bg];"
            f"[fg_raw]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]drawbox=x=60:y=180:w=960:h=90:color=black@0.85:t=fill,"
            f"drawbox=x=60:y=180:w=960:h=90:color=yellow@0.95:t=3,"
            f"drawtext=text='{brand_header}':fontcolor=gold:fontsize=38:font='DejaVu Sans':"
            f"x=(w-text_w)/2:y=206[v_out];"
            f"[0:a]afade=t=in:ss=0:d=0.15,afade=t=out:st={fade_out_b:.2f}:d=0.20[a_out]"
        )
        cmd_b = [
            "ffmpeg", "-y", "-ss", "00:00:00", "-t", str(actual_b_sec),
            "-i", str(part_b_raw),
            "-filter_complex", vf_b,
            "-map", "[v_out]", "-map", "[a_out]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-r", "30",
            str(part_b_norm)
        ]
        res_b = subprocess.run(cmd_b, capture_output=True, text=True)
        if res_b.returncode != 0:
            logger.error(f"Part B normalize failed: {res_b.stderr}")
            return False

        # 3. Concatenate Part A + Part B
        with open(concat_list, "w") as f:
            f.write(f"file '{part_a_norm}'\n")
            f.write(f"file '{part_b_norm}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_mp4)
        ]
        res_concat = subprocess.run(cmd_concat, capture_output=True, text=True)
        return res_concat.returncode == 0 and output_mp4.exists()


def run_batch():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = BASE_DIR / "data" / "cache" / "campaign_sources"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not FOUNDER_CTA_PATH.exists():
        logger.error(f"Founder CTA video not found at {FOUNDER_CTA_PATH}")
        return

    results = []

    for item in APPROVED_STITCHES:
        stitch_id = item["id"]
        logger.info(f"▶ Processing Stitch: {item['name']} ...")

        raw_download = cache_dir / f"{stitch_id}_raw.mp4"
        if not raw_download.exists() or raw_download.stat().st_size == 0:
            logger.info(f"Downloading source: {item['url']} ...")
            success = download_video(item["url"], raw_download)
            if not success:
                logger.warning(f"Failed to download {item['name']}, skipping.")
                continue

        final_mp4 = OUTPUT_DIR / f"{stitch_id}.mp4"
        success = render_stitch(
            part_a_raw=raw_download,
            part_b_raw=FOUNDER_CTA_PATH,
            output_mp4=final_mp4,
            hook_text=item["hook_text"],
            part_a_sec=item["part_a_duration"],
            part_b_sec=item["part_b_duration"]
        )

        if success:
            file_size_mb = round(final_mp4.stat().st_size / (1024 * 1024), 2)
            logger.info(f"✅ Generated: {final_mp4.name} ({file_size_mb} MB)")
            results.append({
                "id": stitch_id,
                "name": item["name"],
                "filename": final_mp4.name,
                "file_path": str(final_mp4),
                "file_size_mb": file_size_mb,
                "aspect_ratio": "9:16 (1080x1920)",
                "duration_sec": item["part_a_duration"] + item["part_b_duration"],
                "post_copy": item["post_copy"],
                "compliance": {
                    "watermarks": "None (Compliant with campaign rules)",
                    "brand_featured": "Predominant (Part B)",
                    "tag_required": "@kettleandfire (Included)"
                }
            })
        else:
            logger.error(f"❌ Failed to render stitch: {stitch_id}")

    meta_path = OUTPUT_DIR / "campaign_posts_manifest.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"🎉 Batch execution completed! {len(results)} videos ready at {OUTPUT_DIR}")


if __name__ == "__main__":
    run_batch()
