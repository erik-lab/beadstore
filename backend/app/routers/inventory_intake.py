"""Staged inventory intake from spreadsheets, documents, notes and dictation.

One parse endpoint per input shape (text or file), then a shared review and
commit surface. Dictation is deliberately not its own code path: the browser
transcribes speech locally and posts the transcript to the text endpoint with
source_kind='voice', so a spoken entry is parsed by exactly the same pass as a
pasted note.
"""
import base64
import binascii
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.enums import IntakeSourceKind
from app.schemas.inventory_intake import (
    IntakeBatchDetail,
    IntakeBatchRead,
    IntakeBulkUpdate,
    IntakeCommitResult,
    IntakeParseFileRequest,
    IntakeParseTextRequest,
    IntakeRowRead,
    IntakeRowSkip,
    IntakeRowUpdate,
    NamesToCreate,
)
from app.services import intake_extract, intake_parse, intake_service

router = APIRouter(
    prefix="/inventory-intake",
    tags=["inventory-intake"],
    dependencies=[Depends(get_current_user)],
)


def _batch_detail(db: Session, batch) -> IntakeBatchDetail:
    detail = IntakeBatchDetail.model_validate(batch)
    detail.will_create = NamesToCreate(**intake_service.names_to_be_created(db, batch))
    return detail


@router.post("/parse-text", response_model=IntakeBatchDetail, status_code=status.HTTP_201_CREATED)
def parse_text(payload: IntakeParseTextRequest, db: Session = Depends(get_db)):
    """Parse typed, pasted or dictated text into a reviewable draft batch."""
    hint = (
        "This source is a spoken note dictated by the shop owner, so it may be conversational, "
        "unpunctuated, or contain speech-recognition errors in product names and numbers. "
        "Interpret it as generously as the wording allows, but still use null for anything "
        "genuinely not said."
        if payload.source_kind == IntakeSourceKind.voice
        else ""
    )
    parsed = intake_parse.parse_text(db, payload.text, context_hint=hint)
    default_name = "Dictated note" if payload.source_kind == IntakeSourceKind.voice else "Pasted text"
    batch = intake_service.create_batch_from_parse(
        db,
        parsed,
        source_kind=payload.source_kind,
        source_name=payload.source_name or default_name,
        raw_text=payload.text,
    )
    return _batch_detail(db, batch)


@router.post("/parse-file", response_model=IntakeBatchDetail, status_code=status.HTTP_201_CREATED)
def parse_file(payload: IntakeParseFileRequest, db: Session = Depends(get_db)):
    """Parse an uploaded spreadsheet, document, PDF or photo into a draft batch."""
    try:
        data = base64.b64decode(payload.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file didn't upload correctly. Try again.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That file is empty.")

    mime_type = intake_extract.guess_mime_type(payload.filename, payload.mime_type)
    source_name = payload.filename or "Uploaded file"

    if mime_type in intake_extract.PDF_TYPES or mime_type in intake_extract.IMAGE_TYPES:
        # Handed to the model as-is: scanned invoices and phone photos read far
        # better natively than through any text extraction we'd do here.
        parsed = intake_parse.parse_document(db, payload.data_base64, mime_type)
        raw_text = None
        source_kind = IntakeSourceKind.document
    else:
        raw_text = intake_extract.extract_text(data, payload.filename, payload.mime_type)
        parsed = intake_parse.parse_text(db, raw_text)
        source_kind = (
            IntakeSourceKind.spreadsheet
            if mime_type in intake_extract.SPREADSHEET_TYPES
            or mime_type in {"text/csv", "text/tab-separated-values"}
            else IntakeSourceKind.document
        )

    batch = intake_service.create_batch_from_parse(
        db, parsed, source_kind=source_kind, source_name=source_name, raw_text=raw_text
    )
    return _batch_detail(db, batch)


@router.get("/batches", response_model=list[IntakeBatchRead])
def list_batches(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    return intake_service.list_batches(db, limit=limit, offset=offset)


@router.get("/batches/{batch_id}", response_model=IntakeBatchDetail)
def get_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    return _batch_detail(db, intake_service.get_batch_or_404(db, batch_id))


@router.patch("/batches/{batch_id}/rows", response_model=IntakeBatchDetail)
def bulk_update_rows(batch_id: uuid.UUID, payload: IntakeBulkUpdate, db: Session = Depends(get_db)):
    """Apply shared values (received date, vendor, location...) to every open row."""
    changes = payload.model_dump(exclude_unset=True)
    batch = intake_service.bulk_update_rows(db, batch_id, changes)
    return _batch_detail(db, batch)


@router.post("/batches/{batch_id}/commit", response_model=IntakeCommitResult)
def commit_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    """Save every ready row as a product and inventory unit."""
    return intake_service.commit_batch(db, batch_id)


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    intake_service.delete_batch(db, batch_id)


@router.patch("/rows/{row_id}", response_model=IntakeRowRead)
def update_row(row_id: uuid.UUID, payload: IntakeRowUpdate, db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_unset=True)
    # The API speaks in an attributes object; the row stores it as JSON text.
    if "attributes" in changes:
        attributes = changes.pop("attributes")
        changes["attributes_json"] = json.dumps(attributes) if attributes else None
    return intake_service.update_row(db, row_id, changes)


@router.post("/rows/{row_id}/skip", response_model=IntakeRowRead)
def skip_row(row_id: uuid.UUID, payload: IntakeRowSkip, db: Session = Depends(get_db)):
    """Exclude a row from the commit (or put it back)."""
    return intake_service.set_row_skipped(db, row_id, payload.skipped)
