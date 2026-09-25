"""
Audio Enhancer Utility
Handles background music (BGM) mixing with sidechain ducking and sound effects (SFX).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
BGM_DIR = ASSETS_DIR / 'bgm'
SFX_DIR = ASSETS_DIR / 'sfx'
CUSTOM_BGM_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'custom_bgm'
CUSTOM_BGM_DIR.mkdir(parents=True, exist_ok=True)

BGM_TRACKS = {
    'suspense': {
        'id': 'suspense',
        'name': '🎬 Suspense & Drama',
        'description': 'Dark sub-bass drone for high-stakes or dramatic moments',
        'filename': 'suspense.wav',
        'default_volume': 0.18
    },
    'lofi': {
        'id': 'lofi',
        'name': '☕ Lofi Chill',
        'description': 'Warm, mellow ambient chords for storytelling & podcasts',
        'filename': 'lofi.wav',
        'default_volume': 0.20
    },
    'upbeat': {
        'id': 'upbeat',
        'name': '⚡ Upbeat Pulse',
        'description': 'Energetic rhythmic beat for high-energy hooks & gaming',
        'filename': 'upbeat.wav',
        'default_volume': 0.16
    }
}

SFX_TRACKS = {
    'pop': 'pop.wav',
    'ding': 'ding.wav',
    'whoosh': 'whoosh.wav'
}


class AudioEnhancer:
    @staticmethod
    def get_available_bgm_tracks() -> List[Dict[str, Any]]:
        """List available BGM presets and custom uploaded tracks."""
        tracks = [
            {
                'id': 'none',
                'name': '🔇 None (Original Audio Only)',
                'description': 'No background music',
                'default_volume': 0.0,
                'is_custom': False
            }
        ]
        # Presets
        for key, info in BGM_TRACKS.items():
            track_file = BGM_DIR / info['filename']
            if track_file.exists():
                tracks.append({
                    'id': key,
                    'name': info['name'],
                    'description': info['description'],
                    'default_volume': info['default_volume'],
                    'is_custom': False
                })
        # Custom uploaded tracks
        if CUSTOM_BGM_DIR.exists():
            for cf in sorted(CUSTOM_BGM_DIR.glob('*.*')):
                if cf.suffix.lower() in ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac']:
                    clean_name = cf.stem.replace('_', ' ')
                    tracks.append({
                        'id': f"custom:{cf.name}",
                        'name': f"🎵 {clean_name}",
                        'description': f"Custom uploaded audio ({cf.suffix.upper()})",
                        'default_volume': 0.20,
                        'is_custom': True,
                        'path': str(cf)
                    })
        return tracks

    @staticmethod
    def save_custom_bgm(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Save a user-uploaded custom BGM file."""
        import uuid
        import re
        CUSTOM_BGM_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        out_path = CUSTOM_BGM_DIR / unique_name
        out_path.write_bytes(file_bytes)
        logger.info(f"Saved custom BGM to {out_path}")
        return {
            'id': f"custom:{unique_name}",
            'name': f"🎵 {safe_name}",
            'filename': unique_name,
            'path': str(out_path),
            'default_volume': 0.20
        }

    @staticmethod
    def get_bgm_path(track_key: Optional[str] = None, custom_bgm_path: Optional[str] = None) -> Optional[Path]:
        """Get path to a specific BGM track or custom path."""
        # 1. If explicit custom path provided
        if custom_bgm_path:
            p = Path(custom_bgm_path)
            if p.exists():
                return p
            p_custom = CUSTOM_BGM_DIR / custom_bgm_path
            if p_custom.exists():
                return p_custom

        if not track_key or track_key == 'none':
            return None

        # 2. If track_key is custom:filename
        if track_key.startswith('custom:'):
            fn = track_key.split(':', 1)[1]
            p = CUSTOM_BGM_DIR / fn
            if p.exists():
                return p

        # 3. If built-in preset
        info = BGM_TRACKS.get(track_key.lower())
        if info:
            p = BGM_DIR / info['filename']
            if p.exists():
                return p
        return None

    @staticmethod
    def get_sfx_path(sfx_key: str) -> Optional[Path]:
        """Get path to a specific SFX track."""
        fn = SFX_TRACKS.get(sfx_key.lower())
        if fn:
            p = SFX_DIR / fn
            if p.exists():
                return p
        return None

    @classmethod
    def build_audio_filter_graph(
        cls,
        bgm_track: Optional[str] = None,
        bgm_volume: float = 0.18,
        sfx_enabled: bool = False,
        base_input_offset: int = 1,
        custom_bgm_path: Optional[str] = None
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Builds FFmpeg audio inputs and filter_complex graph for BGM mixing and SFX.
        
        Args:
            bgm_track: BGM preset key ('suspense', 'lofi', 'upbeat', 'none' or 'custom:...')
            bgm_volume: BGM volume float (0.05 to 0.6)
            sfx_enabled: Whether to trigger hook pop SFX
            base_input_offset: Index offset for extra -i inputs (after main video and watermark)
            custom_bgm_path: Optional direct file path to custom audio track
            
        Returns:
            Tuple of:
            - extra_ffmpeg_args: list of input flags, e.g. ['-stream_loop', '-1', '-i', bgm_path, ...]
            - audio_filter_fragment: filtergraph fragment to be joined with video filtergraph
            - final_audio_output_node: name of the output audio node, e.g. '[outa]'
        """
        extra_args: List[str] = []
        filter_parts: List[str] = []
        bgm_path = cls.get_bgm_path(bgm_track, custom_bgm_path)
        pop_sfx_path = cls.get_sfx_path('pop') if sfx_enabled else None
        has_bgm = bool(bgm_path and bgm_path.exists())
        has_sfx = bool(sfx_enabled and pop_sfx_path and pop_sfx_path.exists())

        if not has_bgm and not has_sfx:
            return [], None, None

        if has_bgm:
            filter_parts.append('[0:a]asetpts=PTS-STARTPTS,aresample=async=1,asplit=2[a_main][a_sidechain]')
        else:
            filter_parts.append('[0:a]asetpts=PTS-STARTPTS,aresample=async=1[a_main]')

        mix_inputs: List[str] = ['[a_main]']
        mix_weights: List[str] = ['1.0']

        current_input_idx = base_input_offset

        # 1. BGM Track with loop and true sidechain compression ducking
        if has_bgm and bgm_path:
            extra_args.extend(['-stream_loop', '-1', '-i', str(bgm_path)])
            bgm_vol = max(0.02, min(0.60, float(bgm_volume)))
            filter_parts.append(f'[{current_input_idx}:a]volume={bgm_vol:.2f}[bgm_raw]')
            # Sidechain ducking: when voice speaks, BGM ducks automatically by 12-16dB
            filter_parts.append(f'[bgm_raw][a_sidechain]sidechaincompress=threshold=0.03:ratio=4:attack=40:release=300[bgm_ducked]')
            mix_inputs.append('[bgm_ducked]')
            mix_weights.append('0.35')
            current_input_idx += 1

        # 2. Hook Pop SFX (triggered at 0.15s start)
        if has_sfx and pop_sfx_path:
            extra_args.extend(['-i', str(pop_sfx_path)])
            filter_parts.append(f'[{current_input_idx}:a]adelay=150|150,volume=0.65[sfx_pop]')
            mix_inputs.append('[sfx_pop]')
            mix_weights.append('0.70')
            current_input_idx += 1

        # Multi-input audio mixer
        input_nodes = ''.join(mix_inputs)
        weights_str = ' '.join(mix_weights)
        filter_parts.append(
            f'{input_nodes}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:weights={weights_str}[outa]'
        )

        return extra_args, ';'.join(filter_parts), '[outa]'