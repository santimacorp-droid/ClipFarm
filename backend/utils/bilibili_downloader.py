#!/usr/bin/env python3
"""
BSite video downloader - Bilibili video and subtitle download implementation based on yt-dlp
Integrated into automatic segmenting tool project
"""

import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import yt_dlp

try:
    from .error_handler import FileIOError, ValidationError, ProcessingError
except ImportError:
    # Import in standalone execution
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from ..utils.error_handler import FileIOError, ValidationError, ProcessingError

logger = logging.getLogger(__name__)

class BilibiliVideoInfo:
    """BSite video information class"""
    def __init__(self, info_dict: Dict[str, Any]):
        self.bvid = info_dict.get('id', '')
        self.title = info_dict.get('title', 'unknown_video')
        self.duration = info_dict.get('duration', 0)
        self.uploader = info_dict.get('uploader', 'unknown')
        self.description = info_dict.get('description', '')
        self.thumbnail_url = info_dict.get('thumbnail', '')
        self.view_count = info_dict.get('view_count', 0)
        self.upload_date = info_dict.get('upload_date', '')
        self.webpage_url = info_dict.get('webpage_url', '')
    
    def to_dict(self) -> Dict[str, Any]:
        """Converted to dictionary format"""
        return {
            'bvid': self.bvid,
            'title': self.title,
            'duration': self.duration,
            'uploader': self.uploader,
            'description': self.description,
            'thumbnail_url': self.thumbnail_url,
            'view_count': self.view_count,
            'upload_date': self.upload_date,
            'webpage_url': self.webpage_url
        }

