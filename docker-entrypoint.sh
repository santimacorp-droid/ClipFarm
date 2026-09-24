#!/bin/bash

# DockerContainer startup script
# Specifically forDockerEnvironment design, addressing permission and configuration issues

set -euo pipefail

# Set environment variables
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# Ensure data directory exists and has correct permissions
mkdir -p /app/data/projects /app/data/uploads /app/data/temp /app/data/output /app/logs

# If data directory is empty, create necessary files
if [[ ! -f /app/data/clipfarm.db && ! -f /app/data/autoclip.db ]]; then
    echo "Initialize database..."
    python -c "
import sys
sys.path.insert(0, '/app')
from backend.core.database import engine, Base
from backend.models import project, task, clip, collection, campaign
try:
    Base.metadata.create_all(bind=engine)
    print('Database initialization succeeded')
except Exception as e:
    print(f'Database initialization failed: {e}')
    sys.exit(1)
"
fi

# CheckRedisConnect
echo "CheckRedisConnect..."
python -c "
import os
import redis
try:
    redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    print(f'RedisConnection successful: {redis_url}')
except Exception as e:
    print(f'RedisConnection failed: {e}')
    print('Will useSQLiteAs fallback storage')
"

# Start application
echo "StartAutoClipApplication..."
exec "$@"