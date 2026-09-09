"""Allow running the API with: python -m api"""

import os
import uvicorn

if __name__ == "__main__":
    # Development reload is opt-in (FOLDER_ANALYZER_RELOAD=1). Scan state lives
    # on app.state and is intentionally per-process; a reloader restarts it.
    reload_dev = os.environ.get("FOLDER_ANALYZER_RELOAD", "0") == "1"
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=reload_dev)
