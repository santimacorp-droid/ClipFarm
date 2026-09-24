import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.utils.watermark_processor import get_watermark_overlay_expr
from backend.services.watermark_service import WatermarkService
from backend.core.desktop_config import ApiConfig, DesktopConfig


def test_get_watermark_overlay_expr_9_grid_positions():
    """Verify all 9-grid anchor positions generate valid FFmpeg expressions."""
    margin = 20
    # Top row
    assert get_watermark_overlay_expr("top_left", margin) == "20:20"
    assert get_watermark_overlay_expr("top_center", margin) == "(main_w-overlay_w)/2:20"
    assert get_watermark_overlay_expr("top_right", margin) == "main_w-overlay_w-20:20"

    # Middle row
    assert get_watermark_overlay_expr("center_left", margin) == "20:(main_h-overlay_h)/2"
    assert get_watermark_overlay_expr("center", margin) == "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    assert get_watermark_overlay_expr("center_right", margin) == "main_w-overlay_w-20:(main_h-overlay_h)/2"

    # Bottom row
    assert get_watermark_overlay_expr("bottom_left", margin) == "20:main_h-overlay_h-20"
    assert get_watermark_overlay_expr("bottom_center", margin) == "(main_w-overlay_w)/2:main_h-overlay_h-20"
    assert get_watermark_overlay_expr("bottom_right", margin) == "main_w-overlay_w-20:main_h-overlay_h-20"


def test_get_watermark_overlay_expr_custom_draggable_coords():
    """Verify draggable percentage coordinates produce correct expressions."""
    # custom:50:50 (center)
    expr = get_watermark_overlay_expr("custom:50:50", 24)
    assert expr == "(main_w-overlay_w)*0.5000:(main_h-overlay_h)*0.5000"

    # custom:85:90
    expr = get_watermark_overlay_expr("custom:85:90", 24)
    assert expr == "(main_w-overlay_w)*0.8500:(main_h-overlay_h)*0.9000"

    # custom_10_20 format
    expr = get_watermark_overlay_expr("custom_10_20", 24)
    assert expr == "(main_w-overlay_w)*0.1000:(main_h-overlay_h)*0.2000"


def test_watermark_service_lifecycle(tmp_path: Path):
    """Test creating, updating, and deleting watermark presets."""
    service = WatermarkService(data_dir=tmp_path)
    
    # Create fake logo
    logo_filename = service.save_logo_file(b"fake_png_data", "test.png")
    assert (tmp_path / "logos" / logo_filename).exists()

    # Create preset with custom position
    preset = service.create_preset(
        name="Test Brand",
        logo_filename=logo_filename,
        position="custom:75:80",
        scale_percent=20,
        opacity=0.9,
        margin=16,
        is_default=True
    )

    assert preset["name"] == "Test Brand"
    assert preset["position"] == "custom:75:80"
    assert preset["scale_percent"] == 20
    assert preset["opacity"] == 0.9
    assert preset["margin"] == 16
    assert preset["is_default"] is True

    # Update preset
    updated = service.update_preset(preset["id"], {
        "name": "Updated Brand",
        "position": "top_center",
        "scale_percent": 25
    })
    assert updated["name"] == "Updated Brand"
    assert updated["position"] == "top_center"
    assert updated["scale_percent"] == 25

    # Delete preset
    deleted = service.delete_preset(preset["id"])
    assert deleted is True
    assert service.get_preset(preset["id"]) is None


def test_speech_config_model_options():
    """Verify ApiConfig includes model_name for cloud speech recognition."""
    cfg = ApiConfig(endpoint="https://api.groq.com/openai/v1", model_name="whisper-large-v3-turbo")
    assert cfg.endpoint == "https://api.groq.com/openai/v1"
    assert cfg.model_name == "whisper-large-v3-turbo"

    desktop_cfg = DesktopConfig()
    assert hasattr(desktop_cfg.speech_recognition.openai_config, "model_name")
    assert desktop_cfg.speech_recognition.openai_config.model_name == "whisper-1"
