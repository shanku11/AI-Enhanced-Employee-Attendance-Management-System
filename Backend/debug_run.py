import sys
import os

with open("debug_out.txt", "w") as f:
    sys.stdout = f
    sys.stderr = f
    print("Starting debug_run.py...")
    try:
        import uvicorn
        os.chdir(r"D:\Projects\Gradious\Backend")
        uvicorn.run("main:app", host="127.0.0.1", port=5000, log_level="info")
    except Exception as e:
        import traceback
        print("Exception caught:", e)
        traceback.print_exc(file=f)
    print("Finished debug_run.py.")
