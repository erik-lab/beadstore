"""Reduce an uploaded inventory source file to plain text.

Everything Patti might paste or upload has to become text before the AI pass,
so there's exactly one parser to maintain instead of one per format. The two
exceptions are PDFs and photos, which go to the model as native document/image
blocks (see intake_parse) because that reads them far better than any text
extraction we could do here.

Spreadsheets are rendered as tab-separated rows with their sheet names, which
keeps column/row structure legible to the model without pretending we know
which column means what — a hand-kept bead spreadsheet rarely has the headers
you'd hope for.
"""
import csv
import io
import re
import zipfile

from fastapi import HTTPException, status

# Extracted text handed to the model is capped so a 20MB spreadsheet can't
# turn into a single enormous (and expensive) request. Patti gets a clear
# message telling her to split the file rather than a silent truncation.
MAX_EXTRACTED_CHARS = 120_000
MAX_SPREADSHEET_ROWS = 2_000
# Guards against a zip bomb in a .docx/.xlsx: these are small formats in
# practice, and refusing is better than inflating gigabytes in memory.
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024

SPREADSHEET_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
WORD_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
TEXT_TYPES = {
    "text/plain",
    "text/csv",
    "text/tab-separated-values",
    "text/markdown",
    "application/json",
    "text/html",
}
PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Microsoft's WordprocessingML namespace, for pulling run text out of a .docx.
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _too_big(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=detail)


def _unsupported(filename: str, mime_type: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Can't read '{filename or 'this file'}' ({mime_type or 'unknown type'}). "
            "Supported: spreadsheets (.xlsx/.csv), Word documents (.docx), PDFs, photos, "
            "and plain text. For anything else, copy the details in and paste them as text."
        ),
    )


def _check_archive_size(data: bytes, filename: str) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{filename or 'This file'}' is damaged or isn't really an Office file.",
        )
    if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise _too_big(f"'{filename or 'This file'}' expands to too much data to read safely.")
    return archive


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 can't fail, but be explicit rather than relying on that.
    return data.decode("utf-8", errors="replace")


def extract_csv(data: bytes) -> str:
    """Normalize a CSV/TSV into tab-separated lines, dropping empty rows."""
    text = _decode_text(data)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    lines: list[str] = []
    for row in csv.reader(io.StringIO(text), dialect):
        cells = [cell.strip() for cell in row]
        if any(cells):
            lines.append("\t".join(cells))
        if len(lines) >= MAX_SPREADSHEET_ROWS:
            lines.append(f"[... stopped after {MAX_SPREADSHEET_ROWS} rows ...]")
            break
    return "\n".join(lines)


def extract_xlsx(data: bytes, filename: str = "") -> str:
    """Render every sheet of a workbook as tab-separated text.

    openpyxl is imported here rather than at module scope so the app still
    boots (and every other intake format still works) if the dependency is
    missing from an older virtualenv.
    """
    _check_archive_size(data, filename)
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Reading .xlsx files needs the openpyxl package on the server "
                "(pip install -r requirements.txt). Save the sheet as .csv and "
                "upload that instead, or paste the rows as text."
            ),
        )

    # read_only keeps memory flat on big sheets; data_only gives us the cached
    # results of formulas instead of "=B2*C2".
    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    chunks: list[str] = []
    rows_emitted = 0
    try:
        for sheet in workbook.worksheets:
            lines: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                if rows_emitted >= MAX_SPREADSHEET_ROWS:
                    lines.append(f"[... stopped after {MAX_SPREADSHEET_ROWS} rows ...]")
                    break
                cells = ["" if value is None else str(value).strip() for value in row]
                if any(cells):
                    lines.append("\t".join(cells))
                    rows_emitted += 1
            if lines:
                chunks.append(f"--- Sheet: {sheet.title} ---\n" + "\n".join(lines))
            if rows_emitted >= MAX_SPREADSHEET_ROWS:
                break
    finally:
        workbook.close()
    return "\n\n".join(chunks)


def extract_docx(data: bytes, filename: str = "") -> str:
    """Pull paragraph and table text out of a .docx.

    Done with the standard library (a .docx is a zip of XML) to avoid another
    dependency: we only need the visible text, not styling or structure.
    """
    import xml.etree.ElementTree as ET

    archive = _check_archive_size(data, filename)
    try:
        document_xml = archive.read("word/document.xml")
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{filename or 'This file'}' doesn't look like a Word document.",
        )

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the text of '{filename or 'this document'}'.",
        )

    lines: list[str] = []
    body = root.find(f"{W_NS}body")
    for block in body if body is not None else []:
        if block.tag == f"{W_NS}p":
            text = "".join(node.text or "" for node in block.iter(f"{W_NS}t")).strip()
            if text:
                lines.append(text)
        elif block.tag == f"{W_NS}tbl":
            # Flatten each table row to tab-separated cells so a table of
            # inventory reads like a spreadsheet to the parser.
            for row in block.iter(f"{W_NS}tr"):
                cells = [
                    "".join(node.text or "" for node in cell.iter(f"{W_NS}t")).strip()
                    for cell in row.findall(f"{W_NS}tc")
                ]
                if any(cells):
                    lines.append("\t".join(cells))
    return "\n".join(lines)


def extract_html(data: bytes) -> str:
    """Strip tags from an HTML source (a saved email, usually)."""
    text = _decode_text(data)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</div>", "\n", text)
    text = re.sub(r"(?i)</t[dh]>", "\t", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def guess_mime_type(filename: str, declared: str) -> str:
    """Trust the extension over the browser's declared type.

    Browsers report .csv as everything from text/csv to application/vnd.ms-excel
    depending on what's installed locally, which would otherwise send a plain
    CSV down the openpyxl path and fail.
    """
    lowered = (filename or "").lower()
    by_extension = {
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".htm": "text/html",
        ".html": "text/html",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    for extension, mime_type in by_extension.items():
        if lowered.endswith(extension):
            return mime_type
    return declared or ""


def extract_text(data: bytes, filename: str = "", mime_type: str = "") -> str:
    """Turn a supported non-PDF/non-image source file into text for parsing."""
    resolved = guess_mime_type(filename, mime_type)
    if resolved in SPREADSHEET_TYPES:
        text = extract_xlsx(data, filename)
    elif resolved in WORD_TYPES:
        text = extract_docx(data, filename)
    elif resolved == "text/html":
        text = extract_html(data)
    elif resolved in {"text/csv", "text/tab-separated-values"}:
        text = extract_csv(data)
    elif resolved in TEXT_TYPES:
        text = _decode_text(data)
    else:
        raise _unsupported(filename, resolved)

    if len(text) > MAX_EXTRACTED_CHARS:
        raise _too_big(
            f"'{filename or 'This file'}' holds about {len(text):,} characters of text, over the "
            f"{MAX_EXTRACTED_CHARS:,} limit for one import. Split it into smaller files and import them separately."
        )
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Found no readable text in '{filename or 'that file'}'.",
        )
    return text
