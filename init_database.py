#!/usr/bin/env python3
"""
Database initialization script
"""

import sys
from pathlib import Path

# Add project root directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "backend"))

# Set working directory
import os
os.chdir(current_dir)

def init_database():
    """Initialize database"""
    print("🚀 Beginning database initialization...")
    
    try:
        # Import all models to ensure tables are created
        from backend.models import Base, BilibiliAccount, UploadRecord
        from backend.core.database import init_database, create_tables
        
        print("✅ All models imported successfully")
        
        # Initialize database
        if init_database():
            print("✅ Database initialization successful")
        else:
            print("❌ Database initialization failed")
            return False
        
        # Create table
        create_tables()
        print("✅ Database table creation successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    if success:
        print("\n🎉 Database initialization complete! ")
        print("Now you can start the system: ")
        print("1. ./start_autoclip_with_upload.sh")
        print("2. Or manually start individual services")
    else:
        print("\n❌ Database initialization failed. Please check error information")
        sys.exit(1)

