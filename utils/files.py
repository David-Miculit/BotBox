from pathlib import Path
from uuid import uuid4

def save_file(upload_dir: Path, user_id: str, original_file_name: str, content: bytes) -> tuple[str, Path]:
    safe_name = Path(original_file_name).name
    suffix = Path(safe_name).suffix
    stored_name = f"{uuid4().hex}{suffix}"

    user_dir = upload_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    dest = user_dir / stored_name
    dest.write_bytes(content)

    return stored_name, dest