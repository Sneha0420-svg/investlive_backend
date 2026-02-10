from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd
import os
import math
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models.mcapgainerloser import (
    McapGainersLosers,
    McapGainersLosersUpload,
   Upward_DownwardMobile,
   Upward_DownwardMobileUpload,
   Up_DownTrend,
    Up_DownTrendUpload
)

UPLOAD_FOLDER = "uploads/gainer_loser"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(prefix="/gainloss", tags=["Gainers / Losers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- helper ----------
def clean_nan(val):
    return None if isinstance(val, float) and math.isnan(val) else val

# ---------- Upload endpoint ----------
@router.post("/upload/{category}")
async def upload_file(
    category: str,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- create unique group_id and save file ----------
    group_id = str(uuid4())
    filename = f"{date.today()}_{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # ---------- read file ----------
    if filename.endswith(".csv"):
        df = pd.read_csv(file_path, header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    # ---------- select models & columns ----------
    if category == "mcap_movers":
        DataModel = McapGainersLosers
        UploadModel = McapGainersLosersUpload

        expected_cols = 16
        df.columns = [
            "COMPANY", "ISIN", "CMP",
            "MCAP_CR", "CH_CR", "CH_PER",
            "VOL_NOS", "VOL_CH_PER",
            "DAY_HIGH", "DAY_LOW",
            "60DMA", "60DMA_PER",
            "245DMA", "245DMA_PER",
            "52WKH", "52WKL"
        ]

    elif category == "up_down_mobile":
        DataModel = Upward_DownwardMobile
        UploadModel = Upward_DownwardMobileUpload

        expected_cols = 7
        df.columns = [
            "COMPANY", "ISIN", "CMP",
            "START", "DAYS",
            "CH_PER", "PERDAY"
        ]

    else:  # up_down_trend
        DataModel = Up_DownTrend
        UploadModel = Up_DownTrendUpload

        expected_cols = 8
        df.columns = [
            "COMPANY", "ISIN", "CMP",
            "5DMA", "21DMA", "60DMA", "245DMA",
            "CH_PER"
        ]

    # ---------- validate columns ----------
    if df.shape[1] != expected_cols:
        raise HTTPException(
            400,
            f"{category} file must have exactly {expected_cols} columns"
        )

    # ---------- store upload info ----------
    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        category=category,
        file_name=filename,
        file_path=file_path
    )
    db.add(upload_row)

    # ---------- check latest upload ----------
    latest_upload = (
        db.query(UploadModel)
        .order_by(UploadModel.data_date.desc())
        .first()
    )

    if not latest_upload or data_date >= latest_upload.data_date:
        db.query(DataModel).delete(synchronize_session=False)

        # ---------- parse and save ----------
        if category == "mcap_movers":
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    MCAP_CR=clean_nan(r["MCAP_CR"]),
                    CH_CR=clean_nan(r["CH_CR"]),
                    CH_PER=clean_nan(r["CH_PER"]),
                    VOL_NOS=clean_nan(r["VOL_NOS"]),
                    VOL_CH_PER=clean_nan(r["VOL_CH_PER"]),
                    DAY_HIGH=clean_nan(r["DAY_HIGH"]),
                    DAY_LOW=clean_nan(r["DAY_LOW"]),
                    DMA_60=clean_nan(r["60DMA"]),
                    DMA_PER_60=clean_nan(r["60DMA_PER"]),
                    DMA_245=clean_nan(r["245DMA"]),
                    DMA_PER_245=clean_nan(r["245DMA_PER"]),
                    WKH_52=clean_nan(r["52WKH"]),
                    WKL_52=clean_nan(r["52WKL"]),
                    group_id=group_id
                )
                for _, r in df.iterrows()
            ]

        elif category == "up_down_mobile":
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    START=clean_nan(r["START"]),
                    DAYS=int(r["DAYS"]) if pd.notna(r["DAYS"]) else None,
                    CH_PER=clean_nan(r["CH_PER"]),
                    PERDAY=clean_nan(r["PERDAY"]),
                    group_id=group_id
                )
                for _, r in df.iterrows()
            ]

        else:  # up_down_trend
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    DMA_5=clean_nan(r["5DMA"]),
                    DMA_21=clean_nan(r["21DMA"]),
                    DMA_60=clean_nan(r["60DMA"]),
                    DMA_245=clean_nan(r["245DMA"]),
                    CH_PER=clean_nan(r["CH_PER"]),
                    group_id=group_id
                )
                for _, r in df.iterrows()
            ]

        db.bulk_save_objects(records)

    db.commit()

    return {
        "message": f"{category} data uploaded successfully",
        "group_id": group_id,
        "records": len(df)
    }
