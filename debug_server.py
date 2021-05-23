import uvicorn

from app.main import app

if __name__ == "__main__":
    print(f"DEBUG: Starting App: '{app.title}'")
    uvicorn.run("debug_server:app", host="127.0.0.1", port=8000, reload=True)
