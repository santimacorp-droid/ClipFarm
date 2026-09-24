"""
Watermark Service
Manages saved watermark / campaign presets and logo assets for AI Video Clipper.
"""

import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class WatermarkService:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from ..core.path_utils import get_data_directory
            data_dir = get_data_directory() / "watermarks"
        
        self.data_dir = Path(data_dir)
        self.logos_dir = self.data_dir / "logos"
        self.presets_file = self.data_dir / "presets.json"
        
        self.logos_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_presets_file()

    def _ensure_presets_file(self) -> None:
        """Ensure presets.json exists with default sample presets."""
        if not self.presets_file.exists():
            default_logo_path = self.logos_dir / "default_badge.png"
            if not default_logo_path.exists():
                self._generate_default_logo(default_logo_path)

            initial_presets = [
                {
                    "id": "default",
                    "name": "⚡ Highlight Badge",
                    "logo_filename": "default_badge.png",
                    "position": "bottom_right",
                    "scale_percent": 15,
                    "opacity": 0.85,
                    "margin": 24,
                    "is_default": True,
                    "created_at": datetime.utcnow().isoformat()
                }
            ]
            self._save_presets(initial_presets)

    def _generate_default_logo(self, output_path: Path) -> None:
        """Generate a clean, high-contrast sample badge logo."""
        try:
            img = Image.new("RGBA", (240, 72), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle(
                [(2, 2), (237, 69)],
                radius=14,
                fill=(18, 18, 24, 210),
                outline=(255, 215, 0, 230),
                width=2
            )
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            draw.text((22, 26), "⚡ AI HIGHLIGHT", fill=(255, 255, 255, 255), font=font)
            img.save(output_path, "PNG")
            logger.info(f"Generated default watermark logo at: {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate default watermark logo: {e}")

    def _load_presets(self) -> List[Dict[str, Any]]:
        try:
            if self.presets_file.exists():
                return json.loads(self.presets_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load watermark presets: {e}")
        return []

    def _save_presets(self, presets: List[Dict[str, Any]]) -> None:
        try:
            self.presets_file.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save watermark presets: {e}")

    def get_all_presets(self) -> List[Dict[str, Any]]:
        """Return all saved watermark presets with absolute logo URLs."""
        presets = self._load_presets()
        for p in presets:
            logo_fn = p.get("logo_filename", "")
            p["logo_url"] = f"/api/v1/watermarks/logos/{logo_fn}" if logo_fn else None
            p["logo_exists"] = (self.logos_dir / logo_fn).exists() if logo_fn else False
        return presets

    def get_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Get a single preset by ID."""
        if not preset_id or preset_id == "none":
            return None
        presets = self.get_all_presets()
        for p in presets:
            if p.get("id") == preset_id:
                return p
        if preset_id == "default" and presets:
            return presets[0]
        return None

    def get_logo_path(self, filename: str) -> Optional[Path]:
        """Get absolute path to a logo file."""
        if not filename:
            return None
        safe_fn = Path(filename).name
        target = self.logos_dir / safe_fn
        return target if target.exists() else None

    def save_logo_file(self, file_bytes: bytes, original_filename: str) -> str:
        """Save an uploaded logo file and return the saved filename."""
        ext = Path(original_filename).suffix.lower()
        if not ext or ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
            ext = ".png"
        saved_filename = f"logo_{uuid.uuid4().hex[:10]}{ext}"
        target_path = self.logos_dir / saved_filename
        target_path.write_bytes(file_bytes)
        logger.info(f"Saved watermark logo: {saved_filename}")
        return saved_filename

    def create_preset(
        self,
        name: str,
        logo_filename: str,
        position: str = "bottom_right",
        scale_percent: int = 15,
        opacity: float = 0.85,
        margin: int = 24,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Create and store a new watermark preset."""
        preset_id = f"wm_{uuid.uuid4().hex[:8]}"
        new_preset = {
            "id": preset_id,
            "name": name.strip(),
            "logo_filename": logo_filename,
            "position": position,
            "scale_percent": max(5, min(50, scale_percent)),
            "opacity": max(0.05, min(1.0, float(opacity))),
            "margin": max(0, min(120, int(margin))),
            "is_default": bool(is_default),
            "created_at": datetime.utcnow().isoformat()
        }

        presets = self._load_presets()
        if is_default:
            for p in presets:
                p["is_default"] = False

        presets.append(new_preset)
        self._save_presets(presets)
        logger.info(f"Created watermark preset: {new_preset["name"]} ({preset_id})")
        return self.get_preset(preset_id) or new_preset

    def update_preset(self, preset_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing watermark preset."""
        presets = self._load_presets()
        updated = None
        for p in presets:
            if p.get("id") == preset_id:
                if "name" in updates and updates["name"]:
                    p["name"] = updates["name"].strip()
                if "logo_filename" in updates and updates["logo_filename"]:
                    p["logo_filename"] = updates["logo_filename"]
                if "position" in updates:
                    p["position"] = updates["position"]
                if "scale_percent" in updates:
                    p["scale_percent"] = max(5, min(50, int(updates["scale_percent"])))
                if "opacity" in updates:
                    p["opacity"] = max(0.05, min(1.0, float(updates["opacity"])))
                if "margin" in updates:
                    p["margin"] = max(0, min(120, int(updates["margin"])))
                if updates.get("is_default"):
                    for other in presets:
                        other["is_default"] = False
                    p["is_default"] = True
                updated = p
                break

        if updated:
            self._save_presets(presets)
            return self.get_preset(preset_id)
        return None

    def delete_preset(self, preset_id: str) -> bool:
        """Delete a watermark preset."""
        presets = self._load_presets()
        new_presets = [p for p in presets if p.get("id") != preset_id]
        if len(new_presets) < len(presets):
            self._save_presets(new_presets)
            logger.info(f"Deleted watermark preset: {preset_id}")
            return True
        return False


watermark_service = WatermarkService()
