from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from db.schema import UserRecord, FileRecord, FileContentRecord
from api.models import SearchRequest
from db.database import get_db
from sqlalchemy.orm import Session
from utils.auth import get_current_user
from api.services.file_service import FileService, get_file_service
from sqlalchemy import func

UPLOAD_DIR = Path("files")

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserRecord = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service),
    db: Session = Depends(get_db),
):    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    
    record = await file_service.store_and_record(file=file, user_id=current_user.id, db=db)

    return {
        "id": record.id,
        "original_name": record.original_name,
        "random_name": record.random_name,
        "content_type": record.content_type,
        "size": record.size,
        "user_id": record.user_id,
        "path": record.path,
        "created_at": record.created_at,
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

    return FileResponse(path=file_path, media_type=file_record.content_type, filename=file_record.original_name)

@router.post("/search")
def search_content(payload: SearchRequest, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    ts_query = func.to_tsquery('english', payload.body)

    file_record = (
        db.query(FileRecord)
        .join(FileContentRecord, FileContentRecord.file_id == FileRecord.id)
        .filter(FileRecord.user_id == str(current_user.id))
        .filter(FileContentRecord.content_tsv.op('@@')(ts_query))
        .order_by(func.ts_rank(FileContentRecord.content_tsv, ts_query).desc())
        .limit(10).all()
    )

    return file_record