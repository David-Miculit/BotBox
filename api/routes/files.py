from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from db.models import UserRecord, FileRecord
from sqlalchemy.orm import Session
from utils.auth import get_current_user
from db.database import get_db
from utils.files import save_file
from fastapi.responses import FileResponse

UPLOAD_DIR = Path("files")

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    
    content = await file.read()
    stored_name, dest = save_file(upload_dir=UPLOAD_DIR, user_id=str(current_user.id), original_file_name=file.filename, content=content)

    try:
        file_record = FileRecord(
            user_id=str(current_user.id),
            original_filename=Path(file.filename).name,
            stored_filename=stored_name,
            content_type=file.content_type or "application/octet-stream",
            size=len(content),
            path=str(dest),
        )

        db.add(file_record)
        db.commit()
        db.refresh(file_record)
    except Exception:
        db.rollback()
        if dest.exists():
            dest.unlink()
        raise

    return {
        "id": file_record.id,
        "filename": file_record.original_filename,
        "stored_filename": file_record.stored_filename,
        "content_type": file_record.content_type,
        "size": file_record.size,
        "path": file_record.path,
        "created_at": file_record.created_at,
    }

@router.get("")
def list_files(current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(FileRecord)
        .filter(FileRecord.user_id == str(current_user.id))
        .order_by(FileRecord.created_at.desc())
        .all()
    )

@router.get("/{file_id}")
def retrieve_file(file_id: int, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    file_record = (
        db.query(FileRecord)
        .filter(FileRecord.id == file_id, FileRecord.user_id == str(current_user.id))
        .first()
    )

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return file_record

@router.get("/content/{file_id}")
def retrieve_content(file_id: int, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    file_record = (
        db.query(FileRecord)
        .filter(
            FileRecord.id == file_id,
            FileRecord.user_id == str(current_user.id),
        )
        .first()
    )

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_path = Path(file_record.path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content not found on disk",
        )

    return FileResponse(path=file_path, media_type=file_record.content_type, filename=file_record.original_filename)