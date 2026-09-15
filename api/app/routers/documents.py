"""Asynchronous document API: validate, persist pending state, then enqueue."""

from fastapi import APIRouter, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db import get_conn
from app.core.errors import InvalidDocument
from app.core.queue import enqueue_document

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_EXT = (".txt", ".md", ".pdf")


def _create_pending_document(filename: str) -> int:
    with get_conn() as conn:
        return conn.execute(
            "INSERT INTO documents (filename, status) "
            "VALUES (%s, 'pending') RETURNING id",
            (filename,),
        ).fetchone()[0]


def _delete_pending_document(document_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM documents WHERE id = %s AND status = 'pending'",
            (document_id,),
        )


@router.post("", status_code=202)
async def upload_document(file: UploadFile):
    try:
        if not file.filename or not file.filename.lower().endswith(ALLOWED_EXT):
            raise HTTPException(400, "Chỉ chấp nhận: .txt, .md, .pdf")
        if len(file.filename) > 255 or "\x00" in file.filename:
            raise HTTPException(422, "Tên file không hợp lệ.")
        content = await file.read(get_settings().max_upload_bytes + 1)
    finally:
        await file.close()
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "File vượt quá giới hạn upload.")
    if not content:
        raise InvalidDocument()
    document_id = await run_in_threadpool(_create_pending_document, file.filename)
    try:
        job_id = await enqueue_document(document_id, file.filename, content)
    except Exception:
        # Do not leave a row pending forever when Redis rejects the enqueue.
        await run_in_threadpool(_delete_pending_document, document_id)
        raise
    settings = get_settings()
    return {
        "id": document_id,
        "filename": file.filename,
        "status": "pending",
        "chunk_count": 0,
        "job_id": job_id,
        "mode": settings.rag_mode,
        "embedding_identity_id": settings.embedding_identity_id,
    }


@router.get("")
def list_documents():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, status, chunk_count, created_at, "
            "embedding_identity_id, error_code FROM documents ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r[0],
            "filename": r[1],
            "status": r[2],
            "chunk_count": r[3],
            "created_at": r[4].isoformat(),
            "embedding_identity_id": r[5],
            "error_code": r[6],
        }
        for r in rows
    ]


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int):
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM documents WHERE id = %s RETURNING id",
            (document_id,),
        ).fetchone()
    if result is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
