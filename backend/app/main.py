import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.store import DatasetNotFound
from .routers import causal, datasets, experiments, power

logger = logging.getLogger("platform")

app = FastAPI(
    title="Experimentation & Causal Inference Platform",
    description="Design A/B tests, analyze them correctly, and estimate causal effects from observational data.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

for r in (power.router, datasets.router, experiments.router, causal.router):
    app.include_router(r)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DatasetNotFound)
async def not_found_handler(_: Request, exc: DatasetNotFound):
    return JSONResponse(status_code=404, content={"detail": "Dataset not found. Upload or load it again."})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": f"Analysis failed: {exc}"})


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok"}


STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = STATIC_DIR / path
        return FileResponse(file if path and file.is_file() else STATIC_DIR / "index.html")
