#!/usr/bin/env python3
"""
AddthumbnailAdding field toprojectsTable script for
"""

import sys
from pathlib import Path

# AddbackendAdding toPythonPath
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Adding project root directory toPythonPath
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.core.database import engine, SessionLocal
from sqlalchemy import text

def add_thumbnail_column():
    """AddthumbnailAdding field toprojectsTable"""
    try:
        # Check if field exists
        with engine.connect() as conn:
            # ForSQLite, Checking table structure
            result = conn.execute(text("PRAGMA table_info(projects)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'thumbnail' in columns:
                print("✅ thumbnailField already exists, not adding")
                return True
            
            # AddthumbnailField
            conn.execute(text("ALTER TABLE projects ADD COLUMN thumbnail TEXT"))
            conn.commit()
            print("✅ Successfully addedthumbnailAdding field toprojectsTable")
            return True
            
    except Exception as e:
        print(f"❌ AddthumbnailField failed: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Starting to addthumbnailField...")
    
    if add_thumbnail_column():
        print("🎉 thumbnailField added successfully! ")
    else:
        print("❌ thumbnailFailed to add field")
        sys.exit(1)

if __name__ == "__main__":
    main()
