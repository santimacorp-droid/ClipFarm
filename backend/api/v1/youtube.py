"""
YouTubeRelatedAPIRouter handlerYouTubeVideo parsing and download functionality
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from ...core.config import get_data_directory
import uuid
import asyncio
from datetime import datetime
from contextlib import contextmanager
import os
import shutil
import yt_dlp

logger = logging.getLogger(__name__)
router = APIRouter()

# Storing download task state
download_tasks = {}


@contextmanager
def sanitized_yt_env():
    """Temporary cleanup and yt-dlp Relevant environment variables to avoid external configuration affecting behavior"""
    original_env = os.environ.copy()
    try:
        for key in list(os.environ.keys()):
            upper_key = key.upper()
            if upper_key.startswith("YT_DLP") or upper_key.startswith("YTDL") or upper_key.startswith("YOUTUBE_DL") or upper_key.startswith("YOUTUBEDL"):
                os.environ.pop(key, None)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original_env)

def _find_node_bin() -> Optional[str]:
    """Dynamically locates node binary across PATH, NVM, and standard directories without hardcoded usernames."""
    found = shutil.which("node")
    if found:
        return found
    candidates = [
        "/usr/local/bin/node",
        "/usr/bin/node",
        "/opt/homebrew/bin/node",
        "/home/linuxbrew/.linuxbrew/bin/node"
    ]
    nvm_dir = os.environ.get("NVM_DIR") or os.path.expanduser("~/.nvm")
    nvm_node_versions = Path(nvm_dir) / "versions" / "node"
    if nvm_node_versions.exists():
        try:
            for ver_dir in sorted(nvm_node_versions.iterdir(), reverse=True):
                cand = ver_dir / "bin" / "node"
                if cand.exists():
                    candidates.insert(0, str(cand))
                    break
        except Exception:
            pass
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None

class YouTubeParseRequest(BaseModel):
    url: str
    browser: Optional[str] = None

class YouTubeDownloadRequest(BaseModel):
    url: str
    project_name: Optional[str] = None
    video_category: Optional[str] = "default"
    browser: Optional[str] = None
    caption_style: Optional[str] = "hormozi_yellow"
    duration_mode: Optional[str] = "tiktok_crp"
    aspect_ratio: Optional[str] = "9:16_blur"
    show_hook_banner: Optional[bool] = True
    watermark_preset_id: Optional[str] = "none"

class YouTubeVideoInfo(BaseModel):
    title: str
    description: str
    duration: int
    uploader: str
    upload_date: str
    view_count: int
    like_count: int
    thumbnail: str

class YouTubeDownloadTask(BaseModel):
    id: str
    url: str
    project_name: str
    video_category: str
    status: str  # pending, processing, completed, failed
    progress: float
    error_message: Optional[str] = None
    project_id: Optional[str] = None
    created_at: str
    updated_at: str

def robust_extract_youtube_info(url: str, browser: Optional[str] = None, client: Optional[str] = None) -> Dict[str, Any]:
    """Use subprocess Call yt-dlp extracting YouTube Video metadata (supports Node.js JSsolver + Multiple browsersCookieAuto fallback)"""
    import subprocess
    import json
    import shutil
    
    project_root = Path(__file__).resolve().parents[3]
    venv_ytdlp = Path(sys.executable).parent / "yt-dlp"
    if venv_ytdlp.exists():
        ytdlp_bin = str(venv_ytdlp)
    elif (project_root / "venv" / "bin" / "yt-dlp").exists():
        ytdlp_bin = str(project_root / "venv" / "bin" / "yt-dlp")
    else:
        ytdlp_bin = shutil.which("yt-dlp") or "yt-dlp"

    node_bin = _find_node_bin()

    browser_candidates = [browser, None, "chrome", "firefox", "chromium"] if browser else [None, "chrome", "firefox", "chromium", "brave"]

    last_error = None
    env = os.environ.copy()
    for k in list(env.keys()):
        uk = k.upper()
        if uk.startswith('YT_DLP') or uk.startswith('YTDL') or uk.startswith('YOUTUBE_DL') or uk.startswith('YOUTUBEDL'):
            env.pop(k, None)

    for b in browser_candidates:
        cmd = [
            ytdlp_bin,
            '--ignore-config',
            '--no-warnings',
            '--no-playlist',
            '--dump-json',
            '--skip-download',
            '--no-cache-dir',
            '--remote-components', 'ejs:github'
        ]
        if node_bin and os.path.exists(node_bin):
            cmd.extend(['--js-runtimes', f'node:{node_bin}'])

        if b:
            cmd.extend(['--cookies-from-browser', b.lower()])

        yt_client = (client or os.getenv('AUTOCLIP_YT_CLIENT', '')).strip().lower()
        if yt_client in {"android", "ios", "tv"}:
            cmd.extend(['--extractor-args', f"youtube:player_client={yt_client}"])

        cmd.append(url)

        try:
            logger.info(f"Execute yt-dlp parsing (browser={b or 'none'}): {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(project_root),
                env=env
            )

            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            
            err_msg = result.stderr or result.stdout
            logger.warning(f"yt-dlp (browser={b or 'none'}) did not succeed: {err_msg[:200]}")
            last_error = err_msg

        except Exception as e:
            logger.warning(f"yt-dlp Execution error (browser={b}): {e}")
            last_error = str(e)

    raise Exception(f"yt-dlp execution failed: {last_error or 'Unable to parse video info'}")


@router.post("/parse")
async def parse_youtube_video(
    url: str = Form(...),
    browser: Optional[str] = Form(None),
    client: Optional[str] = Form(None)
):
    """parsingYouTubeVideo info"""
    try:
        logger.info(f"Beginning parsingYouTubeVideo: {url}")
        
        if "youtube.com" not in url and "youtu.be" not in url:
            raise HTTPException(status_code=400, detail="invalidYouTubeVideo link")
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(None, robust_extract_youtube_info, url, browser, client)
        
        logger.info(f"YouTubeVideo information parsed successfully: {info_dict.get('title', 'Unknown')}")
        
        return {
            "success": True,
            "video_info": {
                "title": info_dict.get('title', 'Unknown'),
                "description": info_dict.get('description', ''),
                "duration": info_dict.get('duration', 0) or 0,
                "uploader": info_dict.get('uploader', 'Unknown'),
                "upload_date": info_dict.get('upload_date', ''),
                "view_count": info_dict.get('view_count', 0),
                "like_count": info_dict.get('like_count', 0),
                "thumbnail": info_dict.get('thumbnail', '')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"parsingYouTubevideo failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"parsing failed: {str(e)}")

@router.post("/download")
async def create_youtube_download_task(request: YouTubeDownloadRequest):
    """CreateYouTubeVideo download task - immediately create project"""
    try:
        logger.info(f"CreateYouTubeDownload task: {request.url}")
        
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(None, robust_extract_youtube_info, request.url, request.browser)
        
        # Immediately create project record
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        from ...schemas.project import ProjectCreate, ProjectType, ProjectStatus
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # Process thumbnails - directly use parsed cover image
            thumbnail_data = None
            thumbnail_url = video_info.get('thumbnail', '')
            if thumbnail_url:
                try:
                    import requests
                    import base64
                    
                    # Download thumbnail
                    response = requests.get(thumbnail_url, timeout=10)
                    if response.status_code == 200:
                        # converted tobase64
                        thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                        thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                        logger.info(f"YouTubeThumbnail retrieved successfully: {video_info.get('title', 'Unknown')}")
                    else:
                        logger.warning(f"DownloadYouTubeThumbnail failed: {response.status_code}")
                except Exception as e:
                    logger.error(f"processingYouTubeThumbnail failed: {e}")
                    # Thumbnail processing failure does not affect main flow
            
            # Determine project name
            resolved_project_name = (request.project_name or '').strip() or video_info.get('title') or f"YouTube_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Creating project data
            project_data = ProjectCreate(
                name=resolved_project_name,
                description=f"Downloaded from YouTube: {video_info.get('title', 'Unknown')}",
                project_type=ProjectType(request.video_category),
                status=ProjectStatus.PENDING,  # Initial state is pending
                source_url=request.url,
                source_file=None,  # Temporarily empty, updated after download completes
                settings={
                    "download_status": "downloading",
                    "download_progress": 0.0,
                    "caption_style": request.caption_style or "hormozi_yellow",
                    "duration_mode": request.duration_mode or "tiktok_crp",
                    "aspect_ratio": request.aspect_ratio or "9:16_blur",
                    "show_hook_banner": True if request.show_hook_banner is None else request.show_hook_banner,
                    "watermark_preset_id": request.watermark_preset_id or "none",
                    "youtube_info": {
                        "url": request.url,
                        "browser": request.browser,
                        "title": video_info.get('title', 'Unknown'),
                        "uploader": video_info.get('uploader', 'Unknown'),
                        "duration": video_info.get('duration', 0),
                        "view_count": video_info.get('view_count', 0),
                        "thumbnail_url": thumbnail_url
                    }
                }
            )
            
            project = project_service.create_project(project_data)
            project_id = str(project.id)
            
            # Set thumbnail
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                db.commit()
                logger.info(f"Project {project_id} Thumbnail set")
            
            # Creating project directory
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Project created: {project_id}")
            
            # Generate download taskID
            task_id = str(uuid.uuid4())
            
            # Create task record
            task = YouTubeDownloadTask(
                id=task_id,
                url=request.url,
                project_name=resolved_project_name,
                video_category=request.video_category,
                status="pending",
                progress=0.0,
                project_id=project_id,  # associate projectID
                created_at=str(uuid.uuid1().time),
                updated_at=str(uuid.uuid1().time)
            )
            
            # Store task
            download_tasks[task_id] = task
            
            # Asynchronously launch download task - using secure task manager
            from .async_task_manager import task_manager
            await task_manager.create_safe_task(
                f"youtube_download_{task_id}", 
                process_youtube_download_task, 
                task_id, 
                request, 
                project_id
            )
            
            # Return project info, not task info
            return {
                "project_id": project_id,
                "task_id": task_id,
                "status": "created",
                "message": "Project created, downloading now..."
            }
            
        finally:
            db.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CreateYouTubeDownload task failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Task creation failed: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_youtube_task_status(task_id: str):
    """GetYouTubeDownload task status"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return download_tasks[task_id]

