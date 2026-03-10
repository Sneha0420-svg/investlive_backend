from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd

from fastapi.responses import StreamingResponse
from app.database import SessionLocal
from app.models.indstocksnapshot_graph import IndStockGraph, IndStockGraphUpload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3
import io

router = APIRouter(prefix="/indstockgraph", tags=["IndStock Graph"])

# ---------------- DB session ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Helpers ----------------
def clean_nan(val):
    return None if isinstance(val, float) and pd.isna(val) else val

# ---------------- Upload ----------------
@router.post("/upload")
async def upload_file(
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    group_id = str(uuid4())
    contents = await file.read()
    file_like = io.BytesIO(contents)
    # Upload to S3
    s3_folder = "indstockgraphgraph"
    s3_key = upload_file_to_s3(file_obj=file_like, folder=s3_folder, filename=file.filename)

    # Read CSV / Excel from file memory
    file.file.seek(0)
    if file.filename.lower().endswith(".csv"):
        df = pd.read_csv(file.file, header=None)
    else:
        df = pd.read_excel(file.file, header=None)

    if df.shape[1] != 6:
        raise HTTPException(
            400,
            "File must have exactly 6 columns: ID, TRN_DATE, STKS_TRD, ADV, DECL, UNCHG"
        )

    df.columns = ["ID", "TRN_DATE", "STKS_TRD", "ADV", "DECL", "UNCHG"]
    df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"]).dt.date

    records = [
        IndStockGraph(
            TRN_DATE=r["TRN_DATE"],
            STKS_TRD=int(r["STKS_TRD"]),
            ADV=int(r["ADV"]),
            DECL=int(r["DECL"]),
            UNCHG=int(r["UNCHG"]),
            group_id=group_id
        )
        for _, r in df.iterrows()
    ]

    upload_row = IndStockGraphUpload(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        data_type="IndStockGraph",
        file_name=file.filename,
        file_path=s3_key  # S3 key instead of local path
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {"message": "Upload successful", "group_id": group_id, "records": len(records)}

# ---------------- Get Uploads ----------------
@router.get("/uploads")
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IndStockGraphUpload).order_by(IndStockGraphUpload.upload_date.desc()).all()
    return [
        {"id": u.id, "group_id": u.group_id, "upload_date": u.upload_date,
         "data_date": u.data_date, "file_name": u.file_name}
        for u in uploads
    ]

# ---------------- Get Latest Data ----------------
@router.get("/latest")
def get_latest_data(db: Session = Depends(get_db)):
    latest_upload = db.query(IndStockGraphUpload).order_by(IndStockGraphUpload.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(404, "No upload data found")

    latest_records = db.query(IndStockGraph).filter(
        IndStockGraph.group_id == latest_upload.group_id
    ).all()

    result = [
        {
            "ID": r.ID,
            "TRN_DATE": r.TRN_DATE,
            "STKS_TRD": r.STKS_TRD,
            "ADV": r.ADV,
            "DECL": r.DECL,
            "UNCHG": r.UNCHG,
            "group_id": r.group_id
        } for r in latest_records
    ]

    return {
        "upload_id": latest_upload.id,
        "data_date": latest_upload.data_date,
        "data_type": latest_upload.data_type,
        "records": result
    }

# ---------------- Download File ----------------
@router.get("/download/{group_id}")
def download_file(group_id: str, db: Session = Depends(get_db)):
    upload = db.query(IndStockGraphUpload).filter(IndStockGraphUpload.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # Stream from S3
    file_stream = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(file_stream, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={upload.file_name}"})

# ---------------- Update Upload ----------------
@router.put("/upload/{group_id}")
async def update_upload(
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    upload = db.query(IndStockGraphUpload).filter(IndStockGraphUpload.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:
        # Delete old file from S3
        delete_file_from_s3(upload.file_path)

        # Upload new file
        s3_folder = "indstockgraph"
        s3_key = upload_file_to_s3(file_obj=file.file, folder=s3_folder, filename=file.filename)
        upload.file_name = file.filename
        upload.file_path = s3_key

        # Delete old data
        db.query(IndStockGraph).filter(IndStockGraph.group_id == group_id).delete(synchronize_session=False)

        # Read new file
        file.file.seek(0)
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file, header=None)
        else:
            df = pd.read_excel(file.file, header=None)

        if df.shape[1] != 6:
            raise HTTPException(400, "File must have exactly 6 columns")

        df.columns = ["ID", "TRN_DATE", "STKS_TRD", "ADV", "DECL", "UNCHG"]
        df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"]).dt.date

        records = [
            IndStockGraph(
                TRN_DATE=r["TRN_DATE"],
                STKS_TRD=int(r["STKS_TRD"]),
                ADV=int(r["ADV"]),
                DECL=int(r["DECL"]),
                UNCHG=int(r["UNCHG"]),
                group_id=group_id
            )
            for _, r in df.iterrows()
        ]
        db.bulk_save_objects(records)

    db.commit()
    return {"message": "Upload updated successfully", "group_id": group_id}

# ---------------- Delete Upload ----------------
@router.delete("/upload/{group_id}")
def delete_upload(group_id: str, db: Session = Depends(get_db)):
    upload = db.query(IndStockGraphUpload).filter(IndStockGraphUpload.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # Delete all records
    db.query(IndStockGraph).filter(IndStockGraph.group_id == group_id).delete(synchronize_session=False)

    # Delete file from S3
    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted successfully"}