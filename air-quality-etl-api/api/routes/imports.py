from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.schemas import ImportFileResponse

router = APIRouter(prefix="/api/v1/imports", tags=["导入审计"])


@router.get("", response_model=list[ImportFileResponse], summary="查询文件导入审计记录")
def list_imports(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                id_import_file, filename, source_month, status,
                total_rows, accepted_rows, rejected_rows,
                started_at, completed_at, error_message
            FROM air_quality.import_file
            WHERE (:status IS NULL OR status = :status)
            ORDER BY source_month DESC, id_import_file DESC
            LIMIT :limit
            """
        ),
        {"status": status, "limit": limit},
    ).mappings()
    return [ImportFileResponse(**row) for row in rows]
