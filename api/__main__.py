"""Allow running the API with: python -m api"""

import sys
import threading
import webbrowser

URL = "http://localhost:8000"
DELAY = 1.5


def _open_browser():
    webbrowser.open(URL)


if __name__ == "__main__":
    frozen = getattr(sys, "frozen", False)

    if frozen:
        print("=" * 50)
        print("  Folder Analyzer v3.0  -  Caza Bytes")
        print("=" * 50)
        print(f"  Open your browser: {URL}")
        print("  Press Ctrl+C to stop the server.")
        print("=" * 50)
        threading.Timer(DELAY, _open_browser).start()

    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=not frozen,
    )