class BilibiliDownloader:
    """BSite video downloader"""
    
    def __init__(self, download_dir: Optional[Path] = None, browser: Optional[str] = None):
        """
        Initialized downloader
        
        Args:
            download_dir: Download directory, default is current directory
            browser: Browser type, used for obtainingcookies
        """
        self.download_dir = download_dir or Path.cwd()
        self.browser = browser
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    def validate_bilibili_url(self, url: str) -> bool:
        """
        Validate Bilibili video link format
        
        Args:
            url: Video link
            
        Returns:
            Is a valid Bilibili link
        """
        bilibili_patterns = [
            r'https?://www\.bilibili\.com/video/[Bb][Vv][0-9A-Za-z]+',
            r'https?://bilibili\.com/video/[Bb][Vv][0-9A-Za-z]+',
            r'https?://b23\.tv/[0-9A-Za-z]+',
            r'https?://www\.bilibili\.com/video/av\d+',
            r'https?://bilibili\.com/video/av\d+'
        ]
        
        return any(re.match(pattern, url) for pattern in bilibili_patterns)
    
    async def get_video_info(self, url: str) -> BilibiliVideoInfo:
        """
        Get video information (not downloading))
        
        Args:
            url: Video link
            
        Returns:
            Video information object
        """
        if not self.validate_bilibili_url(url):
            raise ValidationError(f"Invalid Bilibili video link: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        if self.browser:
            ydl_opts['cookiesfrombrowser'] = (self.browser.lower(),)
        
        try:
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(
                None, 
                self._extract_info_sync, 
                url, 
                ydl_opts
            )
            return BilibiliVideoInfo(info_dict)
        except Exception as e:
            raise ProcessingError(f"Getting video information failed: {str(e)}")
    
    def _extract_info_sync(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous method to extract video information"""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    async def download_video_and_subtitle(
        self, 
        url: str, 
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict[str, str]:
        """
        Download video and subtitle files
        
        Args:
            url: Video link
            progress_callback: Progress callback function, with parameters (status information, progress percentage))
            
        Returns:
            Dictionary containing video path and subtitle path
        """
        if not self.validate_bilibili_url(url):
            raise ValidationError(f"Invalid Bilibili video link: {url}")
        
        # Obtained video information
        video_info = await self.get_video_info(url)
        
        # Clean filename, remove special characters
        safe_title = self._sanitize_filename(video_info.title)
        
        # Set download options - improved subtitle download strategy
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'writesubtitles': True,
            'writeautomaticsub': True,  # Simultaneously attempt to download autogenerated subtitles
            'subtitleslangs': ['ai-zh', 'zh-Hans', 'zh', 'en'],  # Multiple subtitle languages
            'subtitlesformat': 'srt',  # Force SRT format
            'outtmpl': str(self.download_dir / f'{safe_title}.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'progress': True,
            'no_warnings': False,  # Display warning message for debugging
        }
        
        if self.browser:
            ydl_opts['cookiesfrombrowser'] = (self.browser.lower(),)
        
        # Added progress hook
        if progress_callback:
            ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback)]
        
        try:
            if progress_callback:
                progress_callback("Start downloading video and subtitles...", 0)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._download_sync,
                url,
                ydl_opts
            )
            
            # Found downloaded file
            video_path = self._find_downloaded_video(safe_title)
            subtitle_path = self._find_downloaded_subtitle(safe_title)
            
            # If no subtitles are found in the first attempt, try different subtitle retrieval strategies
            if not subtitle_path:
                logger.info("First subtitle download failed, attempt backup strategy...")
                subtitle_path = await self._try_alternative_subtitle_strategies(url, safe_title)
            
            if progress_callback:
                progress_callback("Download complete", 100)
            
            result = {
                'video_path': str(video_path) if video_path else '',
                'subtitle_path': str(subtitle_path) if subtitle_path else '',
                'video_info': video_info.to_dict()
            }
            
            logger.info(f"Download complete: {video_info.title}")
            return result
            
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            if progress_callback:
                progress_callback(error_msg, 0)
            raise ProcessingError(error_msg)
    
    async def _try_alternative_subtitle_strategies(self, url: str, safe_title: str) -> Optional[Path]:
        """Trying multiple subtitle retrieval strategies"""
        strategies = [
            self._try_download_with_different_langs,
            self._try_download_without_cookies,
            self._try_extract_from_video_metadata
        ]
        
        for strategy in strategies:
            try:
                subtitle_path = await strategy(url, safe_title)
                if subtitle_path:
                    logger.info(f"Subtitle fallback strategy succeeded: {strategy.__name__}")
                    return subtitle_path
            except Exception as e:
                logger.warning(f"Subtitle fallback strategy failed {strategy.__name__}: {e}")
                continue
        
        logger.warning("All subtitle retrieval strategies failed")
        return None
    
    async def _try_download_with_different_langs(self, url: str, safe_title: str) -> Optional[Path]:
        """Attempting to download subtitles in different languages"""
        logger.info("Attempting to download subtitles in different languages...")
        
        # Trying different subtitle language combinations
        lang_combinations = [
            ['zh-Hans', 'zh'],  # Simplified Chinese
            ['en', 'en-US'],    # English
            ['ai-zh'],          # AIChinese subtitles
            ['auto']            # Automatic detection
        ]
        
        for langs in lang_combinations:
            try:
                ydl_opts = {
                    'skip_download': True,  # Only download subtitles, do not download video
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': langs,
                    'subtitlesformat': 'srt',
                    'outtmpl': str(self.download_dir / f'{safe_title}_sub.%(ext)s'),
                    'noplaylist': True,
                    'quiet': True,
                }
                
                if self.browser:
                    ydl_opts['cookiesfrombrowser'] = (self.browser.lower(),)
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._download_sync, url, ydl_opts)
                
                # Find subtitle file
                subtitle_path = self._find_downloaded_subtitle(safe_title + "_sub")
                if subtitle_path:
                    return subtitle_path
                    
            except Exception as e:
                logger.debug(f"Attempt language {langs} Failed: {e}")
                continue
        
        return None
    
    async def _try_download_without_cookies(self, url: str, safe_title: str) -> Optional[Path]:
        """Attempt to download subtitles without using cookies (some public subtitles may not require login))"""
        logger.info("Try downloading subtitles without cookies...")
        
        try:
            ydl_opts = {
                'skip_download': True,  # Only download subtitles, do not download video
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['zh-Hans', 'zh', 'en'],
                'subtitlesformat': 'srt',
                'outtmpl': str(self.download_dir / f'{safe_title}_nocookie.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
            }
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, url, ydl_opts)
            
            subtitle_path = self._find_downloaded_subtitle(safe_title + "_nocookie")
            return subtitle_path
            
        except Exception as e:
            logger.debug(f"Downloading without cookies failed: {e}")
            return None
    
    async def _try_extract_from_video_metadata(self, url: str, safe_title: str) -> Optional[Path]:
        """Attempt to extract subtitle information from video metadata"""
        logger.info("Attempt to extract subtitle information from video metadata...")
        
        try:
            # Obtained video details
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            if self.browser:
                ydl_opts['cookiesfrombrowser'] = (self.browser.lower(),)
            
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(None, self._extract_info_sync, url, ydl_opts)
            
            # Check for subtitle information
            subtitles = info_dict.get('subtitles', {})
            auto_subtitles = info_dict.get('automatic_captions', {})
            
            if subtitles or auto_subtitles:
                logger.info(f"Found subtitle information: {list(subtitles.keys()) + list(auto_subtitles.keys())}")
                # Subtitle information can be further processed here
                return None  # Temporarily return None; can be extended later
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract video metadata: {e}")
            return None
    
    def _download_sync(self, url: str, ydl_opts: Dict[str, Any]):
        """Synchronous download method"""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    
    def _create_progress_hook(self, progress_callback: Callable[[str, float], None]):
        """Created progress callback hook"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and d['total_bytes']:
                    progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                elif '_percent_str' in d:
                    # Extract numeric value from percentage string
                    percent_str = d['_percent_str'].strip().rstrip('%')
                    try:
                        progress = float(percent_str)
                    except ValueError:
                        progress = 0
                else:
                    progress = 0
                
                speed = d.get('_speed_str', '')
                eta = d.get('_eta_str', '')
                status = f"Downloading... {speed} ETA: {eta}"
                progress_callback(status, progress)
            elif d['status'] == 'finished':
                progress_callback("Download complete, processing underway...", 95)
        
        return progress_hook
    
    def _sanitize_filename(self, filename: str) -> str:
        """Clean filename, remove unsafe characters"""
        # Remove or replace unsafe characters
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # Limit file name length
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename.strip()
    
    def _find_downloaded_video(self, title: str) -> Optional[Path]:
        """Looking for downloaded video file"""
        possible_extensions = ['.mp4', '.mkv', '.webm', '.flv']
        
        for ext in possible_extensions:
            video_path = self.download_dir / f"{title}{ext}"
            if video_path.exists():
                return video_path
        
        # If an exact match fails, attempt fuzzy matching
        for file_path in self.download_dir.glob(f"{title}*"):
            if file_path.suffix.lower() in possible_extensions:
                return file_path
        
        return None
    
    def _find_downloaded_subtitle(self, title: str) -> Optional[Path]:
        """Search for downloaded subtitle files - simplified version, focusing on AI subtitles"""
        logger.info(f"Finding subtitle file, title: {title}")
        
        # First check AI subtitle file
        ai_subtitle_path = self.download_dir / f"{title}.ai-zh.srt"
        if ai_subtitle_path.exists():
            # Renamed to standard format
            standard_path = self.download_dir / f"{title}.srt"
            if not standard_path.exists():
                ai_subtitle_path.rename(standard_path)
                logger.info(f"Rename AI subtitle file: {title}.ai-zh.srt -> {title}.srt")
                return standard_path
            return ai_subtitle_path
        
        # Check if it is already in standard format
        standard_path = self.download_dir / f"{title}.srt"
        if standard_path.exists():
            logger.info(f"Found standard subtitle file: {title}.srt")
            return standard_path
        
        # Found subtitles via fuzzy match
        for file_path in self.download_dir.glob(f"{title}*.srt"):
            logger.info(f"Found subtitle file: {file_path.name}")
            return file_path
        
        logger.warning(f"Subtitle file not found, title: {title}")
        return None
    
    def _convert_vtt_to_srt(self, vtt_path: Path, srt_path: Path):
        """Convert VTT subtitle file to standard SRT format"""
        try:
            with open(vtt_path, 'r', encoding='utf-8', errors='ignore') as vtt_file:
                vtt_content = vtt_file.read()
            
            def format_timestamp(ts: str) -> str:
                ts = ts.strip().replace('.', ',')
                parts = ts.split(':')
                if len(parts) == 2:
                    h = 0
                    m = int(parts[0])
                    sec_parts = parts[1].split(',')
                    s = int(sec_parts[0])
                    ms = int(sec_parts[1].ljust(3, '0')[:3]) if len(sec_parts) > 1 else 0
                elif len(parts) == 3:
                    h = int(parts[0])
                    m = int(parts[1])
                    sec_parts = parts[2].split(',')
                    s = int(sec_parts[0])
                    ms = int(sec_parts[1].ljust(3, '0')[:3]) if len(sec_parts) > 1 else 0
                else:
                    return ts
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            blocks = re.split(r'\n\s*\n', vtt_content.strip())
            srt_lines = []
            subtitle_count = 1
            
            for block in blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if not lines:
                    continue
                time_idx = -1
                for idx, line in enumerate(lines[:3]):
                    if '-->' in line:
                        time_idx = idx
                        break
                if time_idx == -1:
                    continue
                
                time_line = lines[time_idx]
                time_match = re.search(r'((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)', time_line)
                if not time_match:
                    continue
                
                start_srt = format_timestamp(time_match.group(1))
                end_srt = format_timestamp(time_match.group(2))
                
                text_lines = []
                for text_line in lines[time_idx + 1:]:
                    clean = re.sub(r'<[^>]+>', '', text_line).strip()
                    if clean:
                        text_lines.append(clean)
                
                if text_lines:
                    srt_lines.append(str(subtitle_count))
                    srt_lines.append(f"{start_srt} --> {end_srt}")
                    srt_lines.extend(text_lines)
                    srt_lines.append('')
                    subtitle_count += 1
            
            with open(srt_path, 'w', encoding='utf-8') as srt_file:
                srt_file.write('\n'.join(srt_lines) + '\n')
                
        except Exception as e:
            logger.error(f"VTTConversion to SRT failed: {e}")
            raise
    
    def cleanup_temp_files(self, title: str):
        """Clean up temporary files"""
        try:
            # Clean up possible temporary files
            for pattern in [f"{title}*.part", f"{title}*.tmp", f"{title}*.ytdl"]:
                for temp_file in self.download_dir.glob(pattern):
                    temp_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to clean temporary files: {e}")

# Convenience functions
async def download_bilibili_video(
    url: str, 
    download_dir: Optional[Path] = None,
    browser: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Dict[str, str]:
    """
    Convenient Bilibili video download function
    
    Args:
        url: BSite video links
        download_dir: Download directory
        browser: Browser type
        progress_callback: Progress callback function
        
    Returns:
        Dictionary containing video path and subtitle path
    """
    downloader = BilibiliDownloader(download_dir, browser)
    return await downloader.download_video_and_subtitle(url, progress_callback)

async def get_bilibili_video_info(url: str, browser: Optional[str] = None) -> BilibiliVideoInfo:
    """
    Convenient Bilibili video information retrieval function
    
    Args:
        url: BSite video links
        browser: Browser type
        
    Returns:
        Video information object
    """
    downloader = BilibiliDownloader(browser=browser)
    return await downloader.get_video_info(url)