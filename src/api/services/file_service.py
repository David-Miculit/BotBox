from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from sqlalchemy.orm import Session
from db.schema import FileContentRecord, FileRecord
from sqlalchemy import func

class FileService:
    def __init__(self, base_dir: Path | str = "files") -> None:
        self.base_dir = Path(base_dir)

    # return the upload directory for a given user
    def get_upload_dir(self, user_id: int) -> Path:
        return self.base_dir / str(user_id)

    # store an uploaded file on disk under files/{user_id}/ and return metadata
    async def store(self, file: UploadFile, user_id: int) -> dict:
        original_name = Path(file.filename or "").name
        ext = Path(original_name).suffix

        random_name = f"{uuid4().hex}{ext}"

        user_dir = self.get_upload_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        dest = user_dir / random_name

        content = await file.read()
        dest.write_bytes(content)

        return {
            "filename": original_name,
            "stored_filename": random_name,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(content),
            "path": str(dest),
            "raw_bytes": content,
        }

    # store file on disk and create a FileRecord in the database
    async def store_and_record(self,*,file: UploadFile,user_id: int,db: Session,) -> FileRecord:
        stored = await self.store(file=file, user_id=user_id)

        record = FileRecord(
            original_name=stored["filename"],
            random_name=stored["stored_filename"],
            content_type=stored["content_type"],
            size=stored["size"],
            path=stored["path"],
            user_id=user_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
              
        raw_bytes = stored.get("raw_bytes", b"")
        try:
            text_content = raw_bytes.decode("utf-8", errors="ignore").replace("\x00", "")
        except Exception:
            text_content = ""

        if text_content:
            content_record = FileContentRecord(
                file_id=record.id,
                content_tsv=func.to_tsvector("english", text_content),
            )
            db.add(content_record)

        db.commit()
        db.refresh(record)

        return record

# provide a FileService instance
def get_file_service() -> FileService:
    return FileService()
