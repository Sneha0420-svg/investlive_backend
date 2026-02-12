from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd
import os
from typing import List
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models.indstocksnapshot_graph import (
    IndStockGraph,
    IndStockGraphUpload
)

UPLOAD_FOLDER = "uploads/indstockgraph"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(prefix="/indstockgraph", tags=["IndStock Graph"])


# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- UPLOAD EXCEL --------------------
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

    for file in files:

        group_id = str(uuid4())
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save upload metadata
        upload_record = IndStockGraphUpload(
            group_id=group_id,
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=filename,
            file_path=file_path
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        upload_ids.append(upload_record.id)

        # Read Excel / CSV
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_path, header=None)
            elif filename.endswith(".csv"):
                df = pd.read_csv(file_path, header=None)
            else:
                raise HTTPException(status_code=400, detail="Invalid file type")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

        # ✅ Correct column validation (6 columns)
        if df.shape[1] != 6:
            raise HTTPException(
                status_code=400,
                detail="File must contain exactly 6 columns: "
                       "ID, TRN_DATE, STKS_TRD, ADV, DECL, UNCHG"
            )

        # Assign column names
        df.columns = [
            "ID",
            "TRN_DATE",
            "STKS_TRD",
            "ADV",
            "DECL",
            "UNCHG"
        ]

        # Convert TRN_DATE properly
        df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"]).dt.date

        # Insert rows
        for _, row in df.iterrows():
            record = IndStockGraph(
                ID=int(row["ID"]),
                TRN_DATE=row["TRN_DATE"],
                STKS_TRD=int(row["STKS_TRD"]),
                ADV=int(row["ADV"]),
                DECL=int(row["DECL"]),
                UNCHG=int(row["UNCHG"]),
                group_id=group_id   # ✅ comma fixed
            )
            all_records.append(record)

    if not all_records:
        raise HTTPException(status_code=400, detail="No valid data found")

    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "Files uploaded successfully",
        "upload_ids": upload_ids,
        "records_inserted": len(all_records)
    }
@router.get("/uploads")
def get_all_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IndStockGraphUpload).order_by(
        IndStockGraphUpload.id.desc()
    ).all()

    return uploads

@router.get("/latest-graph")
def get_latest_data(db: Session = Depends(get_db)):
    # Step 1: Get latest upload by data_date
    latest_upload = db.query(IndStockGraphUpload).order_by(
        IndStockGraphUpload.data_date.desc()
    ).first()

    if not latest_upload:
        raise HTTPException(status_code=404, detail="No upload data found")

    # Step 2: Get graph data using group_id
    graph_data = db.query(IndStockGraph).filter(
        IndStockGraph.group_id == latest_upload.group_id
    ).all()

    return {
        "upload_id": latest_upload.id,
        "data_date": latest_upload.data_date,
        "data_type": latest_upload.data_type,
        "graph_data": graph_data
    }

@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IndStockGraphUpload).filter(
        IndStockGraphUpload.id == upload_id
    ).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found")

    return FileResponse(
        upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )


@router.get("/uploads/{upload_id}")
def get_single_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IndStockGraphUpload).filter(
        IndStockGraphUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    graph_data = db.query(IndStockGraph).filter(
        IndStockGraph.group_id == upload.group_id
    ).all()

    return {
        "upload": upload,
        "graph_data": graph_data
    }

@router.put("/uploads/{upload_id}")
def update_upload(
    upload_id: int,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    upload = db.query(IndStockGraphUpload).filter(
        IndStockGraphUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.upload_date = upload_date
    upload.data_date = data_date
    upload.data_type = data_type

    db.commit()
    db.refresh(upload)

    return {
        "message": "Upload updated successfully",
        "upload": upload
    }

@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IndStockGraphUpload).filter(
        IndStockGraphUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete related graph records
    db.query(IndStockGraph).filter(
        IndStockGraph.group_id == upload.group_id
    ).delete()

    # Delete file from disk
    if os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    # Delete upload metadata
    db.delete(upload)
    db.commit()

    return {"message": "Upload and related data deleted successfully"}
