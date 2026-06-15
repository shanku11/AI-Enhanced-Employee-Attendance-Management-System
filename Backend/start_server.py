import uvicorn
import sys
import traceback
import os

if __name__ == "__main__":
    os.chdir(r"D:\Projects\Gradious\Backend")
    try:
        uvicorn.run("main:app", host="127.0.0.1", port=5000, log_level="info")
    except Exception as e:
        print("Error:", e)
        traceback.print_exc()
        sys.exit(1)
