import io
from datetime import date
from uuid import uuid4
from typing import List, Dict, Any

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.mostvalued import (
    MostValuedStock,
    MostValuedHouses,
    MostValuedStockUpload,
    MostValuedHousesUpload
)

from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_file_url,
    get_file_stream_from_s3
)

router = APIRouter(prefix="/mostvalued", tags=["Most Valued"])


# ---------------- DB ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Helpers ----------------
def get_models(category: str):
    if category == "stock":
        return MostValuedStock, MostValuedStockUpload, "stock"
    elif category == "house":
        return MostValuedHouses, MostValuedHousesUpload, "house"
    else:
        raise HTTPException(400, "Category must be 'stock' or 'house'")


def read_file(file_bytes: bytes, expected_cols: int, columns: list):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception:
        df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)

    if df.shape[1] != expected_cols:
        raise HTTPException(400, f"File must have {expected_cols} columns")

    df.columns = columns
    return df


# ==========================================================
# UPLOAD (SNAPSHOT REPLACE)
# ==========================================================
@router.post("/upload/{category}")
async def upload_data(
    category: str,
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    DataModel, UploadModel, cat = get_models(category)

    file_bytes = await file.read()

    # Upload file to S3
    s3_key = upload_file_to_s3(
        io.BytesIO(file_bytes),
        f"mostvalued/{category}/{uuid4()}_{file.filename}"
    )

    # Read file structure
    if category == "stock":
        columns = [
            "company", "isin", "today", "p_day", "p_wk",
            "p_mth", "p_qtr", "p_hy", "p_yr"
        ]
    else:
        columns = [
            "house", "today", "p_day", "p_wk",
            "p_mth", "p_qtr", "p_hy", "p_yr"
        ]

    df = read_file(file_bytes, len(columns), columns)

    # =========================
    # SNAPSHOT DELETE
    # =========================
    db.query(DataModel).delete()

    # =========================
    # INSERT DATA
    # =========================
    records = []
    for _, row in df.iterrows():

        if category == "stock":
            records.append(
                MostValuedStock(
                    company=row["company"],
                    isin=row["isin"],
                    today=row["today"],
                    p_day=row["p_day"],
                    p_wk=row["p_wk"],
                    p_mth=row["p_mth"],
                    p_qtr=row["p_qtr"],
                    p_hy=row["p_hy"],
                    p_yr=row["p_yr"]
                )
            )
        else:
            records.append(
                MostValuedHouses(
                    house=row["house"],
                    today=row["today"],
                    p_day=row["p_day"],
                    p_wk=row["p_wk"],
                    p_mth=row["p_mth"],
                    p_qtr=row["p_qtr"],
                    p_hy=row["p_hy"],
                    p_yr=row["p_yr"]
                )
            )

    # =========================
    # UPLOAD RECORD
    # =========================
    upload_row = UploadModel(
        data_date=data_date,
        file_name=file.filename,
        file_path=s3_key
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} uploaded successfully",
        "records_inserted": len(records),
        "file_url": get_s3_file_url(s3_key)
    }


# ==========================================================
# GET LATEST DATA
# ==========================================================
@router.get("/latest")
def get_latest(db: Session = Depends(get_db)):

    stock_data = db.query(MostValuedStock).all()
    house_data = db.query(MostValuedHouses).all()

    def map_stock(r):
        return {
            "company": r.company,
            "isin": r.isin,
            "today": r.today,
            "p_day": r.p_day,
            "p_wk": r.p_wk,
            "p_mth": r.p_mth,
            "p_qtr": r.p_qtr,
            "p_hy": r.p_hy,
            "p_yr": r.p_yr
        }

    def map_house(r):
        return {
            "house": r.house,
            "today": r.today,
            "p_day": r.p_day,
            "p_wk": r.p_wk,
            "p_mth": r.p_mth,
            "p_qtr": r.p_qtr,
            "p_hy": r.p_hy,
            "p_yr": r.p_yr
        }

    return {
        "stock": [map_stock(x) for x in stock_data],
        "house": [map_house(x) for x in house_data]
    }


