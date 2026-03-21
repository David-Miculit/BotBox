from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.schema import FileRecord, FileContentRecord, FileContentChunkRecord
from config.settings import settings
import voyageai
import re

client = voyageai.Client(api_key=settings.voyage_api_key)

# provide a base_dir to be used for file storage
def get_file_base_dir() -> Path:
    return Path("files")

# return the upload directory for a given user
def get_upload_dir(base_dir: Path | str, user_id: int) -> Path:
    return Path(base_dir) / str(user_id)

# store an uploaded file on disk under files/{user_id}/ and return metadata
async def store(*, file: UploadFile, user_id: int, base_dir: Path | str = "files") -> dict:
    original_name = Path(file.filename or "").name
    ext = Path(original_name).suffix

    random_name = f"{uuid4().hex}{ext}"

    user_dir = get_upload_dir(base_dir, user_id)
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
async def store_and_record(*, file: UploadFile, user_id: int, db: Session, base_dir: Path | str = "files") -> FileRecord:
    stored = await store(file=file, user_id=user_id, base_dir=base_dir)

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

        chunks = chunk_by_sentence(text_content)
        embeddings = embed(chunks)
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings), start=1):
            chunk_record = FileContentChunkRecord(
                file_id=record.id,
                chunk_id=idx,
                chunk=chunk_text,
                embedding=embedding,
            )
            db.add(chunk_record)

    db.commit()
    db.refresh(record)

    return record

# split text into chunks by number of sentences
def chunk_by_sentence(text, max_sentences_per_chunk=3, overlap_sentences=1):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    start_idx = 0

    while start_idx < len(sentences):
        end_idx = min(start_idx + max_sentences_per_chunk, len(sentences))
        chunks.append(" ".join(sentences[start_idx:end_idx]))
        start_idx += max_sentences_per_chunk - overlap_sentences
        if start_idx < 0:
            start_idx = 0

    return chunks

# def chunk_by_section_markdown(document_text):
#     return [s.strip() for s in re.split(r"\n## ", document_text) if s.strip()]

# return an embedding vector per text
def embed(texts: list[str], model: str = "voyage-3") -> list[list[float]]:
    result = client.embed(texts, model=model, output_dimension=1024)
    return result.embeddings

SIMILARITY_THRESHOLD = 0.20
def semantic_retrieve(db: Session, user_id: int, query: str, limit: int = 10) -> list[dict]:
    query_embedding = embed([query])[0]
    distance = FileContentChunkRecord.embedding.cosine_distance(query_embedding)

    results = (
        db.query(
            FileContentChunkRecord.file_id,
            FileContentChunkRecord.chunk_id,
            FileContentChunkRecord.chunk,
            FileRecord.original_name,
            distance.label("distance"),
        )
        .join(FileRecord, FileRecord.id == FileContentChunkRecord.file_id)
        .filter(FileRecord.user_id == user_id)
        .order_by(distance, FileContentChunkRecord.file_id, FileContentChunkRecord.chunk_id)
        .limit(limit * 2)
        .all()
    )

    filtered = [
        {
            "file_id": r.file_id,
            "chunk_id": r.chunk_id,
            "filename": r.original_name,
            "chunk": r.chunk,
            "similarity": float(1 - r.distance),
        }
        for r in results
        if (1 - r.distance) > SIMILARITY_THRESHOLD
    ]

    return filtered[:limit]