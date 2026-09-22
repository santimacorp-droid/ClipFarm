#!/usr/bin/env python3
"""
WhisperProcess monitor toolWhisperProcess
"""

import psutil
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_whisper_processes():
    """Looking up all running instancesWhisperProcess"""
    whisper_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            cmdline = proc.info['cmdline'] or []
            if 'whisper' in proc.info['name'].lower() or any('whisper' in str(arg).lower() for arg in cmdline):
                whisper_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': ' '.join(cmdline),
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return whisper_processes

def check_duplicate_whisper_processes():
    """Checking for existing duplicatesWhisperProcesses handling the same file"""
    whisper_processes = find_whisper_processes()
    
    if not whisper_processes:
        logger.info("Not foundWhisperProcess")
        return True
    
    logger.info(f"Found {len(whisper_processes)} CountWhisperProcess:")
    
    # Grouping by video file
    video_files = {}
    for proc in whisper_processes:
        cmdline = proc['cmdline']
        # Extracting video file paths
        parts = cmdline.split()
        video_file = None
        for i, part in enumerate(parts):
            if part.endswith(('.mp4', '.avi', '.mkv', '.mov', '.wav', '.mp3')):
                video_file = part
                break
        
        if video_file:
            if video_file not in video_files:
                video_files[video_file] = []
            video_files[video_file].append(proc)
    
    # Checking duplicate processing
    duplicates_found = False
    for video_file, processes in video_files.items():
        if len(processes) > 1:
            logger.warning(f"Found duplicate file processing {video_file}:")
            duplicates_found = True
            for proc in processes:
                logger.warning(f"  PID {proc['pid']}: CPU {proc['cpu_percent']:.1f}%, Memory {proc['memory_mb']:.1f}MB")
    
    if not duplicates_found:
        logger.info("No duplicate processing foundWhisperProcess")
    
    return not duplicates_found

def kill_duplicate_whisper_processes():
    """Terminated duplicatesWhisperProcess"""
    whisper_processes = find_whisper_processes()
    
    if not whisper_processes:
        logger.info("NoWhisperProcess needs to be terminated")
        return
    
    # Grouping by video file
    video_files = {}
    for proc in whisper_processes:
        cmdline = proc['cmdline']
        parts = cmdline.split()
        video_file = None
        for i, part in enumerate(parts):
            if part.endswith(('.mp4', '.avi', '.mkv', '.mov', '.wav', '.mp3')):
                video_file = part
                break
        
        if video_file:
            if video_file not in video_files:
                video_files[video_file] = []
            video_files[video_file].append(proc)
    
    # KeepCPUFor detecting and preventing duplicates
    for video_file, processes in video_files.items():
        if len(processes) > 1:
            logger.info(f"Handling duplicate processes - by file: {video_file}")
            
            # ByCPUBy usage rank, keeping the top ones
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            keep_process = processes[0]
            
            logger.info(f"Keep process PID {keep_process['pid']} (CPU: {keep_process['cpu_percent']:.1f}%)")
            
            # Terminating other processes
            for proc in processes[1:]:
                try:
                    logger.info(f"Terminating duplicate processes PID {proc['pid']}")
                    psutil.Process(proc['pid']).terminate()
                except psutil.NoSuchProcess:
                    logger.info(f"Process PID {proc['pid']} Already does not exist")
                except psutil.AccessDenied:
                    logger.error(f"Unable to terminate process PID {proc['pid']} (Insufficient permissions)")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--kill-duplicates':
        logger.info("Checking and terminating duplicatesWhisperProcess...")
        kill_duplicate_whisper_processes()
    else:
        logger.info("CheckWhisperProcess state...")
        if check_duplicate_whisper_processes():
            logger.info("✅ System state is healthy")
            sys.exit(0)
        else:
            logger.warning("⚠️ Duplicate foundWhisperProcess")
            sys.exit(1)

if __name__ == '__main__':
    main()
