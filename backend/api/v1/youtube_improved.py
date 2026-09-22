"""
ImprovedYouTubeDownload processing403Issues with error and exception handling
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class YouTubeDownloadError(Exception):
    """YouTubeDownload exception"""
    pass

class YouTubeDownloader:
    """ImprovedYouTubeDownloader"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
    async def download_video(
        self, 
        url: str, 
        output_dir: Path, 
        browser: Optional[str] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        DownloadingYouTubeVideo
        
        Args:
            url: YouTubeVideoURL
            output_dir: Output directory
            browser: Browser type (forcookies)
            retry_count: current retry count
            
        Returns:
            Contains dictionary with download information
        """
        
        try:
            # build download options
            ydl_opts = self._build_download_options(output_dir, browser)
            
            # execute download
            def download_sync():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # First retrieve video information
                    info = ydl.extract_info(url, download=False)
                    
                    # Checking if video is downloadable
                    if not self._is_video_downloadable(info):
                        raise YouTubeDownloadError(f"Video cannot be downloaded: {info.get('title', 'Unknown')}")
                    
                    # execute download
                    ydl.download([url])
                    
                    return info
            
            # Executing synchronous download in asynchronous environment
            loop = asyncio.get_event_loop()
            video_info = await loop.run_in_executor(None, download_sync)
            
            # Finding downloaded file
            video_files = list(output_dir.glob("*.mp4"))
            subtitle_files = list(output_dir.glob("*.srt"))
            
            if not video_files:
                raise YouTubeDownloadError("Video file download failed")
            
            return {
                "success": True,
                "video_file": video_files[0],
                "subtitle_file": subtitle_files[0] if subtitle_files else None,
                "video_info": video_info
            }
            
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error(f"YouTubedownload error: {error_msg}")
            
            # analyze error type
            if "HTTP Error 403" in error_msg:
                if retry_count < self.max_retries:
                    logger.info(f"403Error, attempting retry ({retry_count + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay)
                    return await self.download_video(url, output_dir, browser, retry_count + 1)
                else:
                    raise YouTubeDownloadError("Video access denied, may require login or video is protected")
            elif "Video unavailable" in error_msg:
                raise YouTubeDownloadError("Video unavailable, possibly deleted or set to private")
            elif "Private video" in error_msg:
                raise YouTubeDownloadError("Video is private, cannot download")
            else:
                raise YouTubeDownloadError(f"Download failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Unknown error occurred during download: {e}")
            raise YouTubeDownloadError(f"Download failed: {str(e)}")
    
    def _build_download_options(self, output_dir: Path, browser: Optional[str] = None) -> Dict[str, Any]:
        """build download options"""
        
        options = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-Hans', 'zh', 'en-US', 'auto'],
            'subtitlesformat': 'srt',
            'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': False,
            # AddedUser-Agentto avoid detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            # add retry mechanism
            'retries': 3,
            'fragment_retries': 3,
            # set timeout
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # If browser specified, usecookies
        if browser:
            options['cookiesfrombrowser'] = (browser.lower(),)
        
        return options
    
    def _is_video_downloadable(self, video_info: Dict[str, Any]) -> bool:
        """Checking if video is downloadable"""
        
        # Checking video status
        if video_info.get('availability') == 'private':
            return False
        
        if video_info.get('availability') == 'premium_only':
            return False
        
        # Checking for available formats
        formats = video_info.get('formats', [])
        if not formats:
            return False
        
        # Checking for video format
        video_formats = [f for f in formats if f.get('vcodec') != 'none']
        if not video_formats:
            return False
        
        return True

async def improved_youtube_download_task(
    task_id: str, 
    url: str, 
    project_name: str, 
    output_dir: Path,
    browser: Optional[str] = None
) -> Dict[str, Any]:
    """
    ImprovedYouTubedownload task handling
    
    Args:
        task_id: TaskID
        url: YouTubeVideoURL
        project_name: Project name
        output_dir: Output directory
        browser: browser type
        
    Returns:
        download result
    """
    
    downloader = YouTubeDownloader()
    
    try:
        logger.info(f"Starting downloadYouTubeVideo: {url}")
        
        # create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # execute download
        result = await downloader.download_video(url, output_dir, browser)
        
        logger.info(f"YouTubeVideo download successful: {result['video_file']}")
        
        return {
            "success": True,
            "task_id": task_id,
            "video_file": result["video_file"],
            "subtitle_file": result["subtitle_file"],
            "video_info": result["video_info"]
        }
        
    except YouTubeDownloadError as e:
        logger.error(f"YouTubeDownload failed: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "error_type": "download_error"
        }
        
    except Exception as e:
        logger.error(f"YouTubeUnknown error occurred during download: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "error_type": "unknown_error"
        }

# Usage example
async def main():
    """Testing improved download functionality"""
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    output_dir = Path("/tmp/youtube_test")
    task_id = str(uuid.uuid4())
    
    result = await improved_youtube_download_task(
        task_id=task_id,
        url=test_url,
        project_name="test project",
        output_dir=output_dir
    )
    
    if result["success"]:
        print(f"✅ Download successful: {result['video_file']}")
    else:
        print(f"❌ Download failed: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())

