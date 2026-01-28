from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List
import pandas as pd
import os
from uuid import uuid4
import math

from app.database import SessionLocal
from app.models.volumetrade import (
    VolumeTradevolume,
    VolumeTradevalue,
    VolumeTradetrade,
    VolumeTradeUpload
)
from app.schemas.volumetrade import UploadSummaryResponse,UploadSummaryMultiFiles
from fastapi.responses import FileResponse

UPLOAD_FOLDER = "uploads/volume"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(prefix="/VolumeTrade", tags=["VolumeTrade Data"])

# -------------------- Database Session --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- Utility Functions --------------------
TAB_MODEL_MAPPING = {
    "volume": VolumeTradevolume,
    "value": VolumeTradevalue,
    "trade": VolumeTradetrade
}

def clean_objs(objs):
    for obj in objs:
        for attr in vars(obj):
            val = getattr(obj, attr)
            if isinstance(val, float) and math.isnan(val):
                setattr(obj, attr, None)
    return objs


# -------------------- Upload Endpoint for Multiple Tabs --------------------
@router.post("/upload")
async def upload_three_tabs(
    files: List[UploadFile] = File(...),
    data_types: List[str] = Form(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if len(files) != len(data_types):
        raise HTTPException(400, "Number of files and data_types must match")

    # 🔥 ONE COMMON GROUP ID
    group_id = str(uuid4())

    all_records = []

    for file, data_type in zip(files, data_types):

        if data_type not in TAB_MODEL_MAPPING:
            raise HTTPException(400, f"Invalid data_type: {data_type}")

        Model = TAB_MODEL_MAPPING[data_type]

        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, "wb") as f:
            f.write(await file.read())

        # ✅ SAME group_id for all 3
        upload_record = VolumeTradeUpload(
            group_id=group_id,
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=filename,
            file_path=file_path
        )
        db.add(upload_record)

        # Read file
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        if df.shape[1] != 13:
            raise HTTPException(400, f"{data_type} file must have 13 columns")

        df.columns = [
            "company","isin","mcap","cmp","volume","spurt","chper",
            "five_dvma","twentyone_dvma","sixty_dvma",
            "two_four_five_dvma","five_two_wkhv","five_two_wklv"
        ]

        df = df.where(pd.notnull(df), None)

        for _, row in df.iterrows():
            all_records.append(
                Model(
                    upload_date=upload_date,
                    data_date=data_date,
                    **row.to_dict()
                )
            )

    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "3 files uploaded as one group",
        "group_id": group_id
    }


# -------------------- Get Latest Data --------------------
@router.get("/latest")
def get_latest_all(tab: str = "volume", db: Session = Depends(get_db)):

    if tab not in TAB_MODEL_MAPPING:
        raise HTTPException(400, "Invalid tab. Must be volume, value, or trade.")

    Model = TAB_MODEL_MAPPING[tab]

    latest_upload = db.query(
        Model.upload_date,
        Model.data_date
    ).order_by(Model.upload_date.desc()).first()

    if not latest_upload:
        raise HTTPException(404, "No data found")

    rows = db.query(Model).filter(
        Model.upload_date == latest_upload.upload_date,
        Model.data_date == latest_upload.data_date
    ).order_by(Model.isin).all()

    return {
        "upload_date": latest_upload.upload_date,
        "data_date": latest_upload.data_date,
        "data": clean_objs(rows)
    }


# -------------------- Get Upload Summary --------------------
@router.get("/uploads")
def get_uploads_summary(db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).order_by(
        VolumeTradeUpload.upload_date.desc()
    ).all()

    grouped = {}

    for u in uploads:
        gid = u.group_id
        if gid not in grouped:
            grouped[gid] = {
                "group_id": gid,
                "upload_date": u.upload_date,
                "data_date": u.data_date,
                "volume": None,
                "value": None,
                "trade": None,
            }

        grouped[gid][u.data_type] = {
            "file_name": u.file_name,
            "file_id": u.id
        }

    return list(grouped.values())


# -------------------- Download Uploaded File --------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(VolumeTradeUpload).filter(VolumeTradeUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    if not upload.file_path or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found on server")

    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )


# -------------------- Update Upload --------------------
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
        raise HTTPException(404, "Upload group not found")

    file_map = {
        "volume": volume_file,
        "value": value_file,
        "trade": trade_file
    }

    for upload in uploads:
        # update dates
        if upload_date:
            upload.upload_date = upload_date
        if data_date:
            upload.data_date = data_date

        new_file = file_map.get(upload.data_type)
        if not new_file:
            continue  # skip if no new file for this type

        Model = TAB_MODEL_MAPPING[upload.data_type]

        # remove old file
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        filename = f"{date.today()}_{uuid4()}_{new_file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, "wb") as f:
            f.write(await new_file.read())

        upload.file_name = filename
        upload.file_path = file_path

        # delete old table rows
        db.query(Model).filter(
            Model.upload_date == upload.upload_date,
            Model.data_date == upload.data_date
        ).delete(synchronize_session=False)

        # read new data
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        if df.shape[1] != 13:
            raise HTTPException(400, f"{upload.data_type} must have 13 columns")

        df.columns = [
            "company","isin","mcap","cmp","volume","spurt","chper",
            "five_dvma","twentyone_dvma","sixty_dvma",
            "two_four_five_dvma","five_two_wkhv","five_two_wklv"
        ]
        df = df.where(pd.notnull(df), None)

        records = [
            Model(
                upload_date=upload.upload_date,
                data_date=upload.data_date,
                **row.to_dict()
            )
            for _, row in df.iterrows()
        ]

        db.bulk_save_objects(records)

    db.commit()

    return {
        "message": "Upload group updated successfully",
        "group_id": group_id
    }



# -------------------- Delete Upload --------------------
@router.delete("/upload/{group_id}")
def delete_upload_group(group_id: str, db: Session = Depends(get_db)):
    uploads = db.query(VolumeTradeUpload).filter(
        VolumeTradeUpload.group_id == group_id
    ).all()

    if not uploads:
        raise HTTPException(404, "Group not found")

    for u in uploads:
        Model = TAB_MODEL_MAPPING[u.data_type]

        # delete table data
        db.query(Model).filter(
            Model.upload_date == u.upload_date,
            Model.data_date == u.data_date
        ).delete(synchronize_session=False)

        if os.path.exists(u.file_path):
            os.remove(u.file_path)

        db.delete(u)

    db.commit()
    return {"detail": "All 3 files deleted successfully"}
