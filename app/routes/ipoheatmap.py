from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import date
import pandas as pd
import io
from sqlalchemy import extract
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.ipoheatmap import (
    IPOHeatmapYear,
    IPOHeatmapYearUpload,
    IPOHeatmapData,
    IPOHeatmapDataUpload,
)
from app.schemas.ipoheatmap import (
    IPOHeatmapYearRead,
    IPOHeatmapYearUploadRead,
    IPOHeatmapDataRead,
    IPOHeatmapDataUploadRead,
)
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

router = APIRouter(
    prefix="/ipoheatmap",
    tags=["IPO Heatmap"],
)

# ---------------- DATABASE SESSION ---------------- #
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================
# YEAR ROUTES
# =========================================================

@router.post("/year/upload-file", response_model=IPOHeatmapYearUploadRead)
async def upload_year_file(
    file: UploadFile = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only CSV or Excel allowed")

    contents = await file.read()

    # Upload to S3
    s3_stream = io.BytesIO(contents)
    s3_key = upload_file_to_s3(s3_stream, "ipoheatmap/year")

    # Read dataframe
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents), header=None)
    else:
        df = pd.read_excel(io.BytesIO(contents), header=None)

    df = df.iloc[:, 1:]
    df.columns = ["year", "cos", "ipo_value", "market_value", "ch_per"]

    try:
        # Clear old data
        db.query(IPOHeatmapYear).delete()

        records = [
            IPOHeatmapYear(
                year=int(row["year"]),
                cos=int(row["cos"]),
                ipo_value=float(row["ipo_value"]),
                market_value=float(row["market_value"]),
                ch_per=float(row["ch_per"]),
            )
            for _, row in df.iterrows()
        ]

        db.bulk_save_objects(records)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    upload_obj = IPOHeatmapYearUpload(
        upload_date=upload_date,
        data_date=data_date,
        data_type="Year CSV/Excel",
        file_name=file.filename,
        file_path=s3_key,
    )

    db.add(upload_obj)
    db.commit()
    db.refresh(upload_obj)

    return {
        **upload_obj.__dict__,
        "file_url": get_s3_file_url(upload_obj.file_path)
    }


@router.get("/year/latest", response_model=List[IPOHeatmapYearRead])
def get_latest_year_data(db: Session = Depends(get_db)):
    data = db.query(IPOHeatmapYear).all()
    if not data:
        raise HTTPException(status_code=404, detail="No year data found")
    return data


@router.get("/year/uploads", response_model=List[IPOHeatmapYearUploadRead])
def get_year_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IPOHeatmapYearUpload)\
        .order_by(IPOHeatmapYearUpload.upload_date.desc())\
        .all()

    result = []
    for u in uploads:
        result.append({
            **u.__dict__,
            "file_url": get_s3_file_url(u.file_path)
        })
    return result



@router.get("/year/download/{upload_id}")
def download_year_file(upload_id: int, db: Session = Depends(get_db)):

    upload = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )


@router.put("/year/uploads/{upload_id}", response_model=IPOHeatmapYearUploadRead)
async def update_year_upload(
    upload_id: int,
    file: UploadFile | None = File(None),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    db: Session = Depends(get_db),
):
    upload = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:
        if not file.filename.endswith((".csv", ".xlsx")):
            raise HTTPException(status_code=400, detail="Only CSV or Excel allowed")

        delete_file_from_s3(upload.file_path)

        contents = await file.read()
        s3_stream = io.BytesIO(contents)
        s3_key = upload_file_to_s3(s3_stream, "ipoheatmap/year")

        upload.file_name = file.filename
        upload.file_path = s3_key

    db.commit()
    db.refresh(upload)

    return {
        **upload.__dict__,
        "file_url": get_s3_file_url(upload.file_path)
    }


@router.delete("/year/uploads/{upload_id}")
def delete_year_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    delete_file_from_s3(upload.file_path)
    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted successfully"}


# =========================================================
# DATA ROUTES
# =========================================================

@router.post("/data/upload-file", response_model=IPOHeatmapDataUploadRead)
async def upload_data_file(
    file: UploadFile = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only CSV or Excel allowed")

    contents = await file.read()

    s3_stream = io.BytesIO(contents)
    s3_key = upload_file_to_s3(s3_stream, "ipoheatmap/data")

    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents), header=None)
    else:
        df = pd.read_excel(io.BytesIO(contents), header=None)

    df = df.iloc[:, 1:]
    df.columns = ["company", "iss_open", "offer_price", "cmp", "ipo_value", "cur_value", "gain_per"]

    try:
        db.query(IPOHeatmapData).delete()
        records = [
            IPOHeatmapData(
                company=row["company"],
                iss_open=pd.to_datetime(row["iss_open"]),
                offer_price=float(row["offer_price"]),
                cmp=float(row["cmp"]),
                ipo_value=float(row["ipo_value"]),
                cur_value=float(row["cur_value"]),
                gain_per=float(row["gain_per"]),
            )
            for _, row in df.iterrows()
        ]
        db.bulk_save_objects(records)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    upload_obj = IPOHeatmapDataUpload(
        upload_date=upload_date,
        data_date=data_date,
        data_type="Data CSV/Excel",
        file_name=file.filename,
        file_path=s3_key,
    )

    db.add(upload_obj)
    db.commit()
    db.refresh(upload_obj)

    return {
        **upload_obj.__dict__,
        "file_url": get_s3_file_url(upload_obj.file_path)
    }


@router.get("/data/latest", response_model=List[IPOHeatmapDataRead])
def get_latest_data(db: Session = Depends(get_db)):
    data = db.query(IPOHeatmapData).all()
    if not data:
        raise HTTPException(status_code=404, detail="No IPO data found")
    return data


@router.get("/data/yearwise", response_model=List[IPOHeatmapDataRead])
def get_data_by_year(year: int = Query(..., description="Year filter"), db: Session = Depends(get_db)):
    data = db.query(IPOHeatmapData).filter(extract("year", IPOHeatmapData.iss_open) == year).all()
    if not data:
        raise HTTPException(status_code=404, detail=f"No IPO data found for year {year}")
    return data


@router.get("/data/uploads", response_model=List[IPOHeatmapDataUploadRead])
def get_data_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IPOHeatmapDataUpload).order_by(IPOHeatmapDataUpload.upload_date.desc()).all()
    result = []
    for u in uploads:
        result.append({
            **u.__dict__,
            "file_url": get_s3_file_url(u.file_path)
        })
    return result


@router.get("/data/download/{upload_id}")
def download_data_file(upload_id: int, db: Session = Depends(get_db)):

    upload = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )

@router.put("/data/uploads/{upload_id}", response_model=IPOHeatmapDataUploadRead)
async def update_data_upload(
    upload_id: int,
    file: UploadFile | None = File(None),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    db: Session = Depends(get_db),
):
    upload = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:
        if not file.filename.endswith((".csv", ".xlsx")):
            raise HTTPException(status_code=400, detail="Only CSV or Excel allowed")

        delete_file_from_s3(upload.file_path)
        contents = await file.read()
        s3_stream = io.BytesIO(contents)
        s3_key = upload_file_to_s3(s3_stream, "ipoheatmap/data")
        upload.file_name = file.filename
        upload.file_path = s3_key

    db.commit()
    db.refresh(upload)

    return {
        **upload.__dict__,
        "file_url": get_s3_file_url(upload.file_path)
    }


@router.delete("/data/uploads/{upload_id}")
def delete_data_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    delete_file_from_s3(upload.file_path)
    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted successfully"}