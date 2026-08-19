from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
)

from sqlalchemy.orm import Session

from datetime import datetime, timedelta
from io import BytesIO

import fitz  # PyMuPDF

from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.file import CompanyFile

from app.schemas.files import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
)

from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_file_url,
    get_file_stream_from_s3,
)


router = APIRouter(
    prefix="/files",
    tags=["Files"]
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# HELPER - GET FILE BY DOCUMENT ID
# ============================================================

def get_report_by_document_id(
    document_id: str,
    db: Session
):
    report = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.document_id == document_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return report


# ============================================================
# UPLOAD PDF
# ============================================================

@router.post("/")
async def upload_report(
    isin: str = Form(...),
    company: str = Form(...),
    mcap: str = Form(...),
    year: int = Form(...),
    document_type: str = Form(...),
    treasure: str = Form(...),
    price: float = Form(299),

    file: UploadFile = File(...),

    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Only PDF
    # --------------------------------------------------------

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # --------------------------------------------------------
    # Read PDF into memory
    # --------------------------------------------------------

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF is empty."
        )

    # --------------------------------------------------------
    # Get total pages from PDF
    # --------------------------------------------------------

    try:
        pdf = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        total_pages = pdf.page_count

        pdf.close()

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file."
        )

    # --------------------------------------------------------
    # Generate unique S3 filename
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    filename = f"{timestamp}_{file.filename}"

    # --------------------------------------------------------
    # Upload directly to S3
    # --------------------------------------------------------

    s3_key = upload_file_to_s3(
        file_obj=BytesIO(file_bytes),
        folder="company-files",
        filename=filename
    )

    if not s3_key:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload PDF to S3."
        )

    # --------------------------------------------------------
    # File size
    # --------------------------------------------------------

    file_size = len(file_bytes)

    # --------------------------------------------------------
    # Save database record
    #
    # filepath stores S3 KEY, NOT local filepath
    # --------------------------------------------------------

    report = CompanyFile(
        isin=isin,
        company=company,
        mcap=mcap,
        year=year,
        document_type=document_type,
        treasure=treasure,
        filename=file.filename,
        filepath=s3_key,
        total_pages=total_pages,
        file_size=file_size,
        price=price,
    )

    db.add(report)

    db.commit()

    db.refresh(report)

    # --------------------------------------------------------
    # Generate document ID
    # --------------------------------------------------------

    report.document_id = f"DOC{report.id:06d}"

    db.commit()

    db.refresh(report)

    return report


# ============================================================
# GET ALL REPORTS
# ============================================================

@router.get(
    "/",
    response_model=list[ReportResponse]
)
def get_reports(
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .order_by(
            CompanyFile.uploaded_at.desc()
        )
        .all()
    )


# ============================================================
# GET TREASURE REPORTS
# ============================================================

@router.get(
    "/treasure",
    response_model=list[ReportResponse]
)
def get_treasure_reports(
    db: Session = Depends(get_db)
):

    reports = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.treasure.ilike("yes")
        )
        .order_by(
            CompanyFile.uploaded_at.desc()
        )
        .all()
    )

    return reports


# ============================================================
# LATEST UPLOADS
# ============================================================

@router.get(
    "/latest-uploads",
    response_model=list[ReportResponse]
)
def get_latest_uploads(
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .order_by(
            CompanyFile.uploaded_at.desc(),
            CompanyFile.id.desc()
        )
        .all()
    )


# ============================================================
# LATEST 24 HOURS
# ============================================================

@router.get(
    "/latest-24-hours",
    response_model=list[ReportResponse]
)
def get_latest_24_hours_reports(
    db: Session = Depends(get_db)
):

    last_24_hours = (
        datetime.now() - timedelta(hours=24)
    )

    reports = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.uploaded_at >= last_24_hours
        )
        .order_by(
            CompanyFile.uploaded_at.desc()
        )
        .all()
    )

    return reports


# ============================================================
# VIEW PDF
# ============================================================

@router.get("/view/{document_id}")
def view_pdf(
    document_id: str,
    db: Session = Depends(get_db)
):

    report = get_report_by_document_id(
        document_id,
        db
    )

    # filepath now contains S3 key
    s3_key = report.filepath

    if not s3_key:
        raise HTTPException(
            status_code=404,
            detail="S3 file not found"
        )

    try:

        file_stream = get_file_stream_from_s3(
            s3_key
        )

    except Exception:
        raise HTTPException(
            status_code=404,
            detail="PDF file missing from S3"
        )

    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{report.filename}"'
            )
        }
    )


# ============================================================
# DOWNLOAD PDF
# ============================================================

@router.get("/download/{document_id}")
def download_pdf(
    document_id: str,
    db: Session = Depends(get_db)
):

    report = get_report_by_document_id(
        document_id,
        db
    )

    s3_key = report.filepath

    if not s3_key:
        raise HTTPException(
            status_code=404,
            detail="S3 file not found"
        )

    try:

        file_stream = get_file_stream_from_s3(
            s3_key
        )

    except Exception:
        raise HTTPException(
            status_code=404,
            detail="PDF file missing from S3"
        )

    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{report.filename}"'
            )
        }
    )


# ============================================================
# PREVIEW PDF
#
# First 2 pages only
# No local file is created
# ============================================================

