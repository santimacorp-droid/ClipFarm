#!/usr/bin/env python3
"""
Affiliate Marketing Video Creator CLI
Processes videos for affiliate marketing by:
- Transcribing Filipino / Tagalog speech ('tl') with word timestamps
- Burning stylish social captions (Hormozi Yellow, Neon Green, etc.)
- Overlaying an animated Facebook Follow CTA
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.affiliate.affiliate_processor import AffiliateVideoProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("affiliate_cli")


def main():
    parser = argparse.ArgumentParser(
        description="Affiliate Marketing Video Creator (Filipino Captions + Facebook Follow CTA)"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        nargs="+",
        help="Path to input video file(s) or directory containing MP4/MOV videos."
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="data/output/affiliate",
        help="Directory where processed videos will be saved (default: data/output/affiliate)."
    )
    parser.add_argument(
        "--fb-handle",
        default="",
        help="Facebook handle or page name to display on the Follow CTA (e.g. '@AffiliatePH' or 'ShopeeFinds')."
    )
    parser.add_argument(
        "--caption-style",
        default="hormozi_yellow",
        choices=["hormozi_yellow", "neon_green", "neon_cyan", "minimal_box", "none"],
        help="Caption visual style preset (default: hormozi_yellow)."
    )
    parser.add_argument(
        "--cta-style",
        default="pill",
        choices=["pill", "card"],
        help="CTA visual presentation: 'pill' (action button) or 'card' (frosted handle badge) (default: pill)."
    )
    parser.add_argument(
        "--cta-position",
        default="lower_center",
        help="CTA position on screen (default: lower_center)."
    )
    parser.add_argument(
        "--transcript", "--srt",
        dest="transcript",
        default=None,
        help="Path to existing transcription file (.srt, .vtt, .txt, .json) or transcript text to align and burn."
    )
    parser.add_argument(
        "--engine",
        default="gemini",
        choices=["gemini", "whisper", "auto"],
        help="Transcription model: 'gemini' (Gemini 2.5 Flash Native Filipino AI - Recommended), 'whisper' (local faster-whisper), or 'auto'."
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium"],
        help="faster-whisper model size if whisper engine is used (default: small)."
    )
    parser.add_argument(
        "--language",
        default="tl",
        help="Spoken language code for Whisper transcription (default: tl for Tagalog/Filipino)."
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Device to run Whisper on: 'auto', 'cpu', 'cuda' (default: auto)."
    )

    args = parser.parse_args()

    # Collect video files
    video_files = []
    for item in args.input:
        p = Path(item).resolve()
        if p.is_dir():
            for ext in ["*.mp4", "*.mov", "*.mkv", "*.webm"]:
                video_files.extend(list(p.glob(ext)))
        elif p.is_file():
            video_files.append(p)
        else:
            logger.warning(f"Specified input does not exist: {p}")

    if not video_files:
        logger.error("No valid video files found to process.")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Found {len(video_files)} video(s) to process.")
    processor = AffiliateVideoProcessor(
        whisper_model=args.model,
        device=args.device,
        default_caption_style=args.caption_style,
        default_engine=args.engine
    )

    results = []
    for vid in video_files:
        out_vid = output_dir / f"{vid.stem}_filipino_fb.mp4"
        logger.info(f"Processing: {vid.name} -> {out_vid.name} (Engine: {args.engine})")
        try:
            res = processor.process_affiliate_video(
                input_video_path=vid,
                output_video_path=out_vid,
                transcript_source=args.transcript,
                fb_handle=args.fb_handle,
                caption_style=args.caption_style,
                cta_style=args.cta_style,
                cta_position=args.cta_position,
                language=args.language,
                engine=args.engine
            )
            results.append(res)
            logger.info(f"✓ Completed {vid.name}: {res['segment_count']} segments, {res['processing_time_sec']}s")
        except Exception as e:
            logger.error(f"✗ Failed to process {vid.name}: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info(f"All processing finished. {len(results)} of {len(video_files)} succeeded.")
    for r in results:
        logger.info(f"Output: {r['output_video']}")


if __name__ == "__main__":
    main()
