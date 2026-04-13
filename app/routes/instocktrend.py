import io
from datetime import date
from typing import List, Dict, Any

import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    Form
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.instocktrend import InstockTrendData, Indstocktrendupload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3

router = APIRouter(
    prefix="/indstocktrend",
    tags=["InstockTrend"]
)

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload")
async def upload_multiple_data(
    files: List[UploadFile] = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    all_records = []
    upload_ids = []

    try:
        for file in files:

            contents = await file.read()
            s3_stream = io.BytesIO(contents)

            # Upload file to S3
            s3_key = upload_file_to_s3(s3_stream, "indstocktrend")

            file_stream = io.BytesIO(contents)

            # Save upload metadata
            upload_record = Indstocktrendupload(
                upload_date=upload_date,
                data_date=data_date,
                data_type=data_type,
                file_name=file.filename,
                file_path=s3_key
            )

            db.add(upload_record)
            db.flush()  # safer than commit inside loop
            upload_ids.append(upload_record.id)

            file_stream.seek(0)

            # Read file
            try:
                if file.filename.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(file_stream, header=None)
                elif file.filename.endswith(".csv"):
                    df = pd.read_csv(file_stream, header=None)
                else:
                    raise HTTPException(400, "Invalid file type")
            except Exception as e:
                raise HTTPException(400, f"Failed to read file: {e}")

            if df.shape[1] != 8:
                raise HTTPException(
                    400,
                    "Excel must have exactly 8 columns: Metric, Count, Day, Week, Month, Quarter, Halfyear, Year"
                )

            df.columns = [
                "description",
                "count",
                "day",
                "week",
                "month",
                "quarter",
                "halfyear",
                "year"
            ]

            for _, row in df.iterrows():
                all_records.append(
                    InstockTrendData(
                        description=str(row["description"]),
                        count=str(row["count"]),
                        day=str(row["day"]),
                        week=str(row["week"]),
                        month=str(row["month"]),
                        quarter=str(row["quarter"]),
                        halfyear=str(row["halfyear"]),
                        year=str(row["year"]),
                       
                    )
                )

        if not all_records:
            raise HTTPException(400, "No valid data found")

        # 🔥🔥🔥 IMPORTANT CHANGE: DELETE OLD DATA FIRST
        db.query(InstockTrendData).delete(synchronize_session=False)

        # Insert new data
        db.bulk_save_objects(all_records)
        db.commit()

        return {
            "message": "Old data deleted and new data inserted successfully",
            "upload_ids": upload_ids,
            "records_inserted": len(all_records)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error: {str(e)}")
    
# -------------------- GET ALL UPLOADS --------------------
@router.get("/uploads/", response_model=List[dict])
def get_uploads(db: Session = Depends(get_db)):

    uploads = db.query(Indstocktrendupload).order_by(
        Indstocktrendupload.upload_date.desc()
    ).all()

    if not uploads:
        raise HTTPException(404, "No uploads found")

    return [
        {
            "id": u.id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_link": f"/indstocktrend/files/{u.id}"
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD FILE --------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):

    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "File not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={upload.file_name}"
        }
    )


# -------------------- GET LATEST DATA --------------------
@router.get("/stockdata/", response_model=Dict[str, Any])
def get_stock_data(db: Session = Depends(get_db)):

    stocks = db.query(InstockTrendData).order_by(InstockTrendData.id).all()

    if not stocks:
        raise HTTPException(status_code=404, detail="No stock data found")

    return {
        "stocks": [
            {
                "id": s.id,
                "description": s.description,
                "count": s.count,
                "day": s.day,
                "week": s.week,
                "month": s.month,
                "quarter": s.quarter,
                "halfyear": s.halfyear,
                "year": s.year
            }
            for s in stocks
        ]
    }

# -------------------- DELETE UPLOAD --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):

    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {
        "message": "Upload deleted successfully",
        "upload_id": upload_id,
    }


# -------------------- UPDATE UPLOAD --------------------
@router.put("/uploads/{upload_id}")
async def update_upload(
    upload_id: int,
    file: UploadFile = File(None),
    upload_date: date = Form(None),
    data_date: date = Form(None),
    db: Session = Depends(get_db)
):

    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # -----------------------------
    # 1. Update metadata FIRST
    # -----------------------------
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    new_records = []

    # -----------------------------
    # 2. If file uploaded → replace data
    # -----------------------------
    if file:

        # delete old file from S3
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        contents = await file.read()
        file_like = io.BytesIO(contents)

        # upload new file
        s3_key = upload_file_to_s3(file_like, "indstocktrend")

        upload.file_name = file.filename
        upload.file_path = s3_key

        file_like.seek(0)

        # read file
        if file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_like, header=None)
        else:
            df = pd.read_csv(file_like, header=None)

        if df.shape[1] != 8:
            raise HTTPException(400, "File must have 8 columns")

        df.columns = [
            "description",
            "count",
            "day",
            "week",
            "month",
            "quarter",
            "halfyear",
            "year"
        ]

        # -----------------------------------
        # 3. DELETE OLD DATA (FIXED VERSION)
        # -----------------------------------
        db.query(InstockTrendData).delete(synchronize_session=False)

        # -----------------------------------
        # 4. INSERT NEW DATA
        # -----------------------------------
        for _, row in df.iterrows():
            new_records.append(
                InstockTrendData(
                    description=str(row["description"]),
                    count=row["count"],
                    day=row["day"],
                    week=row["week"],
                    month=row["month"],
                    quarter=row["quarter"],
                    halfyear=row["halfyear"],
                    year=row["year"],
                )
            )

        db.bulk_save_objects(new_records)

    db.commit()
    db.refresh(upload)

    return {
        "message": "Upload updated successfully",
        "upload_id": upload.id,
        "file_name": upload.file_name,
        "upload_date": upload.upload_date,
        "data_date": upload.data_date,
        "records_inserted": len(new_records)
    }