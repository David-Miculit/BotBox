from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from db.schema import UserRecord, FileRecord, FileContentRecord, FileContentChunkRecord
from api.models import SearchRequest
from db.database import get_db
from sqlalchemy.orm import Session
from utils.auth import get_current_user
from api.services.file_service import get_file_base_dir, store_and_record
from sqlalchemy import func, text
from api.services.file_service import embed

router = APIRouter(prefix="/files", tags=["files"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
    base_dir: Path = Depends(get_file_base_dir)
):    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    
    record = await store_and_record(file=file, user_id=current_user.id, db=db, base_dir=base_dir)

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

@router.get("/search")
def search_content(q: str, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    if not q or q.strip() == "":
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")    

    ts_query = func.to_tsquery('english', q)

    file_record = (
        db.query(FileRecord)
        .join(FileContentRecord, FileContentRecord.file_id == FileRecord.id)
        .filter(FileRecord.user_id == str(current_user.id))
        .filter(FileContentRecord.content_tsv.op('@@')(ts_query))
        .order_by(func.ts_rank(FileContentRecord.content_tsv, ts_query).desc())
        .limit(10).all()
    )

    return file_record

@router.get("/semantic_search")
def semantic_search(q: str, db: Session = Depends(get_db), current_user: UserRecord = Depends(get_current_user)):
    if not q or q.strip() == "":
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    query_embedding = embed([q])[0]
    cosine_distance = FileContentChunkRecord.embedding.cosine_distance(query_embedding)
    similarity = (1 - cosine_distance).label("similarity")

    results = (
        db.query(FileContentChunkRecord.file_id,FileContentChunkRecord.chunk_id,FileContentChunkRecord.chunk,similarity)
        .join(FileRecord, FileRecord.id == FileContentChunkRecord.file_id)
        .filter(FileRecord.user_id == current_user.id)
        .filter(similarity > 0.25)
        .order_by(cosine_distance.asc())
        .limit(10)
        .all()
    )

    return {
        "query": q,
        "results": [
            {
                "file_id": r.file_id,
                "chunk_id": r.chunk_id,
                "chunk": r.chunk,
                "similarity": float(r.similarity),
            }
            for r in results
        ],
    }

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

@router.get("/{file_id}/content")
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