@router.get("/tasks")
async def get_all_youtube_tasks():
    """Get allYouTubeDownload task"""
    return list(download_tasks.values())

async def update_project_download_progress(project_id: str, progress: float, message: str):
    """Update project download progress"""
    try:
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            project = project_service.get(project_id)
            
            if project:
                from sqlalchemy.orm.attributes import flag_modified
                config = dict(project.processing_config or {})
                config.update({
                    "download_progress": round(progress, 1),
                    "download_message": message,
                    "download_status": "completed" if progress >= 100.0 else "downloading"
                })
                project.processing_config = config
                flag_modified(project, "processing_config")
                
                # If progress reaches100%, Updating status to pending processing
                if progress >= 100.0:
                    from ...schemas.project import ProjectStatus
                    project.status = ProjectStatus.PENDING
                
                db.commit()
                logger.info(f"Project {project_id} Download progress update: {progress}% - {message}")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to update project download progress: {e}")

async def process_youtube_download_task(task_id: str, request: YouTubeDownloadRequest, project_id: str):
    """processingYouTubeDownload task"""
    download_dir = None
    try:
        # Ensure task exists in memory dictionary
        if task_id not in download_tasks:
            download_tasks[task_id] = YouTubeDownloadTask(
                id=task_id,
                url=request.url,
                project_name=request.project_name,
                video_category=request.video_category,
                status="pending",
                progress=0.0,
                project_id=project_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

        # Updating task status to processing
        download_tasks[task_id].status = "processing"
        download_tasks[task_id].progress = 10.0
        
        # Updating project status and progress
        await update_project_download_progress(project_id, 10.0, "Fetching video information...")
        
        # Useyt-dlpDownload video
        import yt_dlp
        import asyncio
        from ...core.config import get_data_directory
        
        data_dir = get_data_directory()
        # Use dedicated task directory to prevent concurrent competition and reading stale files
        download_dir = data_dir / "temp" / f"yt_{task_id}"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Update project progress
        await update_project_download_progress(project_id, 5.0, "Connecting and starting download...")
        
        last_progress_time = [0.0]

        def ytdl_progress_hook(d):
            if d.get('status') == 'downloading':
                import time
                now = time.time()
                # Throttle DB writes to every 2s — HLS with 16 fragments fires hooks
                # extremely frequently; writing to DB every tick would cause contention.
                if now - last_progress_time[0] < 2.0:
                    return
                last_progress_time[0] = now

                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                speed = d.get('speed') or 0  # bytes/sec
                if total > 0:
                    pct = 5.0 + (downloaded / total) * 80.0  # Scale 5% → 85%
                    mb_done = round(downloaded / (1024 * 1024), 1)
                    mb_total = round(total / (1024 * 1024), 1)
                    raw_pct = round(downloaded / total * 100, 1)
                    if speed > 0:
                        speed_mb = round(speed / (1024 * 1024), 2)
                        msg = f"Downloading: {mb_done}MB / {mb_total}MB ({raw_pct}%) at {speed_mb} MB/s"
                    else:
                        msg = f"Downloading: {mb_done}MB / {mb_total}MB ({raw_pct}%)"
                    from ...core.database import SessionLocal
                    from ...services.project_service import ProjectService
                    from sqlalchemy.orm.attributes import flag_modified
                    db = SessionLocal()
                    try:
                        ps = ProjectService(db)
                        p = ps.get(project_id)
                        if p:
                            cfg = dict(p.processing_config or {})
                            cfg.update({
                                "download_progress": round(pct, 1),
                                "download_message": msg,
                                "download_status": "downloading"
                            })
                            p.processing_config = cfg
                            flag_modified(p, "processing_config")
                            db.commit()
                    except Exception:
                        pass
                    finally:
                        db.close()

        # Configure download options - prioritize HLS/m3u8 for speed (can use parallel fragments),
        def download_sync(url, browser):
            import subprocess
            import shutil
            import re
            import time
            from ...core.database import SessionLocal
            from ...services.project_service import ProjectService
            from sqlalchemy.orm.attributes import flag_modified
            
            project_root = Path(__file__).resolve().parents[3]
            venv_ytdlp = Path(sys.executable).parent / "yt-dlp"
            if venv_ytdlp.exists():
                ytdlp_bin = str(venv_ytdlp)
            elif (project_root / "venv" / "bin" / "yt-dlp").exists():
                ytdlp_bin = str(project_root / "venv" / "bin" / "yt-dlp")
            else:
                ytdlp_bin = shutil.which("yt-dlp") or "yt-dlp"

            node_bin = _find_node_bin()

            browser_candidates = [browser, None, "chrome", "firefox", "chromium"] if browser else [None, "chrome", "firefox", "chromium", "brave"]
            env = os.environ.copy()
            for k in list(env.keys()):
                uk = k.upper()
                if uk.startswith('YT_DLP') or uk.startswith('YTDL') or uk.startswith('YOUTUBE_DL') or uk.startswith('YOUTUBEDL'):
                    env.pop(k, None)

            # Parse timestamp if present in URL (e.g. t=1705 or t=4207s)
            import urllib.parse
            parsed_url = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed_url.query)
            timestamp_sec = None
            if 't' in qs:
                t_raw = qs['t'][0].rstrip('s')
                if t_raw.isdigit():
                    timestamp_sec = int(t_raw)
            elif 'start' in qs:
                s_raw = qs['start'][0].rstrip('s')
                if s_raw.isdigit():
                    timestamp_sec = int(s_raw)

            last_err = None
            for b in browser_candidates:
                cmd = [
                    ytdlp_bin,
                    '--ignore-config',
                    '--no-warnings',
                    '--no-playlist',
                    '--newline',
                    '--remote-components', 'ejs:github',
                    '--format', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                    '--merge-output-format', 'mp4',
                    '--extractor-args', 'youtube:player_client=android,web',
                    '--http-chunk-size', '10M',
                    '--write-subs', '--write-auto-subs', '--sub-lang', 'en,zh-Hans,zh,en-US,auto',
                    '--sub-format', 'srt/vtt/best',
                    '--output', str(download_dir / '%(title)s.%(ext)s'),
                    '--concurrent-fragments', '16',
                    '--retries', '10',
                ]

                if node_bin and os.path.exists(node_bin):
                    cmd.extend(['--js-runtimes', f'node:{node_bin}'])
                if b:
                    cmd.extend(['--cookies-from-browser', b.lower()])
                cmd.append(url)

                logger.info(f"Currently executingYouTubeVideo download (browser={b or 'none'}): {' '.join(cmd)}")
                
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True,
                        cwd=str(project_root),
                        env=env
                    )
                    
                    last_update = [0.0]
                    output_lines = []
                    
                    for line in process.stdout:
                        output_lines.append(line)
                        m = re.search(r'\[download\]\s+(\d+\.?\d*)%', line)
                        if m:
                            raw_pct = float(m.group(1))
                            now = time.time()
                            if now - last_update[0] >= 1.5:
                                last_update[0] = now
                                scaled_pct = 5.0 + (raw_pct * 0.80)  # 5% -> 85%
                                if task_id in download_tasks:
                                    download_tasks[task_id].progress = round(scaled_pct, 1)
                                
                                try:
                                    with SessionLocal() as db:
                                        ps = ProjectService(db)
                                        p = ps.get(project_id)
                                        if p:
                                            cfg = dict(p.processing_config or {})
                                            cfg.update({
                                                "download_progress": round(scaled_pct, 1),
                                                "download_message": f"Downloading: {round(raw_pct, 1)}%",
                                                "download_status": "downloading"
                                            })
                                            p.processing_config = cfg
                                            flag_modified(p, "processing_config")
                                            db.commit()
                                except Exception:
                                    pass

                    process.wait()
                    if process.returncode == 0:
                        return True
                    
                    last_err = "".join(output_lines[-10:])
                    logger.warning(f"Download attempt failed (browser={b or 'none'}): {last_err[:200]}")

                except Exception as ex:
                    last_err = str(ex)
                    logger.warning(f"download error (browser={b}): {ex}")

            raise Exception(f"YouTube download failed: {last_err or 'Unknown download error'}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_sync, request.url, request.browser)
        
        # Finding downloaded file(s)
        video_files = list(download_dir.glob("*.mp4")) or list(download_dir.glob("*.mkv")) or list(download_dir.glob("*.webm"))
        subtitle_files = list(download_dir.glob("*.srt"))
        
        # if onlyVTTSubtitles converted toSRT
        if not subtitle_files:
            vtt_files = list(download_dir.glob("*.vtt"))
            if vtt_files:
                try:
                    import re
                    vtt_file = vtt_files[0]
                    srt_file = vtt_file.with_suffix(".srt")
                    with open(vtt_file, 'r', encoding='utf-8', errors='ignore') as vf:
                        vtt_text = vf.read()
                    lines = vtt_text.splitlines()
                    srt_lines = []
                    counter = 1
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.startswith("WEBVTT") or line.startswith("NOTE") or not line:
                            i += 1
                            continue
                        if "-->" in line:
                            formatted_ts = re.sub(r'(\d{2}:\d{2}:\d{2})\.(\d{3})', r'\1,\2', line)
                            formatted_ts = re.sub(r' align:\S+| position:\S+| line:\S+', '', formatted_ts)
                            srt_lines.append(str(counter))
                            srt_lines.append(formatted_ts)
                            counter += 1
                            i += 1
                            while i < len(lines) and lines[i].strip():
                                clean_line = re.sub(r'<[^>]+>', '', lines[i].strip())
                                srt_lines.append(clean_line)
                                i += 1
                            srt_lines.append("")
                        i += 1
                    with open(srt_file, 'w', encoding='utf-8') as sf:
                        sf.write("\n".join(srt_lines))
                    subtitle_files = [srt_file]
                    logger.info(f"Successfully converted YouTube VTT to SRT: {srt_file}")
                except Exception as conv_err:
                    logger.warning(f"Failed to convert VTT to SRT: {conv_err}")

        if not video_files:
            raise Exception("No downloaded video file found in task directory")
        
        video_path = str(video_files[0])
        subtitle_path = str(subtitle_files[0]) if subtitle_files else ""
        
        download_tasks[task_id].progress = 85.0
        
        # Update project progress
        await update_project_download_progress(project_id, 85.0, "Video downloaded, preparing subtitles...")
        
        # If no subtitle file, prioritize usingWhisperGenerate subtitles
        if not subtitle_path:
            logger.info("Prefer usingWhisperGenerating high‑quality subtitles")
            # Update project progress
            await update_project_download_progress(project_id, 90.0, "Generating subtitles with Whisper...")
            
            try:
                from ...utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                video_file_path = Path(video_path)
                
                # Choose appropriate model based on video information
                model = "base"  # Defaulting to balanced model
                language = "auto"  # Default auto-detection of language
                
                logger.info(f"UseWhisperGenerating subtitles - language: {language}, Model: {model}")
                
                generated_subtitle = generate_subtitle_for_video(
                    video_file_path,
                    language=language,
                    model=model
                )
                subtitle_path = str(generated_subtitle)
                logger.info(f"WhisperSubtitles generated successfully: {subtitle_path}")
                
                # Update project progress
                await update_project_download_progress(project_id, 95.0, "Subtitles generated, finalizing import...")
                
            except SpeechRecognitionError as e:
                logger.error(f"WhisperSubtitle generation failed: {e}")
                # WhisperOn failure, try multiple strategies to obtain platform subtitles as backup
                logger.info("Attempt to download platform subtitles as backup solution")
                try:
                    subtitle_path = await _try_youtube_subtitle_strategies(request.url, download_dir, request.browser)
                    if subtitle_path:
                        logger.info(f"Fallback subtitles retrieved successfully: {subtitle_path}")
                    else:
                        logger.warning("All subtitle retrieval strategies failed")
                        subtitle_path = None  # Ensure subtitle path is empty; the project will later be marked as failed
                except Exception as backup_error:
                    logger.error(f"Backup subtitle fetching also failed: {backup_error}")
                    subtitle_path = None  # Ensure subtitle path is empty; the project will later be marked as failed
            except Exception as e:
                logger.error(f"Unknown error occurred during subtitle generation: {e}")
                subtitle_path = None  # Ensure subtitle path is empty; the project will later be marked as failed
        
        logger.info(f"Download complete - video file: {video_path}, Subtitle file: {subtitle_path}")
        
        # Update project information (project already created at start))
        from ...services.project_service import ProjectService
        from ...core.database import SessionLocal
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # Retrieve created project
            project = project_service.get(project_id)
            if not project:
                raise Exception(f"Project {project_id} does not exist")
            
            # Updating project information
            project.description = f"Downloaded from YouTube: {request.project_name}"
            # Note: Do not set this herevideo_path, Set after file move completes
            
            # Update project settings
            if not project.processing_config:
                project.processing_config = {}
            
            project.processing_config.update({
                "youtube_info": {
                    "title": request.project_name,
                    "uploader": "YouTube",
                    "duration": 0,
                    "view_count": 0,
                    "like_count": 0
                },
                "subtitle_path": subtitle_path,
                "download_status": "completed",
                "download_progress": 100.0
            })
            
            # Moving file to project directory
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Move video file to project directory
            import shutil
            
            if video_path:
                video_file_path = Path(video_path)
                if video_file_path.exists():
                    # Rename video file toinput.mp4
                    new_video_path = raw_dir / "input.mp4"
                    shutil.move(str(video_file_path), str(new_video_path))
                    logger.info(f"Video file moved to: {new_video_path}")
                    
                    # Updating video path in project
                    project.video_path = str(new_video_path)
            
            # Move subtitle file to project directory
            if subtitle_path:
                subtitle_file_path = Path(subtitle_path)
                if subtitle_file_path.exists():
                    # Rename subtitle file toinput.srt
                    new_subtitle_path = raw_dir / "input.srt"
                    shutil.move(str(subtitle_file_path), str(new_subtitle_path))
                    logger.info(f"Subtitle file moved to: {new_subtitle_path}")
                    
                    # Update subtitle path in project processing configuration
                    if not project.processing_config:
                        project.processing_config = {}
                    project.processing_config["subtitle_path"] = str(new_subtitle_path)
            
            # Clean up dedicated task temporary download directory
            try:
                shutil.rmtree(str(download_dir), ignore_errors=True)
            except Exception:
                pass

            # Save project update
            db.commit()
            
            # Check if subtitle file exists; mark project as failed if it does not exist
            srt_file_path = raw_dir / "input.srt"
            if not srt_file_path.exists():
                logger.error(f"Subtitle file does not exist: {srt_file_path}, marking project as failed")
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.FAILED
                if not project.processing_config:
                    project.processing_config = {}
                project.processing_config["error_message"] = "Subtitle file not found and Whisper transcription failed"
                db.commit()
                
                # Updating task status to failed
                download_tasks[task_id].status = "failed"
                download_tasks[task_id].error_message = "Subtitle file not found and Whisper transcription failed"
                download_tasks[task_id].progress = 0.0
                download_tasks[task_id].project_id = str(project.id)
                download_tasks[task_id].updated_at = datetime.now().isoformat()
                
                # Update project download progress to failed
                await update_project_download_progress(project_id, 0.0, "Download failed: Subtitle file not found")
                
                logger.info(f"YouTube download task failed: {task_id}, project: {project.id}, reason: subtitle missing")
                return
            
            # Update project download progress to complete
            await update_project_download_progress(project_id, 100.0, "Download completed, ready for processing")
            
            # Updating task status
            download_tasks[task_id].status = "completed"
            download_tasks[task_id].progress = 100.0
            download_tasks[task_id].project_id = str(project.id)
            download_tasks[task_id].updated_at = datetime.now().isoformat()
            
            logger.info(f"YouTubeDownload task completed: {task_id}, ProjectID: {project.id}")
            
            # Immediately initiate processing workflow
            try:
                # Update project status to pending processing
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.PENDING  # ChangePENDING, Trigger automation service start
                db.commit()
                
                logger.info(f"YouTubeProject {project.id} Download complete, waiting for automation pipeline to start")
                
                # Asynchronously start automation pipeline
                import asyncio
                from ...services.auto_pipeline_service import auto_pipeline_service
                
                # Usecreate_taskExecute in running event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Create task in already running event loop
                    task = loop.create_task(
                        auto_pipeline_service.auto_start_pipeline(str(project.id))
                    )
                    # Waiting for task completion
                    pipeline_result = await task
                except RuntimeError:
                    # Create new event loop if none is running
                    pipeline_result = await auto_pipeline_service.auto_start_pipeline(str(project.id))
                
                if pipeline_result['status'] == 'started':
                    logger.info(f"YouTubeProject {project.id} Automation pipeline started successfully: {pipeline_result}")
                else:
                    logger.warning(f"YouTubeProject {project.id} Automation pipeline startup result: {pipeline_result}")
                
            except Exception as e:
                logger.error(f"startYouTubeProject {project.id} Automation pipeline failed: {str(e)}")
                # Even when startup fails, return download success
                # Users can restart processing via the retry button
            
        except Exception as e:
            logger.error(f"Project creation failed: {str(e)}")
            # Even when startup fails, return download success
            # Users can restart processing via the retry button
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to process download task: {str(e)}")
        if task_id in download_tasks:
            download_tasks[task_id].status = "failed"
            download_tasks[task_id].error_message = str(e)
            download_tasks[task_id].progress = 0.0
            download_tasks[task_id].updated_at = datetime.now().isoformat()
    finally:
        if download_dir and download_dir.exists():
            import shutil
            try:
                shutil.rmtree(str(download_dir), ignore_errors=True)
            except Exception:
                pass


async def _try_youtube_subtitle_strategies(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """try multipleYouTubeSubtitle fetching strategy"""
    strategies = [
        lambda: _try_download_with_different_formats(url, download_dir, browser),
        lambda: _try_download_with_different_langs(url, download_dir, browser),
        lambda: _try_extract_from_metadata(url, download_dir, browser)
    ]
    
    for strategy in strategies:
        try:
            subtitle_path = await strategy()
            if subtitle_path:
                logger.info(f"YouTubeFallback subtitle strategy succeeded")
                return subtitle_path
        except Exception as e:
            logger.warning(f"YouTubeFallback subtitle strategy failed: {e}")
            continue
    
    logger.warning("allYouTubeAll subtitle fetching strategies failed")
    return ""


async def _try_download_with_different_formats(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """Try downloading subtitles in different formats"""
    import asyncio
    logger.info("Trying to download different formats ofYouTubeSubtitles...")
    
    formats = ['srt', 'vtt', 'json3']
    
    for fmt in formats:
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'zh-Hans', 'zh'],
                'subtitlesformat': fmt,
                'outtmpl': str(download_dir / f'subtitle_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'ignoreconfig': True,
                'config_locations': [],
            }
            
            if browser:
                ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
            
            def download_sync(url, ydl_opts):
                with sanitized_yt_env():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_sync, url, ydl_opts)
            
            # Looking for downloaded subtitle file
            subtitle_files = list(download_dir.glob(f"*.{fmt}"))
            if subtitle_files:
                subtitle_path = str(subtitle_files[0])
                
                # if it isVTTFormat, converted toSRT
                if fmt == 'vtt':
                    srt_path = subtitle_path.replace('.vtt', '.srt')
                    await _convert_vtt_to_srt(subtitle_path, srt_path)
                    return srt_path
                
                return subtitle_path
                
        except Exception as e:
            logger.debug(f"Try format {fmt} Failed: {e}")
            continue
    
    return ""


async def _try_download_with_different_langs(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """Try downloading subtitles in different languages"""
    import asyncio
    logger.info("Trying to download different languages ofYouTubeSubtitles...")
    
    lang_combinations = [
        ['en', 'en-US'],      # English
        ['zh-Hans', 'zh'],    # Chinese
        ['ja', 'ja-JP'],      # Japanese
        ['ko', 'ko-KR'],      # Korean
        ['auto']              # automatic detection
    ]
    
    for langs in lang_combinations:
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': langs,
                'subtitlesformat': 'srt',
                'outtmpl': str(download_dir / f'lang_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'ignoreconfig': True,
                'config_locations': [],
            }
            
            if browser:
                ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
            
            def download_sync(url, ydl_opts):
                with sanitized_yt_env():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_sync, url, ydl_opts)
            
            # Looking for downloaded subtitle file
            subtitle_files = list(download_dir.glob("*.srt"))
            if subtitle_files:
                return str(subtitle_files[0])
                
        except Exception as e:
            logger.debug(f"Try language {langs} Failed: {e}")
            continue
    
    return ""


async def _try_extract_from_metadata(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """Attempt to extract subtitle information from video metadata"""
    import asyncio
    logger.info("try fromYouTubeExtract subtitle information from video metadata...")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreconfig': True,
            'config_locations': [],
        }
        
        if browser:
            ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
        
        def extract_info_sync(url, ydl_opts):
            with sanitized_yt_env():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(None, extract_info_sync, url, ydl_opts)
        
        # Checking for subtitle information
        subtitles = info_dict.get('subtitles', {})
        auto_subtitles = info_dict.get('automatic_captions', {})
        
        if subtitles or auto_subtitles:
            logger.info(f"DiscoverYouTubeSubtitle info: {list(subtitles.keys()) + list(auto_subtitles.keys())}")
            # Further processing of subtitle information can be added here, but an empty string is returned for now
            return ""
        
        return ""
        
    except Exception as e:
        logger.debug(f"extractingYouTubeVideo metadata retrieval failed: {e}")
        return ""


async def _convert_vtt_to_srt(vtt_path: str, srt_path: str):
    """toVTTSubtitle file conversion toSRTformat"""
    try:
        with open(vtt_path, 'r', encoding='utf-8') as vtt_file:
            vtt_content = vtt_file.read()
        
        # simpleVTTintoSRTConvert
        lines = vtt_content.split('\n')
        srt_lines = []
        subtitle_count = 1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # SkipVTTHeader info
            if line.startswith('WEBVTT') or line.startswith('NOTE') or not line:
                i += 1
                continue
            
            # Find timestamp line
            if '-->' in line:
                # Converting time format (VTTusing dot, SRTUse commas)
                time_line = line.replace('.', ',')
                srt_lines.append(str(subtitle_count))
                srt_lines.append(time_line)
                
                # Getting subtitle text
                i += 1
                subtitle_text = []
                while i < len(lines) and lines[i].strip():
                    subtitle_text.append(lines[i].strip())
                    i += 1
                
                srt_lines.extend(subtitle_text)
                srt_lines.append('')  # Blank line separator
                subtitle_count += 1
            
            i += 1
        
        # WriteSRTfile
        with open(srt_path, 'w', encoding='utf-8') as srt_file:
            srt_file.write('\n'.join(srt_lines))
            
        logger.info(f"VTTconversionSRTconversion successful: {vtt_path} -> {srt_path}")
        
    except Exception as e:
        logger.error(f"VTTconversionSRTConversion failed: {e}")
        raise