@router.get("/preview/{document_id}")
def preview_pdf(
    document_id: str,
    db: Session = Depends(get_db)
):

    report = get_report_by_document_id(
        document_id,
        db
    )

    s3_key = report.filepath

    if not s3_key:
        raise HTTPException(
            status_code=404,
            detail="S3 file not found"
        )

    # --------------------------------------------------------
    # Get original PDF from S3
    # --------------------------------------------------------

    try:

        file_stream = get_file_stream_from_s3(
            s3_key
        )

        # Handle file-like S3 response
        if hasattr(file_stream, "read"):
            source_bytes = file_stream.read()
        else:
            source_bytes = file_stream

    except Exception:
        raise HTTPException(
            status_code=404,
            detail="PDF file missing from S3"
        )

    # --------------------------------------------------------
    # Open PDF directly from memory
    # --------------------------------------------------------

    try:

        source_pdf = fitz.open(
            stream=source_bytes,
            filetype="pdf"
        )

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read PDF"
        )

    # --------------------------------------------------------
    # Create preview PDF in memory
    # --------------------------------------------------------

    preview_pdf = fitz.open()

    pages_to_copy = min(
        2,
        source_pdf.page_count
    )

    for page_number in range(
        pages_to_copy
    ):

        preview_pdf.insert_pdf(
            source_pdf,
            from_page=page_number,
            to_page=page_number
        )

    # --------------------------------------------------------
    # Add locked message
    # --------------------------------------------------------

    if source_pdf.page_count > 2:

        page = preview_pdf.new_page()

        page.insert_text(
            (80, 100),
            "Premium Content Locked\n\n"
            "Purchase this document to access all pages.",
            fontsize=18
        )

    source_pdf.close()

    # --------------------------------------------------------
    # Convert preview PDF to bytes
    # --------------------------------------------------------

    preview_bytes = preview_pdf.tobytes()

    preview_pdf.close()

    # --------------------------------------------------------
    # Return directly from memory
    # --------------------------------------------------------

    return StreamingResponse(
        BytesIO(preview_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{document_id}_preview.pdf"'
            )
        }
    )


# ============================================================
# GET REPORT BY ID
# ============================================================

@router.get(
    "/{report_id}",
    response_model=ReportResponse
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):

    report = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.id == report_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    return report


# ============================================================
# UPDATE REPORT
# ============================================================

@router.put(
    "/{report_id}",
    response_model=ReportResponse
)
async def update_report(
    report_id: int,

    isin: str = Form(...),
    company: str = Form(...),
    mcap: str = Form(...),
    year: int = Form(...),
    document_type: str = Form(...),
    treasure: str = Form(...),
    price: float = Form(...),

    file: UploadFile | None = File(None),

    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Find report
    # --------------------------------------------------------

    report = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.id == report_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    # --------------------------------------------------------
    # Update fields
    # --------------------------------------------------------

    report.isin = isin
    report.company = company
    report.mcap = mcap
    report.year = year
    report.document_type = document_type
    report.treasure = treasure
    report.price = price

    # --------------------------------------------------------
    # If new PDF uploaded
    # --------------------------------------------------------

    if file:

        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed."
            )

        # Read new PDF
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF is empty."
            )

        # ----------------------------------------------------
        # Validate PDF
        # ----------------------------------------------------

        try:

            pdf = fitz.open(
                stream=file_bytes,
                filetype="pdf"
            )

            total_pages = pdf.page_count

            pdf.close()

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file."
            )

        # ----------------------------------------------------
        # Delete old S3 file
        # ----------------------------------------------------

        if report.filepath:

            try:
                delete_file_from_s3(
                    report.filepath
                )
            except Exception:
                pass

        # ----------------------------------------------------
        # Generate new S3 filename
        # ----------------------------------------------------

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )

        filename = (
            f"{timestamp}_{file.filename}"
        )

        # ----------------------------------------------------
        # Upload new PDF to S3
        # ----------------------------------------------------

        s3_key = upload_file_to_s3(
            file_obj=BytesIO(file_bytes),
            folder="company-files",
            filename=filename
        )

        if not s3_key:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload PDF to S3."
            )

        # ----------------------------------------------------
        # Update database
        # ----------------------------------------------------

        report.total_pages = total_pages
        report.file_size = len(file_bytes)
        report.filename = file.filename
        report.filepath = s3_key

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    db.commit()

    db.refresh(report)

    return report


# ============================================================
# DELETE REPORT
# ============================================================

@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db)
):

    report = (
        db.query(CompanyFile)
        .filter(
            CompanyFile.id == report_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    # --------------------------------------------------------
    # Delete PDF from S3
    # --------------------------------------------------------

    if report.filepath:

        try:

            delete_file_from_s3(
                report.filepath
            )

        except Exception as e:

            print(
                "S3 delete error:",
                str(e)
            )

    # --------------------------------------------------------
    # Delete DB record
    # --------------------------------------------------------

    db.delete(report)

    db.commit()

    return {
        "message": "Report deleted successfully"
    }


# ============================================================
# GET REPORTS BY ISIN
# ============================================================

@router.get(
    "/isin/{isin}",
    response_model=list[ReportResponse]
)
def get_reports_by_isin(
    isin: str,
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .filter(
            CompanyFile.isin == isin
        )
        .all()
    )


# ============================================================
# GET REPORTS BY COMPANY
# ============================================================

@router.get(
    "/company/{company}",
    response_model=list[ReportResponse]
)
def get_reports_by_company(
    company: str,
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .filter(
            CompanyFile.company.ilike(
                f"%{company}%"
            )
        )
        .all()
    )


# ============================================================
# GET REPORTS BY YEAR
# ============================================================

@router.get(
    "/year/{year}",
    response_model=list[ReportResponse]
)
def get_reports_by_year(
    year: int,
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .filter(
            CompanyFile.year == year
        )
        .all()
    )


# ============================================================
# GET REPORTS BY DOCUMENT TYPE
# ============================================================

@router.get(
    "/document-type/{document_type}",
    response_model=list[ReportResponse]
)
def get_reports_by_document_type(
    document_type: str,
    db: Session = Depends(get_db)
):

    return (
        db.query(CompanyFile)
        .filter(
            CompanyFile.document_type
            == document_type
        )
        .all()
    )

