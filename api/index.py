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

# No manual static mount – static assets will be served by Vercel via rewrites (see vercel.json)

# Include all routes from the original app (except the root static serving which we already handled)
for route in core_app.routes:
    if route.path != "/":
        app.router.routes.append(route)

# Root endpoint not needed – static UI is served by Vercel
