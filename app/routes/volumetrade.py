import io
from datetime import date
from typing import List
from uuid import uuid4
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

# -------------------- DB --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- MAPPING --------------------
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


def read_file_bytes(file_bytes: bytes, data_type: str):
    if file_bytes.startswith(b'\x50\x4B'):
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    else:
        df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)

    if df.shape[1] != 13:
        raise HTTPException(400, f"{data_type} file must have 13 columns")

    df.columns = COLUMN_MAPPING[data_type]
    return df.where(pd.notnull(df), None)


def generate_s3_key(data_type: str, filename: str):
    return f"volumetrade/{data_type}/{uuid4()}_{filename}"


# =====================================================
# UPLOAD (FULL REPLACE)
# =====================================================
@router.post("/upload")
async def upload_volume_trade(
    files: List[UploadFile] = File(...),
    data_types: List[str] = Form(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if len(files) != len(data_types):
        raise HTTPException(400, "Files and data_types mismatch")

    group_id = str(uuid4())
    all_records = []

    # 1. DELETE OLD DATA
    for dt in set(data_types):
        Model = TAB_MODEL_MAPPING[dt]
        db.query(Model).delete(synchronize_session=False)

    # 2. PROCESS FILES
    for file, data_type in zip(files, data_types):

        Model = TAB_MODEL_MAPPING[data_type]
        file_bytes = await file.read()

        # upload to S3
        s3_key = upload_file_to_s3(
            io.BytesIO(file_bytes),
            generate_s3_key(data_type, file.filename)
        )

        # store upload metadata ONLY HERE
        upload_record = VolumeTradeUpload(
            group_id=group_id,
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=file.filename,
            file_path=s3_key
        )
        db.add(upload_record)

        # read data
        df = read_file_bytes(file_bytes, data_type)

        # IMPORTANT: DO NOT ADD upload metadata here ❌
        for _, row in df.iterrows():
            all_records.append(Model(**row.to_dict()))

    # 3. INSERT DATA
    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "Upload successful (data replaced)",
        "group_id": group_id,
        "records_inserted": len(all_records)
    }


# =====================================================
# LATEST DATA
# =====================================================
@router.get("/latest")
def get_latest(tab: str = "volume", db: Session = Depends(get_db)):
    if tab not in TAB_MODEL_MAPPING:
        raise HTTPException(400, "Invalid tab")

    Model = TAB_MODEL_MAPPING[tab]
    rows = db.query(Model).order_by(Model.isin).all()

    return {
        "data": [vars(r) for r in rows]
    }


# =====================================================
# UPLOADS GROUPED
# =====================================================
@router.get("/uploads")
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).order_by(
        VolumeTradeUpload.upload_date.desc()
    ).all()

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


# =====================================================
# DOWNLOAD
# =====================================================
@router.get("/files/{tab}/{group_id}")
def download_file(tab: str, group_id: str, db: Session = Depends(get_db)):
    upload = db.query(VolumeTradeUpload).filter(
        VolumeTradeUpload.group_id == group_id,
        VolumeTradeUpload.data_type == tab
    ).first()

    if not upload:
        raise HTTPException(404, "Not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )


# =====================================================
# UPDATE GROUP
# =====================================================
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
    uploads = db.query(VolumeTradeUpload).filter(
        VolumeTradeUpload.group_id == group_id
    ).all()

    if not uploads:
        raise HTTPException(404, "Group not found")

    file_map = {
        "volume": volume_file,
        "value": value_file,
        "trade": trade_file
    }

    for upload in uploads:

        if upload_date:
            upload.upload_date = upload_date
        if data_date:
            upload.data_date = data_date

        new_file = file_map.get(upload.data_type)
        Model = TAB_MODEL_MAPPING[upload.data_type]

        if new_file:
            if upload.file_path:
                delete_file_from_s3(upload.file_path)

            file_bytes = await new_file.read()
            s3_key = upload_file_to_s3(
                io.BytesIO(file_bytes),
                generate_s3_key(upload.data_type, new_file.filename)
            )

            upload.file_name = new_file.filename
            upload.file_path = s3_key

            df = read_file_bytes(file_bytes, upload.data_type)

            db.query(Model).delete(synchronize_session=False)

            db.bulk_save_objects([
                Model(**row.to_dict())
                for _, row in df.iterrows()
            ])

    db.commit()

    return {
        "message": "Updated successfully",
        "group_id": group_id
    }


# =====================================================
# DELETE GROUP
# =====================================================
@router.delete("/upload/{group_id}")
def delete_upload_group(group_id: str, db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).filter(
        VolumeTradeUpload.group_id == group_id
    ).all()

    if not uploads:
        raise HTTPException(404, "Group not found")

    for u in uploads:
        Model = TAB_MODEL_MAPPING[u.data_type]

        db.query(Model).delete(synchronize_session=False)

        if u.file_path:
            delete_file_from_s3(u.file_path)

        db.delete(u)

    db.commit()

    return {"message": "Deleted successfully"}