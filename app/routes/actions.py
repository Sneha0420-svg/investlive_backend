from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException,Form
from sqlalchemy.orm import Session
from datetime import date, datetime
import csv
import io
import re
from app.database import SessionLocal
from app.models.action import CorporateActionData, CorporateActionUpload, ResultData, ResultUpload,    ManualEntryUpload
from sqlalchemy import func, text

from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3
)
from sqlalchemy import or_

from fastapi.responses import StreamingResponse
from io import BytesIO


router = APIRouter(
    prefix="/corporate-action",
    tags=["Corporate Action"]
)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
        
        
def normalize_purpose(purpose):
    purpose = (purpose or "").strip().lower()

    if "bonus" in purpose:
        return "bonus"

    if "split" in purpose:
        return "stock split"

    if "dividend" in purpose:
        return "dividend"

    if "buy back" in purpose or "buyback" in purpose:
        return "share buyback"

    return purpose
# -----------------------------
# DATE PARSER
# -----------------------------
def parse_date(date_value):

    if not date_value or str(date_value).strip() in ["", "-"]:
        return None

    formats = [
        "%d-%b-%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_value).strip(), fmt).date()
        except:
            pass

    return None


# -----------------------------
# COMPANY NORMALIZE
# -----------------------------
def normalize_company(name: str):

    if not name:
        return None

    name = name.strip().lower()

    name = re.sub(r'\b(ltd\.?|limited)\b', '', name)

    name = re.sub(r'\s+', ' ', name).strip()

    return name


# -----------------------------
# GOVERNMENT SKIP RULE
# -----------------------------
def is_skipped_company(company: str):

    if not company:
        return False

    company = company.strip().lower().replace(".", "")

    return company in [
        "government of india",
        "govt of india",
        "goi"
    ]


# -----------------------------
# FLOAT SAFE
# -----------------------------
def normalize_float(value):

    if not value or str(value).strip() in ["", "-", "None"]:
        return None

    try:
        return float(value)
    except:
        return None


# -----------------------------
# PURPOSE SPLITTER
# -----------------------------
# -----------------------------
# PURPOSE SPLITTER
# -----------------------------
def split_purpose_and_value(text):

    if not text:
        return None, None, None

    text = str(text)
    text = re.sub(r"\s+", " ", text).strip()

    # Rights 1:9 @ Premium 91
    rights_ratio = re.search(
        r'Rights?\s+(\d+\s*:\s*\d+)\s*@\s*Premium\s+([\d.]+)',
        text,
        re.IGNORECASE
    )

    if rights_ratio:
        return (
            "Rights",
            rights_ratio.group(1).replace(" ", ""),
            rights_ratio.group(2)
        )

    # Right Issue of Equity Shares
    if re.search(
        r'Right\s+Issue\s+of\s+Equity\s+Shares',
        text,
        re.IGNORECASE
    ):
        return (
            "Rights",
            None,
            None
        )

    # Stock Split
    split_match = re.search(
        r"From\s+R(?:s|e)\.?\s*([\d.]+).*?To\s+R(?:s|e)\.?\s*([\d.]+)",
        text,
        re.IGNORECASE
    )

    if split_match:
        return (
            "Stock Split",
            f"{split_match.group(1)} to {split_match.group(2)}",
            None
        )

    # Bonus only
    if text.lower() == "bonus":
        return (
            "Bonus",
            None,
            None
        )

    # Bonus Ratio
    bonus_match = re.search(r"(\d+\s*:\s*\d+)", text)

    if bonus_match:
        return (
            "Bonus",
            bonus_match.group(1).replace(" ", ""),
            None
        )

    # Dividend / Final Dividend / Special Dividend
    div_match = re.search(
        r"^(Final Dividend|Special Dividend|Interim Dividend|Dividend)\s*-\s*Rs\.?\s*-?\s*([\d.]+)(?:\s*Per\s*Share)?",
        text,
        re.IGNORECASE
    )

    if div_match:
        return (
            div_match.group(1).strip(),
            div_match.group(2).strip(),
            None
        )

    return text.strip(), None, None

def normalize_purpose_value(value):

    if not value:
        return ""

    value = str(value).strip().lower()

    ratio = re.search(r"(\d+\s*:\s*\d+)", value)
    if ratio:
        return ratio.group(1).replace(" ", "")

    number = re.search(r"(\d+(?:\.\d+)?)", value)
    if number:
        return str(float(number.group(1)))

    return value

def to_camel_case(text):
    if not text:
        return ""

    return " ".join(word.capitalize() for word in text.split())
# -----------------------------
# UPLOAD API
@router.post("/upload")
async def upload_csv(
    mkt_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    try:

        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV allowed")

        # -----------------------------
        # 1. READ FILE ONCE
        # -----------------------------
        file_bytes = await file.read()
        csv_data = file_bytes.decode("utf-8", errors="ignore")

        # -----------------------------
        # 2. UPLOAD TO S3 ONCE
        # -----------------------------
        file_obj = io.BytesIO(file_bytes)

        s3_url = upload_file_to_s3(
            file_obj,
            file.filename
        )

        # -----------------------------
        # 3. SAVE UPLOAD RECORD
        # -----------------------------
        upload_record = CorporateActionUpload(
            mkt_date=mkt_date,
            file_name=file.filename,
            file_path=s3_url
        )

        db.add(upload_record)

        # -----------------------------
        # 4. DELETE OLD DATA ONCE
        # -----------------------------
        db.query(CorporateActionData).delete()
        db.commit()

        # -----------------------------
        # 5. PARSE CSV
        # -----------------------------
        reader = csv.DictReader(io.StringIO(csv_data))

        inserted = 0
        skipped = 0

        for row in reader:

            if not any(row.values()):
                continue

            # COMPANY
            raw_company = row.get("Company Name", "")
            company = normalize_company(raw_company)

            if is_skipped_company(company):
                skipped += 1
                continue

            code = str(row.get("Security Code", "")).strip()
            name = row.get("Security Name", "").strip()
            series = row.get("SERIES", "").strip()

            if not code or not company:
                skipped += 1
                continue

            # PURPOSE SPLIT
            purpose_text = row.get("Purpose", "").strip()
            purpose, purpose_value, premium = split_purpose_and_value(purpose_text)

            # INSERT
            data = CorporateActionData(
                SCRIP_CODE_SYMBOL=code,
                SECURITY_NAME=name,
                COMPANY=company,
                SERIES=series,

                EX_DATE=parse_date(row.get("Ex Date")),
                RECORD_DATE=parse_date(row.get("Record Date")),

                PURPOSE=purpose,
                PURPOSE_VALUE=str(purpose_value) if purpose_value else None,
                PREMIUM=str(premium).strip() if premium else None,

                FACE_VALUE=normalize_float(row.get("FACE VALUE")),

                BC_START_DATE=parse_date(row.get("BC Start Date")),
                BC_END_DATE=parse_date(row.get("BC End Date")),

                ND_START_DATE=parse_date(row.get("ND Start Date")),
                ND_END_DATE=parse_date(row.get("ND End Date")),

                ACTUAL_PAYMENT_DATE=parse_date(
                    row.get("Actual Payment Date")
                )
            )

            db.add(data)
            inserted += 1

        db.commit()

        return {
            "message": "Upload successful",
            "inserted": inserted,
            "skipped": skipped,
            "s3_url": s3_url
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
# -----------------------------
# SIMPLE CLEAN
# -----------------------------
def clean(value):
    if not value:
        return None
    return str(value).strip()
    
# -----------------------------
# UPLOAD API
# -----------------------------
@router.post("/upload-results")
async def upload_results(
    mkt_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    try:

        # -----------------------------
        # 1. UPLOAD TO S3
        # -----------------------------
        file_bytes = await file.read()
        file_obj = io.BytesIO(file_bytes)
        s3_url = upload_file_to_s3(
            file_obj,
            file.filename,
        )

        # -----------------------------
        # 2. SAVE UPLOAD RECORD
        # -----------------------------
        upload_record = ResultUpload(
            mkt_date=mkt_date,
            file_name=file.filename,
            file_path=s3_url
        )

        db.add(upload_record)

        # -----------------------------
        # 3. DELETE OLD DATA
        # -----------------------------
        db.query(ResultData).delete()
        db.commit()

        # -----------------------------
        # 4. PARSE CSV AGAIN
        # -----------------------------
        csv_data = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(csv_data))

        inserted = 0

        for row in reader:

            data = ResultData(

                scrip_code_symbol=clean(row.get("Security Code")),
                company=clean(row.get("Company name")),

                Result_date=parse_date(row.get("Result Date")),

            )

            db.add(data)
            inserted += 1

        db.commit()

        return {
            "message": "Upload results successful",
            "s3_url": s3_url,
            "inserted": inserted
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
# -----------------------------
# MANUAL ENTRY API
# -----------------------------
@router.post("/add")
async def add_corporate_action(
    mkt_date: date = Form(...),

    scrip_code: str = Form(...),
    security_name: Optional[str] = Form(None),
    company_name: str = Form(...),
    series: Optional[str] = Form(None),

    ex_date:Optional[date] = Form(None),
    record_date: Optional[date] = Form(None),

    purpose: str = Form(None),
    purpose_value: Optional[str] = Form(None),

    face_value:Optional[float] = Form(None),

    bc_start_date: Optional[date] = Form(None),
    bc_end_date: Optional[date] = Form(None),

    nd_start_date: Optional[date] = Form(None),
    nd_end_date: Optional[date] = Form(None),

    actual_payment_date: Optional[date] = Form(None),

    result_date: Optional[date] = Form(None),
    premium: Optional[str] = Form(None),

    db: Session = Depends(get_db)
):

    try:

        company = normalize_company(company_name)

        if is_skipped_company(company):
            raise HTTPException(
                status_code=400,
                detail="Government companies not allowed"
            )
            
        # ==================================================
        # DUPLICATE CHECK
        # ==================================================
        existing_rows = db.query(CorporateActionData).filter(
                    func.lower(CorporateActionData.COMPANY) == company.lower(),
                    CorporateActionData.EX_DATE == ex_date
                ).all()

        for row in existing_rows:

            if (
            normalize_purpose(row.PURPOSE) ==
            normalize_purpose(purpose)
            and
            normalize_purpose_value(row.PURPOSE_VALUE) ==
            normalize_purpose_value(purpose_value)
            and
            normalize_float(row.PREMIUM) == normalize_float(premium)==
            
            normalize_float(premium) is not None
        ):
                
                raise HTTPException(
            status_code=400,
            detail="Corporate action already exists"
        )
        

        # ==================================================
        # RESULT ENTRY
        # ==================================================
        if purpose and purpose.strip().lower() == "Results":

            # STORE RESULT DATA
            result_data = ResultData(
                scrip_code_symbol=scrip_code.strip(),
                company=company,
                Result_date=parse_date(result_date)
            )

            db.add(result_data)



            db.commit()

            return {
                "message": "Result data added successfully"
            }

        # ==================================================
        # CORPORATE ACTION ENTRY
        # ==================================================
        data = CorporateActionData(

            SCRIP_CODE_SYMBOL=scrip_code.strip(),
            SECURITY_NAME=security_name.strip() if security_name else None,
            COMPANY=company,
            SERIES=series.strip() if series else None,

            EX_DATE=parse_date(ex_date),
            RECORD_DATE=parse_date(record_date),

            PURPOSE=purpose.strip() if purpose else None,
            PURPOSE_VALUE=purpose_value.strip() if purpose_value else None,
            PREMIUM=str(premium).strip() if premium else None,

            FACE_VALUE=normalize_float(face_value),

            BC_START_DATE=parse_date(bc_start_date),
            BC_END_DATE=parse_date(bc_end_date),

            ND_START_DATE=parse_date(nd_start_date),
            ND_END_DATE=parse_date(nd_end_date),

            ACTUAL_PAYMENT_DATE=parse_date(actual_payment_date)
        )

        db.add(data)
        db.flush()

       

        # STORE MANUAL ENTRY RECORD
        manual_entry = ManualEntryUpload(
            company_name=to_camel_case(company_name),
            purpose=purpose.strip() if purpose else None,
            entry_date=date.today()
        )

        db.add(manual_entry)
        db.commit()

        return {
            "message": "Corporate action added successfully"
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



@router.get("/uploads")
def get_uploads(db: Session = Depends(get_db)):

    uploads = db.query(CorporateActionUpload)\
        .order_by(CorporateActionUpload.id.desc())\
        .all()

    return [
        {
            "id": u.id,
            "mkt_date": u.mkt_date,
            "file_name": u.file_name,
            "file_path": u.file_path
        }
        for u in uploads
    ]


@router.get("/results-uploads")
def get_uploads(db: Session = Depends(get_db)):

    uploads = db.query(ResultUpload)\
        .order_by(ResultUpload.id.desc())\
        .all()

    return [
        {
            "id": u.id,
            "mkt_date": u.mkt_date,
            "file_name": u.file_name,
            "file_path": u.file_path
        }
        for u in uploads
    ]
    
# ==============================
# GET MANUAL ENTRY UPLOADS
# ==============================

@router.get("/manual-uploads")
def get_manual_uploads(
    db: Session = Depends(get_db)
):

    data = db.query(ManualEntryUpload)\
        .order_by(ManualEntryUpload.id.desc())\
        .all()

    return [
        {
            "id": d.id,
            "company_name": d.company_name,
            "purpose": d.purpose,
            "entry_date": d.entry_date
        }
        for d in data
    ]
@router.get("/actions")
def get_corporate_data(db: Session = Depends(get_db)):

    data = (
        db.query(CorporateActionData)
        .order_by(CorporateActionData.ID.desc())
        .all()
    )

    seen = set()
    result = []

    for d in data:

        key = (
            normalize_company(d.COMPANY),
            normalize_purpose(d.PURPOSE),
            (d.PURPOSE_VALUE or "").strip(),
            d.EX_DATE
        )

        if key in seen:
            continue

        seen.add(key)

        result.append({
            "id": d.ID,
            "scrip_code_symbol": d.SCRIP_CODE_SYMBOL,
            "security_name": d.SECURITY_NAME,
            "company": to_camel_case(d.COMPANY),
            "series": d.SERIES,
            "ex_date": d.EX_DATE,
            "record_date": d.RECORD_DATE,
            "purpose": d.PURPOSE,
            "purpose_value": d.PURPOSE_VALUE,
            "face_value": d.FACE_VALUE,
            "bc_start_date": d.BC_START_DATE,
            "bc_end_date": d.BC_END_DATE,
            "nd_start_date": d.ND_START_DATE,
            "nd_end_date": d.ND_END_DATE,
            "actual_payment_date": d.ACTUAL_PAYMENT_DATE
        })

    return result


@router.get("/results")
def get_result_data(db: Session = Depends(get_db)):

    data = db.query(ResultData)\
        .order_by(ResultData.id.desc())\
        .all()

    return [
        {
            "id": d.id,
            "scrip_code_symbol": d.scrip_code_symbol,
            "company": to_camel_case(d.company),

            "ex_date": d.Result_date,
            
        }
        for d in data
    ]
@router.get("/actions/grouped-by-purpose")
def get_grouped_by_purpose(db: Session = Depends(get_db)):

    corporate_data = (
        db.query(CorporateActionData)
        .order_by(CorporateActionData.ID.desc())
        .all()
    )

    result_data = db.query(ResultData).all()

    # Remove duplicates
    seen = set()
    filtered_data = []

    for d in corporate_data:

        key = (
            normalize_company(d.COMPANY),
            normalize_purpose(d.PURPOSE),
            normalize_purpose_value(d.PURPOSE_VALUE) 
            if d.PURPOSE_VALUE else "",
            d.EX_DATE
        )

        if key in seen:
            continue

        seen.add(key)
        filtered_data.append(d)

    grouped = {
        "Bonus": [],
        "Stock Split": [],
        "Dividend": [],
        "Rights": [],
        "Share Buyback": [],
        "Results": []
    }

    # Corporate Actions
    for d in filtered_data:

        purpose = (d.PURPOSE or "").lower()

        item = {
            "id": d.ID,
            "scrip_code_symbol": d.SCRIP_CODE_SYMBOL,
            "security_name": d.SECURITY_NAME,
            "company": to_camel_case(d.COMPANY),
            "series": d.SERIES,
            "ex_date": d.EX_DATE,
            "record_date": d.RECORD_DATE,
            "purpose": d.PURPOSE,
            "purpose_value": d.PURPOSE_VALUE,
            "premium": d.PREMIUM,
            "face_value": d.FACE_VALUE,
            "bc_start_date": d.BC_START_DATE,
            "bc_end_date": d.BC_END_DATE,
            "nd_start_date": d.ND_START_DATE,
            "nd_end_date": d.ND_END_DATE,
            "actual_payment_date": d.ACTUAL_PAYMENT_DATE
        }

        if "bonus" in purpose:
            grouped["Bonus"].append(item)

        elif "split" in purpose:
            grouped["Stock Split"].append(item)

        elif "dividend" in purpose:
            grouped["Dividend"].append(item)

        elif "buy back" in purpose or "buyback" in purpose:
            grouped["Share Buyback"].append(item)

        elif "rights" in purpose:
            grouped["Rights"].append(item)

    # Results
    for r in result_data:
        grouped["Results"].append({
            "id": r.id,
            "scrip_code_symbol": r.scrip_code_symbol,
            "company": to_camel_case(r.company),
            "ex_date": r.Result_date,
            "purpose": "Results"
        })

    return grouped



@router.get("/data/company/{company_name}")
def get_by_company(company_name: str, db: Session = Depends(get_db)):

    company_name = company_name.strip().lower()

    results = db.query(CorporateActionData).filter(
        CorporateActionData.COMPANY == company_name
    ).all()

    return results



@router.get("/upload/download/{upload_id}")
def download_upload_file(
    upload_id: int,
    db: Session = Depends(get_db)
):

    try:

        # -----------------------------
        # 1. GET UPLOAD RECORD
        # -----------------------------
        upload = db.query(CorporateActionUpload).filter(
            CorporateActionUpload.id == upload_id
        ).first()

        if not upload:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )

        # -----------------------------
        # 2. GET FILE STREAM FROM S3
        # -----------------------------
        file_stream = get_file_stream_from_s3(upload.file_path)

        if not file_stream:
            raise HTTPException(
                status_code=404,
                detail="File not found in S3"
            )

        # -----------------------------
        # 3. RETURN FILE
        # -----------------------------
        return StreamingResponse(
            file_stream,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{upload.file_name}"'
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
@router.get("/results/download/{upload_id}")
def download_upload_file(
    upload_id: int,
    db: Session = Depends(get_db)
):

    try:

        # -----------------------------
        # 1. GET UPLOAD RECORD
        # -----------------------------
        upload = db.query(ResultUpload).filter(
            ResultUpload.id == upload_id
        ).first()

        if not upload:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )

        # -----------------------------
        # 2. GET FILE STREAM FROM S3
        # -----------------------------
        file_stream = get_file_stream_from_s3(upload.file_path)

        if not file_stream:
            raise HTTPException(
                status_code=404,
                detail="File not found in S3"
            )

        # -----------------------------
        # 3. RETURN FILE
        # -----------------------------
        return StreamingResponse(
            file_stream,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{upload.file_name}"'
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete("/upload/{upload_id}")
def delete_upload(
    upload_id: int,
    db: Session = Depends(get_db)
):

    try:

        # -----------------------------
        # 1. FIND UPLOAD RECORD
        # -----------------------------
        upload = db.query(CorporateActionUpload).filter(
            CorporateActionUpload.id == upload_id
        ).first()

        if not upload:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )

        # -----------------------------
        # 2. DELETE FROM S3
        # -----------------------------
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # -----------------------------
        # 3. DELETE DB RECORD
        # -----------------------------
        db.delete(upload)
        db.commit()

        return {
            "message": "Upload deleted successfully",
            "deleted_id": upload_id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
@router.delete("/results/{upload_id}")
def delete_upload(
    upload_id: int,
    db: Session = Depends(get_db)
):

    try:

        # -----------------------------
        # 1. FIND UPLOAD RECORD
        # -----------------------------
        upload = db.query(ResultUpload).filter(
            ResultUpload.id == upload_id
        ).first()

        if not upload:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )

        # -----------------------------
        # 2. DELETE FROM S3
        # -----------------------------
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # -----------------------------
        # 3. DELETE DB RECORD
        # -----------------------------
        db.delete(upload)
        db.commit()

        return {
            "message": "Upload deleted successfully",
            "deleted_id": upload_id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        
# -----------------------------
# DELETE MANUAL ENTRY
# -----------------------------
@router.delete("/manual-upload/{id}")
async def delete_manual_upload(
    id: int,
    db: Session = Depends(get_db)
):

    try:

        entry = db.query(ManualEntryUpload).filter(
            ManualEntryUpload.id == id
        ).first()

        if not entry:
            raise HTTPException(
                status_code=404,
                detail="Manual entry not found"
            )

        db.delete(entry)

        db.commit()

        return {
            "message": "Manual entry deleted successfully"
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )