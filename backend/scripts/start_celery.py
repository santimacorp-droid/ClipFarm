#!/usr/bin/env python3
"""
CeleryStart scriptCelery WorkerAndBeatScheduler
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Add project root directory toPythonPath
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def start_celery_worker():
    """StartCelery Worker"""
    print("🚀 StartCelery Worker...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--queues=processing,video,notification,maintenance",
        "--hostname=worker1@%h"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ Celery WorkerStarted (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ StartCelery WorkerFailed: {e}")
        return None

def start_celery_beat():
    """StartCelery BeatScheduler"""
    print("⏰ StartCelery BeatScheduler...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "beat",
        "--loglevel=info",
        "--schedule=/tmp/celerybeat-schedule",
        "--pidfile=/tmp/celerybeat.pid"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ Celery BeatStarted (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ StartCelery BeatFailed: {e}")
        return None

def start_flower():
    """StartFlowerMonitoring interface"""
    print("🌸 StartFlowerMonitoring interface...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "flower",
        "--port=5555",
        "--loglevel=info"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ FlowerStarted (PID: {process.pid})")
        print("🌐 FlowerMonitoring interface: http://localhost:5555")
        return process
    except Exception as e:
        print(f"❌ StartFlowerFailed: {e}")
        return None

def signal_handler(signum, frame):
    """Signal handling function"""
    print("\n🛑 Stopping due to signal, shutting down service...")
    sys.exit(0)

def main():
    """Main function"""
    print("🎯 AutoClip Celery Task queue launcher")
    print("=" * 50)
    
    # Set signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # CheckRedisConnection
    try:
        import redis
        r = redis.Redis.from_url('redis://localhost:6379/0')
        r.ping()
        print("✅ RedisConnection normal")
    except Exception as e:
        print(f"❌ RedisConnection failed: {e}")
        print("EnsureRedisService is running: redis-server")
        return
    
    # Start service
    processes = []
    
    # StartWorker
    worker_process = start_celery_worker()
    if worker_process:
        processes.append(worker_process)
    
    # StartBeat
    beat_process = start_celery_beat()
    if beat_process:
        processes.append(beat_process)
    
    # StartFlower
    flower_process = start_flower()
    if flower_process:
        processes.append(flower_process)
    
    if not processes:
        print("❌ None of the services started successfully")
        return
    
    print("\n🎉 All services started successfully!")
    print("📊 Service status:")
    print("   - Celery Worker: Process task")
    print("   - Celery Beat: Scheduled task execution")
    print("   - Flower: Task monitoring interface (http://localhost:5555)")
    print("\nPress Ctrl+C Stop all services")
    
    try:
        # Waiting for process
        while True:
            time.sleep(1)
            # Check if process is still running
            for process in processes:
                if process.poll() is not None:
                    print(f"⚠️  Process {process.pid} Exited")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down service...")
    finally:
        # Stop all processes
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                print(f"🛑 Process {process.pid} Stopped")

if __name__ == "__main__":
    main() 