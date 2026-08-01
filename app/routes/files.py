from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
import os
from pathlib import Path
import fitz  # PyMuPDF
from datetime import datetime, timedelta
from fastapi.responses import FileResponse
from app.models.file import CompanyFile
from app.schemas.files import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
)

router = APIRouter(
    prefix="/files",
    tags=["Files"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@router.post("/")
async def upload_report(
    isin: str = Form(...),
    company: str = Form(...),
    mcap:str=Form(...),
    year: int = Form(...),
    document_type: str = Form(...),
    treasure:str=Form(...),
    price: float = Form(199),

    file: UploadFile = File(...),

    db: Session = Depends(get_db)
):
    # Only PDF
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Create unique filename
    extension = Path(file.filename).suffix

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{extension}"

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # Save PDF
    with open(filepath, "wb") as buffer:
        buffer.write(await file.read())

    # File size
    file_size = os.path.getsize(filepath)

    # Total pages
    pdf = fitz.open(filepath)
    total_pages = pdf.page_count
    pdf.close()

    report = CompanyFile(
        isin=isin,
        company=company,
        mcap=mcap,
        year=year,
        document_type=document_type,
        treasure=treasure,
        filename=file.filename,          # original filename
        filepath=filepath,               # stored path
        total_pages=total_pages,
        file_size=file_size,
        price=price,
    )

    db.add(report)
    db.commit()
    db.refresh(report)
    report.document_id = f"DOC{report.id:06d}"
    db.commit()
    db.refresh(report)

    return report

@router.get("/", response_model=list[ReportResponse])
def get_reports(db: Session = Depends(get_db)):
    return (
        db.query(CompanyFile)
        .order_by(CompanyFile.uploaded_at.desc())
        .all()
    )

@router.get("/treasure", response_model=list[ReportResponse])
def get_treasure_reports(
    db: Session = Depends(get_db)
):
    reports = (
        db.query(CompanyFile)
        .filter(CompanyFile.treasure.ilike("yes"))
        .order_by(CompanyFile.uploaded_at.desc())
        .all()
    )

    return reports
@router.get("/latest-uploads", response_model=list[ReportResponse])
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
    
@router.get("/latest-24-hours", response_model=list[ReportResponse])
def get_latest_24_hours_reports(
    db: Session = Depends(get_db)
):
    last_24_hours = datetime.now() - timedelta(hours=24)

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
@router.get("/view/{document_id}")
def view_pdf(
    document_id: str,
    db: Session = Depends(get_db)
):

    report = (
        db.query(CompanyFile)
        .filter(CompanyFile.document_id == document_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    if not os.path.exists(report.filepath):
        raise HTTPException(
            status_code=404,
            detail="PDF file missing"
        )

    return FileResponse(
        path=report.filepath,
        media_type="application/pdf",
        filename=report.filename
    )
@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = (
        db.query(CompanyFile)
        .filter(CompanyFile.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(404, "Report not found")

    return report

@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,

    isin: str = Form(...),
    company: str = Form(...),
    mcap:str=Form(...),
    year: int = Form(...),
    document_type: str = Form(...),
    treasure:str=Form(...) ,
    price: float = Form(...),

    file: UploadFile | None = File(None),

    db: Session = Depends(get_db)
):

    report = db.query(CompanyFile).filter(
        CompanyFile.id == report_id
    ).first()

    if not report:
        raise HTTPException(404, "Report not found")

    report.isin = isin
    report.company = company
    report.mcap=mcap
    report.year = year
    report.document_type = document_type
    report.treasure=treasure,
    report.price = price

    if file:

        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed."
            )

        extension = Path(file.filename).suffix

        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{extension}"

        filepath = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        with open(filepath, "wb") as buffer:
            buffer.write(await file.read())

        pdf = fitz.open(filepath)

        report.total_pages = pdf.page_count

        pdf.close()

        report.file_size = os.path.getsize(filepath)
        report.filename = file.filename
        report.filepath = filepath

    db.commit()
    db.refresh(report)

    return report
@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    report = (
        db.query(CompanyFile)
        .filter(CompanyFile.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(404, "Report not found")

    db.delete(report)
    db.commit()

    return {
        "message": "Report deleted successfully"
    }
    
@router.get("/isin/{isin}", response_model=list[ReportResponse])
def get_reports_by_isin(
    isin: str,
    db: Session = Depends(get_db)
):
    return (
        db.query(CompanyFile)
        .filter(CompanyFile.isin == isin)
        .all()
    )
@router.get("/company/{company}", response_model=list[ReportResponse])
def get_reports_by_company(
    company: str,
    db: Session = Depends(get_db)
):
    return (
        db.query(CompanyFile)
        .filter(CompanyFile.company.ilike(f"%{company}%"))
        .all()
    )
@router.get("/year/{year}", response_model=list[ReportResponse])
def get_reports_by_year(
    year: int,
    db: Session = Depends(get_db)
):
    return (
        db.query(CompanyFile)
        .filter(CompanyFile.year == year)
        .all()
    )


@router.get("/document-type/{document_type}", response_model=list[ReportResponse])
def get_reports_by_document_type(
    document_type: str,
    db: Session = Depends(get_db)
):
    return (
        db.query(CompanyFile)
        .filter(CompanyFile.document_type == document_type)
        .all()
    )