@router.get("/uploads/{category}")
def get_uploads(
    category: str,
    db: Session = Depends(get_db)
):
    # ---------- validate category ----------
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400, "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- select upload model ----------
    if category == "mcap_movers":
        UploadModel = McapGainersLosersUpload
    elif category == "up_down_mobile":
        UploadModel = Upward_DownwardMobileUpload
    else:  # up_down_trend
        UploadModel = Up_DownTrendUpload

    # ---------- fetch uploads ----------
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()

    # ---------- serialize ----------
    return [
        {
            "id": u.id,
            "group_id": u.group_id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "file_name": u.file_name
        }
        for u in uploads
    ]

@router.get("/latest/{category}")
def get_latest_data(
    category: str,
    db: Session = Depends(get_db)
):
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- select models ----------
    if category == "mcap_movers":
        UploadModel = McapGainersLosersUpload
        DataModel = McapGainersLosers

    elif category == "up_down_mobile":
        UploadModel = Upward_DownwardMobileUpload
        DataModel = Upward_DownwardMobile

    else:  # up_down_trend
        UploadModel = Up_DownTrendUpload
        DataModel = Up_DownTrend

    # ---------- get latest upload ----------
    latest_upload = (
        db.query(UploadModel)
        .order_by(UploadModel.data_date.desc())
        .first()
    )

    if not latest_upload:
        return {
            "latest_data_date": None,
            "records": [],
            "count": 0
        }

    # ---------- fetch latest records ----------
    data_rows = (
        db.query(DataModel)
        .filter(DataModel.group_id == latest_upload.group_id)
        .all()
    )

    # ---------- serialize ----------
    records = []
    for row in data_rows:
        r = row.__dict__.copy()
        r.pop("_sa_instance_state", None)
        records.append(r)

    return {
        "latest_data_date": latest_upload.data_date,
        "records": records,
        "count": len(records)
    }

@router.get("/download/{category}/{group_id}")
def download_file(
    category: str,
    group_id: str,
    db: Session = Depends(get_db)
):
    # ---------- validate category ----------
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- select upload model ----------
    if category == "mcap_movers":
        UploadModel = McapGainersLosersUpload
    elif category == "up_down_mobile":
        UploadModel = Upward_DownwardMobileUpload
    else:  # up_down_trend
        UploadModel = Up_DownTrendUpload

    # ---------- fetch upload by group_id ----------
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # ---------- check file existence ----------
    if not upload.file_path or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found on server")

    # ---------- return file ----------
    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )

@router.put("/upload/{category}/{group_id}")
async def update_file_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # ---------- validate category ----------
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- select models ----------
    if category == "mcap_movers":
        UploadModel = McapGainersLosersUpload
        DataModel = McapGainersLosers
        expected_cols = 16
        df_columns = [
            "COMPANY", "ISIN", "CMP", "MCAP_CR", "GAIN_CR", "GAIN_PER",
            "VOL_NOS", "VOL_CH_PER", "DAY_HIGH", "DAY_LOW",
            "DMA_60", "DMA_60_PER", "DMA_245", "DMA_245_PER", "WKH_52", "WKL_52"
        ]
    elif category == "up_down_mobile":
        UploadModel = Upward_DownwardMobileUpload
        DataModel = Upward_DownwardMobile
        expected_cols = 7
        df_columns = ["COMPANY", "ISIN", "CMP", "START", "DAYS", "CH_PER", "PERDAY"]
    else:  # up_down_trend
        UploadModel = Up_DownTrendUpload
        DataModel = Up_DownTrend
        expected_cols = 8
        df_columns = ["COMPANY", "ISIN", "CMP", "DMA_5", "DMA_21", "DMA_60", "DMA_245", "CH_PER"]

    # ---------- fetch upload ----------
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # ---------- update dates ----------
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    # ---------- replace file ----------
    if file:
        # remove old file
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        upload.file_name = filename
        upload.file_path = file_path

        # delete old data
        db.query(DataModel).delete(synchronize_session=False)

        # read new file
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        if df.shape[1] != expected_cols:
            raise HTTPException(
                400,
                f"{category} file must have exactly {expected_cols} columns"
            )
        df.columns = df_columns

        # parse records
        if category == "mcap_movers":
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    MCAP_CR=clean_nan(r["MCAP_CR"]),
                    GAIN_CR=clean_nan(r["GAIN_CR"]),
                    GAIN_PER=clean_nan(r["GAIN_PER"]),
                    VOL_NOS=clean_nan(r["VOL_NOS"]),
                    VOL_CH_PER=clean_nan(r["VOL_CH_PER"]),
                    DAY_HIGH=clean_nan(r["DAY_HIGH"]),
                    DAY_LOW=clean_nan(r["DAY_LOW"]),
                    DMA_60=clean_nan(r["DMA_60"]),
                    DMA_60_PER=clean_nan(r["DMA_60_PER"]),
                    DMA_245=clean_nan(r["DMA_245"]),
                    DMA_245_PER=clean_nan(r["DMA_245_PER"]),
                    WKH_52=clean_nan(r["WKH_52"]),
                    WKL_52=clean_nan(r["WKL_52"]),
                    group_id=group_id,
                )
                for _, r in df.iterrows()
            ]
        elif category == "up_down_mobile":
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    START=clean_nan(r["START"]),
                    DAYS=int(r["DAYS"]) if r["DAYS"] is not None else None,
                    CH_PER=clean_nan(r["CH_PER"]),
                    PERDAY=clean_nan(r["PERDAY"]),
                    group_id=group_id,
                )
                for _, r in df.iterrows()
            ]
        else:  # up_down_trend
            records = [
                DataModel(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    DMA_5=clean_nan(r["DMA_5"]),
                    DMA_21=clean_nan(r["DMA_21"]),
                    DMA_60=clean_nan(r["DMA_60"]),
                    DMA_245=clean_nan(r["DMA_245"]),
                    CH_PER=clean_nan(r["CH_PER"]),
                    group_id=group_id,
                )
                for _, r in df.iterrows()
            ]

        db.bulk_save_objects(records)

    db.commit()

    return {
        "message": "Upload updated successfully",
        "group_id": group_id
    }

@router.delete("/upload/{category}/{group_id}")
def delete_new_high_low_upload(
    category: str,
    group_id: str,
    db: Session = Depends(get_db)
):
    if category not in ["52-week", "multi-year","circuit"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = (
        McapGainersLosersUpload
        if category == "52-week"
        else Upward_DownwardMobileUpload
        if category == "circuit"
        else  Up_DownTrendUpload
    )
    DataModel = (
        McapGainersLosers
        if category == "52-week"
        else Upward_DownwardMobile
        if category == "circuit"
        else  Up_DownTrend
    )

    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # delete data
    db.query(DataModel).delete(synchronize_session=False)

    # delete file
    if os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted successfully"}
@router.delete("/upload/{category}/{group_id}")
def delete_file_upload(
    category: str,
    group_id: str,
    db: Session = Depends(get_db)
):
    # ---------- validate category ----------
    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400, "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # ---------- select models ----------
    if category == "mcap_movers":
        UploadModel = McapGainersLosersUpload
        DataModel = McapGainersLosers
    elif category == "up_down_mobile":
        UploadModel = Upward_DownwardMobileUpload
        DataModel = Upward_DownwardMobile
    else:  # up_down_trend
        UploadModel = Up_DownTrendUpload
        DataModel = Up_DownTrend

    # ---------- fetch upload ----------
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # ---------- delete associated data ----------
    db.query(DataModel).filter(DataModel.group_id == group_id).delete(synchronize_session=False)

    # ---------- delete file ----------
    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    # ---------- delete upload record ----------
    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted successfully"}
