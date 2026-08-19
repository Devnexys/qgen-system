from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import the core FastAPI app from backend
from backend.app import app as core_app

# Create a new FastAPI instance for Vercel
app = FastAPI()

# Copy middleware and routes from core_app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend) – Vercel serves static files from the repo root
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Include all routes from the original app (except the root static serving which we already handled)
for route in core_app.routes:
    if route.path != "/":
        app.router.routes.append(route)

# Root endpoint – serve the UI index.html
@app.get("/", response_class=fastapi.responses.HTMLResponse)
async def serve_root():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return fastapi.responses.HTMLResponse(content=index_path.read_text())
    return fastapi.responses.HTMLResponse("<h1>Frontend not found</h1>")
