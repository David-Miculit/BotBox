from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from db.models import UserRecord
from utils.auth import get_current_user

UPLOAD_DIR = Path("files")

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), current_user: UserRecord = Depends(get_current_user),):
    """Upload a file. Stored under files/{user_id}/. Returns metadata."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    
    safe_name = Path(file.filename).name
    user_dir = UPLOAD_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / safe_name

    #TODO:
    """
    - extract code in a function
    - generate random file name
    - store a DB record for the file
    - create remaining roots (list files, retreife file retreive file content)
    """
    
    content = await file.read()
    dest.write_bytes(content)

    return {
        "filename": safe_name,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "path": str(dest),
    }