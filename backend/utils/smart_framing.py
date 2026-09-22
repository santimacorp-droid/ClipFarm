"""
Smart Framing and Video Layout Detection Engine

Uses OpenCV YuNet lightweight deep-learning face detector (228KB) to analyze
video frames and automatically determine optimal short-form 9:16 video framing:
1. Enhanced Blurred Canvas (safe 16:9 fit with aesthetically dimmed, blurred background)
2. Podcast Stacked Split-Screen (top speaker & bottom speaker for 2-person interviews)
3. Smart Solo Face Centering (centered on single speaker rather than blind middle)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import cv2
import numpy as np

logger = logging.getLogger(__name__)

YUNET_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "yunet.onnx"


class SmartFramingEngine:
    """Analyzes video content to detect faces and compute optimal framing parameters."""

    _detector: Optional[cv2.FaceDetectorYN] = None
    _framing_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_detector(cls, frame_width: int, frame_height: int) -> Optional[cv2.FaceDetectorYN]:
        """Initializes or reuses the YuNet face detector with specified input dimensions."""
        if not YUNET_MODEL_PATH.exists():
            logger.warning(f"YuNet face detection model not found at: {YUNET_MODEL_PATH}")
            return None

        try:
            detector = cv2.FaceDetectorYN.create(
                model=str(YUNET_MODEL_PATH),
                config="",
                input_size=(frame_width, frame_height),
                score_threshold=0.55,
                nms_threshold=0.3,
                top_k=5000,
            )
            detector.setInputSize((frame_width, frame_height))
            return detector
        except Exception as e:
            logger.error(f"Failed to initialize YuNet face detector: {e}")
            return None

    @classmethod
    def analyze_video_framing(
        cls, video_path: Union[str, Path], sample_count: int = 5
    ) -> Dict[str, Any]:
        """
        Samples multiple frames across a video to detect layout category and speaker positions.

        Returns:
            Dict containing:
            - layout_type: 'podcast_2speaker' | 'solo_speaker' | 'general'
            - speaker_positions: List of normalized x-coordinates [0.0 to 1.0]
            - confidence: float
            - recommended_aspect_ratio: '9:16_split' | '9:16_smart_crop' | '9:16_blur'
        """
        video_path = Path(video_path)
        cache_key = str(video_path.resolve()) if video_path.exists() else str(video_path)
        if cache_key in cls._framing_cache:
            return dict(cls._framing_cache[cache_key])

        default_result = {
            "layout_type": "general",
            "speaker_positions": [],
            "confidence": 0.0,
            "recommended_aspect_ratio": "9:16_blur",
        }

        if not video_path.exists():
            cls._framing_cache[cache_key] = default_result
            return default_result

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            cls._framing_cache[cache_key] = default_result
            return default_result

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if w <= 0 or h <= 0 or total_frames <= 0:
            cap.release()
            cls._framing_cache[cache_key] = default_result
            return default_result

        # Only analyze horizontal/landscape video (16:9 or wider)
        if w <= h:
            cap.release()
            res = {
                "layout_type": "vertical_native",
                "speaker_positions": [0.5],
                "confidence": 1.0,
                "recommended_aspect_ratio": "9:16",
            }
            cls._framing_cache[cache_key] = res
            return res

        detector = cls.get_detector(w, h)
        if detector is None:
            cap.release()
            cls._framing_cache[cache_key] = default_result
            return default_result

        # Sample timestamps evenly throughout video (avoiding intro 2s)
        duration_sec = total_frames / fps
        sample_times = [
            max(2.0, duration_sec * (i + 1) / (sample_count + 1))
            for i in range(sample_count)
        ]

        frame_face_counts = []
        all_left_faces = []
        all_right_faces = []
        all_center_faces = []

        for t in sample_times:
            frame_idx = int(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            try:
                _, faces = detector.detect(frame)
                if faces is not None and len(faces) > 0:
                    valid_faces = []
                    for f in faces:
                        box = f[:4].astype(int)
                        conf = float(f[-1])
                        # Filter out tiny artifacts: face width must be >= 4% of frame width
                        if box[2] >= w * 0.04 and conf >= 0.55:
                            cx = box[0] + box[2] // 2
                            norm_cx = cx / float(w)
                            valid_faces.append(norm_cx)

                    frame_face_counts.append(len(valid_faces))

                    for norm_cx in valid_faces:
                        if norm_cx < 0.44:
                            all_left_faces.append(norm_cx)
                        elif norm_cx > 0.56:
                            all_right_faces.append(norm_cx)
                        else:
                            all_center_faces.append(norm_cx)
            except Exception as det_err:
                logger.debug(f"Face detect error at {t}s: {det_err}")

        cap.release()

        # Decision logic based on multi-frame consensus
        has_left_speaker = len(all_left_faces) >= max(1, sample_count // 3)
        has_right_speaker = len(all_right_faces) >= max(1, sample_count // 3)

        if has_left_speaker and has_right_speaker:
            # Multi-speaker podcast / interview setup!
            speaker1_cx = float(np.median(all_left_faces)) if all_left_faces else 0.28
            speaker2_cx = float(np.median(all_right_faces)) if all_right_faces else 0.72
            logger.info(
                f"SmartFraming: Detected 2-Speaker Podcast (Left={speaker1_cx:.2f}, Right={speaker2_cx:.2f})"
            )
            res = {
                "layout_type": "podcast_2speaker",
                "speaker_positions": [speaker1_cx, speaker2_cx],
                "confidence": 0.92,
                "recommended_aspect_ratio": "9:16_split",
            }
            cls._framing_cache[cache_key] = res
            return res

        elif len(all_center_faces) + len(all_left_faces) + len(all_right_faces) >= max(1, sample_count // 2):
            all_detected = all_center_faces + all_left_faces + all_right_faces
            solo_cx = float(np.median(all_detected))
            logger.info(f"SmartFraming: Detected Solo Speaker (Center={solo_cx:.2f})")
            res = {
                "layout_type": "solo_speaker",
                "speaker_positions": [solo_cx],
                "confidence": 0.85,
                "recommended_aspect_ratio": "9:16_smart_crop",
            }
            cls._framing_cache[cache_key] = res
            return res

        logger.info("SmartFraming: No dominant speaking faces, recommending 9:16_blur")
        cls._framing_cache[cache_key] = default_result
        return default_result

    @staticmethod
    def build_blurred_canvas_filter(
        in_w: int,
        in_h: int,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        input_label: str = "0:v",
        output_label: str = "v_base",
    ) -> str:
        """
        Constructs an enhanced, professional blurred canvas FFmpeg filtergraph:
        - Scaled & cropped background with heavy boxblur + subtle dimming (12% brightness reduction).
        - Centered sharp foreground video (canvas_w width, native aspect height).
        - Clean positioning with ample headroom for top hook banner and bottom subtitles.
        """
        fg_h = int(round(canvas_w * in_h / in_w))
        if fg_h % 2 != 0:
            fg_h += 1

        y_offset = (canvas_h - fg_h) // 2

        filtergraph = (
            f"[{input_label}]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},boxblur=35:5,eq=brightness=-0.12:contrast=0.95[bg];"
            f"[{input_label}]scale={canvas_w}:{fg_h}:flags=lanczos[fg];"
            f"[bg][fg]overlay=0:{y_offset}[{output_label}]"
        )
        return filtergraph

    @staticmethod
    def build_black_header_canvas_filter(
        in_w: int,
        in_h: int,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        header_h: int = 520,
        input_label: str = "0:v",
        output_label: str = "v_base",
    ) -> str:
        """
        Constructs a 9:16 Black Canvas Header (Meme / Narrative Story Reel) FFmpeg filtergraph:
        - Pure solid black 1080x1920 canvas background.
        - Foreground video scaled to fit canvas_w preserving natural aspect ratio without face-cropping.
        - Headroom (header_h) reserved for persistent multi-line top headline text.
        """
        # Calculate scaled height preserving aspect ratio
        fg_h = int(round(canvas_w * in_h / in_w))
        if fg_h % 2 != 0:
            fg_h += 1

        max_allowed_h = canvas_h - header_h - 40
        if fg_h > max_allowed_h:
            fg_h = max_allowed_h
            if fg_h % 2 != 0:
                fg_h += 1
            fg_w = int(round(fg_h * in_w / in_h))
            if fg_w % 2 != 0:
                fg_w += 1
            x_offset = (canvas_w - fg_w) // 2
            y_offset = header_h + 10
            scale_str = f"scale={fg_w}:{fg_h}:flags=lanczos"
        else:
            x_offset = 0
            # Center vertically in the space below header_h or place right at header_h
            remaining_space = canvas_h - header_h
            y_offset = header_h + max(0, (remaining_space - fg_h) // 2)
            scale_str = f"scale={canvas_w}:{fg_h}:flags=lanczos"

        filtergraph = (
            f"color=c=black:s={canvas_w}x{canvas_h}:r=30[bg_black];"
            f"[{input_label}]{scale_str}[fg_scaled];"
            f"[bg_black][fg_scaled]overlay={x_offset}:{y_offset}:shortest=1[{output_label}]"
        )
        return filtergraph

    @staticmethod
    def build_podcast_split_filter(
        in_w: int,
        in_h: int,
        speaker1_cx: float = 0.30,
        speaker2_cx: float = 0.70,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        divider_thickness: int = 4,
        input_label: str = "0:v",
        output_label: str = "v_base",
    ) -> str:
        """
        Constructs a dual-speaker stacked split-screen FFmpeg filtergraph:
        - Top panel: Speaker 1 cropped to aspect ratio
        - Bottom panel: Speaker 2 cropped to aspect ratio
        - Sleek separator line between panels
        """
        half_h = (canvas_h - divider_thickness) // 2
        target_aspect = float(canvas_w) / float(half_h)

        crop_h = in_h
        crop_w = int(min(in_w, round(crop_h * target_aspect)))
        if crop_w % 2 != 0:
            crop_w += 1

        c1_center = int(round(speaker1_cx * in_w))
        x1 = max(0, min(in_w - crop_w, c1_center - (crop_w // 2)))

        c2_center = int(round(speaker2_cx * in_w))
        x2 = max(0, min(in_w - crop_w, c2_center - (crop_w // 2)))

        bottom_y = half_h + divider_thickness

        filtergraph = (
            f"[{input_label}]crop={crop_w}:{crop_h}:{x1}:0,scale={canvas_w}:{half_h}:flags=lanczos[top];"
            f"[{input_label}]crop={crop_w}:{crop_h}:{x2}:0,scale={canvas_w}:{half_h}:flags=lanczos[bot];"
            f"color=c=#1e1e1e:s={canvas_w}x{canvas_h}:r=30[base_color];"
            f"[base_color][top]overlay=0:0:shortest=1[m1];"
            f"[m1][bot]overlay=0:{bottom_y}:shortest=1[{output_label}]"
        )
        return filtergraph

    @staticmethod
    def build_solo_smart_crop_filter(
        in_w: int,
        in_h: int,
        speaker_cx: float = 0.5,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        input_label: str = "0:v",
        output_label: str = "v_base",
    ) -> str:
        """
        Constructs a smart single-speaker crop filter centered on the speaker's face.
        """
        crop_w = int(round(in_h * 9.0 / 16.0))
        if crop_w % 2 != 0:
            crop_w += 1

        center_px = int(round(speaker_cx * in_w))
        crop_x = max(0, min(in_w - crop_w, center_px - (crop_w // 2)))

        filtergraph = (
            f"[{input_label}]crop={crop_w}:{in_h}:{crop_x}:0,"
            f"scale={canvas_w}:{canvas_h}:flags=lanczos[{output_label}]"
        )
        return filtergraph
