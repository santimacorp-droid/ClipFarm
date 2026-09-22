#!/usr/bin/env python3
"""
Test link import project thumbnail function
"""

import sys
import asyncio
from pathlib import Path

# Adding project root directory to...PythonPath
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.utils.bilibili_downloader import BilibiliDownloader
import requests
import base64

async def test_bilibili_thumbnail_extraction():
    """TestBSite thumbnail extraction function"""
    print("🧪 TestBSite thumbnail extraction function...")
    
    # Using one public...BTesting site video link
    test_url = "https://www.bilibili.com/video/BV1LSegzbEp9/"
    
    try:
        # Create downloader
        downloader = BilibiliDownloader()
        
        # Get video information
        video_info = await downloader.get_video_info(test_url)
        
        print(f"✅ Video information retrieved successfully:")
        print(f"   Title: {video_info.title}")
        print(f"   Uploader: {video_info.uploader}")
        print(f"   ThumbnailURL: {video_info.thumbnail_url}")
        
        # Test thumbnail download
        if video_info.thumbnail_url:
            print("🖼️  Test thumbnail download...")
            response = requests.get(video_info.thumbnail_url, timeout=10)
            if response.status_code == 200:
                # Convert tobase64
                thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                
                print(f"✅ Thumbnail downloaded successfully, size: {size}: {len(response.content)} bytes")
                print(f"   Base64Length: {len(thumbnail_base64)} Character")
                print(f"   DataURIPrefix: {thumbnail_data[:50]}...")
                
                return True
            else:
                print(f"❌ Thumbnail download failed: HTTP {response.status_code}")
                return False
        else:
            print("⚠️  No thumbnail availableURL")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_youtube_thumbnail_extraction():
    """TestYouTubeThumbnail extraction function"""
    print("\n🧪 TestYouTubeThumbnail extraction function...")
    
    # Using one public...YouTubeTesting video link
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        def extract_info_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(None, extract_info_sync, test_url, ydl_opts)
        
        print(f"✅ Video information retrieved successfully:")
        print(f"   Title: {video_info.get('title', 'Unknown')}")
        print(f"   Uploader: {video_info.get('uploader', 'Unknown')}")
        print(f"   ThumbnailURL: {video_info.get('thumbnail', '')}")
        
        # Test thumbnail download
        thumbnail_url = video_info.get('thumbnail', '')
        if thumbnail_url:
            print("🖼️  Test thumbnail download...")
            response = requests.get(thumbnail_url, timeout=10)
            if response.status_code == 200:
                # Convert tobase64
                thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                
                print(f"✅ Thumbnail downloaded successfully, size: {size}: {len(response.content)} bytes")
                print(f"   Base64Length: {len(thumbnail_base64)} Character")
                print(f"   DataURIPrefix: {thumbnail_data[:50]}...")
                
                return True
            else:
                print(f"❌ Thumbnail download failed: HTTP {response.status_code}")
                return False
        else:
            print("⚠️  No thumbnail availableURL")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    """Main function"""
    print("🚀 Starting test for link import project thumbnail feature...\n")
    
    # TestBSite thumbnail extraction
    bilibili_success = await test_bilibili_thumbnail_extraction()
    
    # TestYouTubeThumbnail extraction
    youtube_success = await test_youtube_thumbnail_extraction()
    
    print(f"\n📊 Test results:")
    print(f"   BSite thumbnail extraction: {'✅ Success' if bilibili_success else '❌ Failed'}")
    print(f"   YouTubeThumbnail extraction: {'✅ Success' if youtube_success else '❌ Failed'}")
    
    if bilibili_success and youtube_success:
        print("\n🎉 All tests passed! Link import project thumbnail feature works fine")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check related function")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
