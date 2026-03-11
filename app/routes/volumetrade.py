import io
from datetime import date
from typing import List
from uuid import uuid4
import math
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.volumetrade import (
    VolumeTradevolume,
    VolumeTradevalue,
    VolumeTradetrade,
    VolumeTradeUpload
)
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

router = APIRouter(prefix="/VolumeTrade", tags=["VolumeTrade Data"])

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- UTILS --------------------
TAB_MODEL_MAPPING = {
    "volume": VolumeTradevolume,
    "value": VolumeTradevalue,
    "trade": VolumeTradetrade
}

COLUMN_MAPPING = {
    "volume": [
        "company","isin","mcap","cmp","volume","spurt","chper",
        "five_dvma","twentyone_dvma","sixty_dvma",
        "two_four_five_dvma","five_two_wkhv","five_two_wklv"
    ],
    "value": [
        "company","isin","mcap","cmp","value","spurt","chper",
        "five_dvma","twentyone_dvma","sixty_dvma",
        "two_four_five_dvma","five_two_wkhv","five_two_wklv"
    ],
    "trade": [
        "company","isin","mcap","cmp","trade","spurt","chper",
        "five_dvma","twentyone_dvma","sixty_dvma",
        "two_four_five_dvma","five_two_wkhv","five_two_wklv"
    ]
}

def clean_nan(val):
    return None if isinstance(val, float) and math.isnan(val) else val

def read_file_bytes(file_bytes: bytes, data_type: str):
    if file_bytes.startswith(b'\x50\x4B\x03\x04') or file_bytes[:2] == b'PK':  # Excel xlsx zip header
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    else:
        df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)
    if df.shape[1] != 13:
        raise HTTPException(400, f"{data_type} file must have 13 columns")
    df.columns = COLUMN_MAPPING[data_type]
    return df.where(pd.notnull(df), None)

def generate_s3_key(data_type: str, filename: str):
    return f"volumetrade/{data_type}/{uuid4()}_{filename}"

# -------------------- UPLOAD --------------------
@router.post("/upload")
async def upload_volume_trade(
    files: List[UploadFile] = File(...),
    data_types: List[str] = Form(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if len(files) != len(data_types):
        raise HTTPException(400, "Number of files and data_types must match")

    group_id = str(uuid4())
    all_records = []

    for file, data_type in zip(files, data_types):
        if data_type not in TAB_MODEL_MAPPING:
            raise HTTPException(400, f"Invalid data_type: {data_type}")

        Model = TAB_MODEL_MAPPING[data_type]
        file_bytes = await file.read()

        # Upload to S3
        s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(data_type, file.filename))

        # Store upload info
        upload_record = VolumeTradeUpload(
            group_id=group_id,
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=file.filename,
            file_path=s3_key
        )
        db.add(upload_record)

        # Read file data
        df = read_file_bytes(file_bytes, data_type)

        # Prepare records
        for _, row in df.iterrows():
            all_records.append(
                Model(
                    upload_date=upload_date,
                    data_date=data_date,
                    **row.to_dict(),
                    group_id=group_id
                   
                )
            )

    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "Files uploaded successfully",
        "group_id": group_id,
        "file_urls": [get_s3_file_url(u.file_path) for u in db.query(VolumeTradeUpload).filter(VolumeTradeUpload.group_id==group_id).all()]
    }

# -------------------- LATEST DATA --------------------
@router.get("/latest")
def get_latest(tab: str = "volume", db: Session = Depends(get_db)):
    if tab not in TAB_MODEL_MAPPING:
        raise HTTPException(400, "Invalid tab. Must be volume, value, or trade")

    Model = TAB_MODEL_MAPPING[tab]
    latest_upload = db.query(Model.upload_date, Model.data_date).order_by(Model.upload_date.desc()).first()
    if not latest_upload:
        raise HTTPException(404, "No data found")

    rows = db.query(Model).filter(
        Model.upload_date == latest_upload.upload_date,
        Model.data_date == latest_upload.data_date
    ).order_by(Model.isin).all()

    return {
        "upload_date": latest_upload.upload_date,
        "data_date": latest_upload.data_date,
        "data": [vars(r) for r in rows]
    }

# -------------------- LIST UPLOADS --------------------
@router.get("/uploads")
def get_uploads_summary(db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).order_by(VolumeTradeUpload.upload_date.desc()).all()
    grouped = {}

    for u in uploads:
        if u.group_id not in grouped:
            grouped[u.group_id] = {
                "group_id": u.group_id,
                "upload_date": u.upload_date,
                "data_date": u.data_date,
                "volume": None,
                "value": None,
                "trade": None,
            }
        grouped[u.group_id][u.data_type] = {
            "file_name": u.file_name,
            "file_id": u.id,
            "file_url": get_s3_file_url(u.file_path)
        }

    return list(grouped.values())

# -------------------- DOWNLOAD --------------------
@router.get("/files/{tab}/{group_id}")
def download_file(tab: str, group_id: str, db: Session = Depends(get_db)):
    upload = db.query(VolumeTradeUpload).filter(
        VolumeTradeUpload.group_id == group_id,
        VolumeTradeUpload.data_type == tab
    ).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(file_stream, media_type="application/octet-stream",
                             headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'})

# -------------------- UPDATE --------------------
@router.put("/upload-group/{group_id}")
async def update_upload_group(
    group_id: str,
    db: Session = Depends(get_db),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    volume_file: UploadFile | None = File(None),
    value_file: UploadFile | None = File(None),
    trade_file: UploadFile | None = File(None),
):
    uploads = db.query(VolumeTradeUpload).filter(VolumeTradeUpload.group_id == group_id).all()
    if not uploads:
        raise HTTPException(404, "Upload group not found")

    file_map = {"volume": volume_file, "value": value_file, "trade": trade_file}

    for upload in uploads:
        if upload_date:
            upload.upload_date = upload_date
        if data_date:
            upload.data_date = data_date

        new_file = file_map.get(upload.data_type)
        if not new_file:
            continue

        Model = TAB_MODEL_MAPPING[upload.data_type]

        # Delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # Upload new file
        file_bytes = await new_file.read()
        s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(upload.data_type, new_file.filename))
        upload.file_name = new_file.filename
        upload.file_path = s3_key

        # Delete old data
        db.query(Model).filter(Model.group_id == group_id).delete(synchronize_session=False)

        # Read new data
        df = read_file_bytes(file_bytes, upload.data_type)
        records = [Model(**row.to_dict(), upload_date=upload.upload_date, data_date=upload.data_date, group_id=group_id)
                   for _, row in df.iterrows()]
        db.bulk_save_objects(records)

    db.commit()
    return {"message": "Upload group updated successfully", "group_id": group_id}

# -------------------- DELETE --------------------
@router.delete("/upload/{group_id}")
def delete_upload_group(group_id: str, db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).filter(VolumeTradeUpload.group_id == group_id).all()
    if not uploads:
        raise HTTPException(404, "Group not found")

    for u in uploads:
        Model = TAB_MODEL_MAPPING[u.data_type]
        db.query(Model).filter(Model.group_id == group_id).delete(synchronize_session=False)

        if u.file_path:
            delete_file_from_s3(u.file_path)

        db.delete(u)

    db.commit()
    return {"detail": "All files deleted successfully"}