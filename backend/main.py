"""FastAPIApplication entry point - WebMode"""

import logging
from backend.app_factory import create_app

# Creating app instance
app = create_app(mode="web")

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Default port
    port = 8000
    
    # Checking command-line parameters
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    logger.error(f"Invalid port number: {sys.argv[i + 1]}")
                    port = 8000
    
    logger.info(f"Starting server, port: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)