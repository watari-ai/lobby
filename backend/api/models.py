"""Local Live2D model file serving API.

Allows mounting a local directory and serving its files over HTTP,
so the browser can load Live2D models without file:// access.
"""

import mimetypes
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/models", tags=["models"])

# Currently mounted directory (single mount for simplicity)
_mounted_dir: Path | None = None
_model3_filename: str | None = None
_temp_dirs: list[str] = []  # Track temp dirs for cleanup


class MountRequest(BaseModel):
    path: str


class MountResponse(BaseModel):
    modelUrl: str
    model3json: str


class ModelInfo(BaseModel):
    path: str
    model3json: str
    modelUrl: str


@router.post("/mount", response_model=MountResponse)
async def mount_model(req: MountRequest):
    """Mount a local directory for file serving."""
    global _mounted_dir, _model3_filename

    directory = Path(req.path).resolve()
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {req.path}")

    # Find .model3.json file
    model_files = list(directory.glob("*.model3.json"))
    if not model_files:
        raise HTTPException(status_code=400, detail="No .model3.json found in directory")

    _mounted_dir = directory
    _model3_filename = model_files[0].name

    return MountResponse(
        modelUrl=f"/api/models/files/{_model3_filename}",
        model3json=_model3_filename,
    )


@router.post("/upload")
async def upload_model(files: list[UploadFile] = FastAPIFile(...)):
    """Upload model files from browser, save to temp dir, and mount.
    
    Each file's filename should be a relative path (e.g. "textures/foo.png").
    """
    global _mounted_dir, _model3_filename

    # Clean up previous temp dir
    if _temp_dirs:
        for d in _temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        _temp_dirs.clear()

    tmp = tempfile.mkdtemp(prefix="lobby-model-")
    _temp_dirs.append(tmp)
    tmp_path = Path(tmp).resolve()  # resolve /var → /private/var on macOS

    model3_name: str | None = None

    for f in files:
        if not f.filename:
            continue
        dest = (tmp_path / f.filename).resolve()
        # Prevent path traversal
        if not str(dest).startswith(str(tmp_path)):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await f.read()
        dest.write_bytes(content)
        if f.filename.endswith(".model3.json"):
            model3_name = f.filename

    if not model3_name:
        shutil.rmtree(tmp, ignore_errors=True)
        _temp_dirs.remove(tmp)
        raise HTTPException(status_code=400, detail="No .model3.json in uploaded files")

    _mounted_dir = tmp_path
    _model3_filename = model3_name

    return MountResponse(
        modelUrl=f"/api/models/files/{model3_name}",
        model3json=model3_name,
    )


@router.get("/list")
async def list_models():
    """Return currently mounted model info."""
    if _mounted_dir is None or _model3_filename is None:
        return {"models": []}
    return {
        "models": [
            ModelInfo(
                path=str(_mounted_dir),
                model3json=_model3_filename,
                modelUrl=f"/api/models/files/{_model3_filename}",
            ).model_dump()
        ]
    }


# Extra MIME types for Live2D assets
_EXTRA_MIME = {
    ".moc3": "application/octet-stream",
    ".model3.json": "application/json",
    ".physics3.json": "application/json",
    ".pose3.json": "application/json",
    ".userdata3.json": "application/json",
    ".exp3.json": "application/json",
    ".motion3.json": "application/json",
    ".cdi3.json": "application/json",
}


def _guess_mime(filepath: Path) -> str:
    name = filepath.name.lower()
    for suffix, mime in _EXTRA_MIME.items():
        if name.endswith(suffix):
            return mime
    mt, _ = mimetypes.guess_type(str(filepath))
    return mt or "application/octet-stream"


@router.get("/files/{filepath:path}")
async def serve_file(filepath: str):
    """Serve a file from the mounted directory."""
    if _mounted_dir is None:
        raise HTTPException(status_code=404, detail="No model mounted")

    # Resolve and prevent path traversal
    requested = (_mounted_dir / filepath).resolve()
    if not str(requested).startswith(str(_mounted_dir)):
        raise HTTPException(status_code=403, detail="Path traversal denied")

    if not requested.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    return FileResponse(
        path=str(requested),
        media_type=_guess_mime(requested),
    )
