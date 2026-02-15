# startServer.py

import os
from dotenv import load_dotenv
import uvicorn
from app.fastapp import app

load_dotenv()

if __name__ == "__main__":
    is_development = os.getenv("ENV") == "development"

    uvicorn.run(
        "app.fastapp:app",
        # host="localhost", # use localhost when run "python startServer.py"
        host="0.0.0.0",  # for docker containers
        port=8000,
        reload=is_development,
        reload_excludes=[
            ".venu",
            "chromadb",
            "chromaDocuments",
            "sqldb",
            "model_cache",
            "__pycache__",
        ],
        reload_includes="*.py",
        reload_delay=0.5,
        timeout_keep_alive=30,
    )
