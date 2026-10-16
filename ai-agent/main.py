"""Entrypoint. `python main.py` for local development; the container
runs uvicorn against `app.main:app` directly."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8100")),
        reload=bool(os.environ.get("RELOAD")),
    )
