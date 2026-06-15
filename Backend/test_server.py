import sys
import traceback
import uvicorn
import os

with open(r"C:\Users\kummu srinivas\debug.log", "w") as f:
    sys.stdout = f
    sys.stderr = f
    print("Starting server test...")
    try:
        # Import main module
        import main
        print("Imported main successfully!")
        
        # Change dir
        os.chdir(r"D:\Projects\Gradious\Backend")
        
        # Run uvicorn
        uvicorn.run("main:app", host="127.0.0.1", port=5000, log_level="info")
    except Exception as e:
        print("Exception:", e)
        traceback.print_exc(file=f)
    print("Server stopped.")