# ==========================================================
# UPLOAD HISTORY
# ==========================================================
@router.get("/uploads/{category}")
def get_uploads(category: str, db: Session = Depends(get_db)):

    _, UploadModel, _ = get_models(category)

    uploads = db.query(UploadModel).order_by(
        UploadModel.data_date.desc()
    ).all()

    return [
        {
            "id": u.id,
            "data_date": u.data_date,
            "file_name": u.file_name,
            "file_url": get_s3_file_url(u.file_path)
        }
        for u in uploads
    ]


# ==========================================================
# DOWNLOAD FILE
# ==========================================================
@router.get("/download/{category}/{upload_id}")
def download(category: str, upload_id: int, db: Session = Depends(get_db)):

    _, UploadModel, _ = get_models(category)

    upload = db.query(UploadModel).filter(
        UploadModel.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "File not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )

# ==========================================================
# UPDATE UPLOAD
# ==========================================================
@router.put("/upload/{category}/{upload_id}")
async def update_upload(
    category: str,
    upload_id: int,
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    DataModel, UploadModel, cat = get_models(category)

    upload = db.query(UploadModel).filter(
        UploadModel.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    new_records = []

    # =========================
    # UPDATE METADATA
    # =========================


    if data_date:
        upload.data_date = data_date

    # =========================
    # IF NEW FILE UPLOADED
    # =========================
    if file:

        file_bytes = await file.read()

        # delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # upload new file
        s3_key = upload_file_to_s3(
            io.BytesIO(file_bytes),
            f"mostvalued/{category}/{uuid4()}_{file.filename}"
        )

        upload.file_name = file.filename
        upload.file_path = s3_key

        # =========================
        # SNAPSHOT REPLACE DATA
        # =========================
        db.query(DataModel).delete()

        # define columns
        if category == "stock":
            columns = [
                "company", "isin", "today", "p_day", "p_wk",
                "p_mth", "p_qtr", "p_hy", "p_yr"
            ]
        else:
            columns = [
                "house", "today", "p_day", "p_wk",
                "p_mth", "p_qtr", "p_hy", "p_yr"
            ]

        df = read_file(file_bytes, len(columns), columns)

        for _, row in df.iterrows():

            if category == "stock":
                new_records.append(
                    MostValuedStock(
                        company=row["company"],
                        isin=row["isin"],
                        today=row["today"],
                        p_day=row["p_day"],
                        p_wk=row["p_wk"],
                        p_mth=row["p_mth"],
                        p_qtr=row["p_qtr"],
                        p_hy=row["p_hy"],
                        p_yr=row["p_yr"]
                    )
                )
            else:
                new_records.append(
                    MostValuedHouses(
                        house=row["house"],
                        today=row["today"],
                        p_day=row["p_day"],
                        p_wk=row["p_wk"],
                        p_mth=row["p_mth"],
                        p_qtr=row["p_qtr"],
                        p_hy=row["p_hy"],
                        p_yr=row["p_yr"]
                    )
                )

        db.bulk_save_objects(new_records)

    db.commit()
    db.refresh(upload)

    return {
        "message": f"{category} upload updated successfully",
        "upload_id": upload.id,
        "file_name": upload.file_name,
        "data_date": upload.data_date,
        "records_inserted": len(new_records)
    }
# ==========================================================
# DELETE UPLOAD
# ==========================================================
@router.delete("/upload/{category}/{upload_id}")
def delete_upload(category: str, upload_id: int, db: Session = Depends(get_db)):

    DataModel, UploadModel, _ = get_models(category)

    upload = db.query(UploadModel).filter(
        UploadModel.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # delete all snapshot data
    db.query(DataModel).delete()

    # delete file from S3
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted successfully"}