# startServer.py

from dotenv import load_dotenv
import uvicorn
from app.fastapp import app

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.fastapp:app",
        host="localhost",
        port=8000,
        reload=True,
        reload_dirs="app",
        reload_delay=0.5,
        workers=2,
        timeout_keep_alive=30,
    )
