"""AI-assisted parsing of supplier order-confirmation emails.

The frontend's Order Email Scan sends the full email (headers, body text, and
selected attachments) here; we ask Claude Haiku 4.5 to extract the order
header and line items as structured JSON. The Anthropic API key lives only on
the server (ANTHROPIC_API_KEY) — never in the browser.
"""
import json

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_current_user

router = APIRouter(prefix="/order-email-parse", tags=["order-email-parse"], dependencies=[Depends(get_current_user)])

settings = get_settings()

MODEL = "claude-haiku-4-5"

# Attachment types we can pass to the model. Anything else is ignored.
PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
TEXT_TYPES = {"text/plain", "text/csv", "text/html"}
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024  # base64 length check, roughly 3MB binary

ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor_name": {
            "type": ["string", "null"],
            "description": "The supplier/store the order was placed with, e.g. 'Fire Mountain Gems'. Null if unclear.",
        },
        "order_number": {
            "type": ["string", "null"],
            "description": "The order/confirmation/invoice number, if present.",
        },
        "order_date": {
            "type": ["string", "null"],
            "description": "The order date in YYYY-MM-DD format. Null if not determinable.",
        },
        "lines": {
            "type": "array",
            "description": "One entry per purchased item. Exclude subtotal/shipping/tax/discount/total rows.",
            "items": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "The item name/description as listed, including size/color details.",
                    },
                    "quantity": {"type": ["number", "null"], "description": "Quantity ordered. Null if not stated."},
                    "unit": {
                        "type": ["string", "null"],
                        "description": "Unit if stated or clearly implied: strand, piece, pair, set, bag, tube, container, gram, ounce, count. Null otherwise.",
                    },
                    "unit_cost": {
                        "type": ["number", "null"],
                        "description": "Price per unit in dollars (not the line total, if both are shown). Null if not stated.",
                    },
                },
                "required": ["description", "quantity", "unit", "unit_cost"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["vendor_name", "order_number", "order_date", "lines"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You extract purchase-order data from supplier order-confirmation emails for a small "
    "bead and jewelry-supply store. Read the email (and any attached invoice/receipt "
    "documents) and extract the vendor, order number, order date, and every purchased "
    "line item. Prefer the most specific item descriptions available. Quantities and "
    "prices must come from the email content — never invent values; use null when a "
    "field is not present. Exclude shipping, tax, discounts, subtotals, and totals from "
    "the line items."
)


class ParseAttachment(BaseModel):
    filename: str = ""
    mime_type: str = ""
    data_base64: str = Field(default="", max_length=MAX_ATTACHMENT_BYTES * 2)


class ParseRequest(BaseModel):
    subject: str = ""
    from_header: str = ""
    date_header: str = ""
    body_text: str = Field(default="", max_length=200_000)
    attachments: list[ParseAttachment] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)


class ParsedLine(BaseModel):
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_cost: float | None = None


class ParseResponse(BaseModel):
    vendor_name: str | None = None
    order_number: str | None = None
    order_date: str | None = None
    lines: list[ParsedLine] = Field(default_factory=list)


def _attachment_block(att: ParseAttachment) -> dict | None:
    if not att.data_base64:
        return None
    if att.mime_type in PDF_TYPES:
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": att.data_base64},
        }
    if att.mime_type in IMAGE_TYPES:
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": att.mime_type, "data": att.data_base64},
        }
    return None


@router.post("", response_model=ParseResponse)
def parse_order_email(payload: ParseRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI parsing is not configured. Set ANTHROPIC_API_KEY on the server to enable it.",
        )

    content: list[dict] = []
    for att in payload.attachments:
        block = _attachment_block(att)
        if block is not None:
            content.append(block)

    email_text = (
        f"From: {payload.from_header}\n"
        f"Date: {payload.date_header}\n"
        f"Subject: {payload.subject}\n\n"
        f"{payload.body_text}"
    )
    content.append({"type": "text", "text": f"Extract the order from this email:\n\n{email_text}"})

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": ORDER_SCHEMA}},
        )
    except anthropic.APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI parsing failed ({exc.status_code}). Try again, or record the order manually.",
        )
    except anthropic.APIConnectionError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the AI parsing service. Try again later.",
        )

    if response.stop_reason == "refusal":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI declined to parse this email. Record the order manually.",
        )

    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI returned an unreadable result. Try again, or record the order manually.",
        )

    return ParseResponse(**data)
