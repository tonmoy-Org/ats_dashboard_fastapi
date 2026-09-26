import sys
import os
import uvicorn

from config import HOST, PORT

def main():
    display_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    print("=" * 60)
    print(" 🚀 Starting ATS Recovery Pro FastAPI Backend...")
    print("=" * 60)
    print(f" Host: http://{display_host}:{PORT}")
    print(f" Docs: http://{display_host}:{PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
