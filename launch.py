# --- FILE: launch.py ---

import uvicorn
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print(">>> SYSTEM STARTUP INITIATED <<<")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)