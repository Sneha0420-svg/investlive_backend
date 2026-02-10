from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd
import os
import math
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models.newhighlow import (
    FiftyTwoWeekHighLow,
    FiftyTwoWeekHighLowUpload,
    MultiYearHighLow,
    MultiYearHighLowUpload,
    CircuitUpLow,
    CircuitUpLowUpload
)

UPLOAD_FOLDER = "uploads/newhighlow"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(prefix="/NewHighLow", tags=["New High / Low"])


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
async def upload_new_high_low(
    category: str,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if category not in ["52-week", "multi-year", "circuit"]:
        raise HTTPException(400, "Category must be '52-week', 'multi-year', or 'circuit'")

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
    if category == "52-week":
        DataModel = FiftyTwoWeekHighLow
        UploadModel = FiftyTwoWeekHighLowUpload
        expected_cols = 7
        df_columns = ["COMPANY", "ISIN", "CMP", "52WKH", "52WKL", "CH_RS", "CH_PER"]
    elif category == "circuit":
        DataModel = CircuitUpLow
        UploadModel = CircuitUpLowUpload
        expected_cols = 11
        df_columns = ["COMPANY", "ISIN", "CMP", "CH_PER", "VOL", "VALUE", "TRADE",
                      "52WKH", "52WKHDT", "52WKL", "52WKLDT"]
    else:  # multi-year
        DataModel = MultiYearHighLow
        UploadModel = MultiYearHighLowUpload
        expected_cols = 11
        df_columns = ["COMPANY", "ISIN", "MCAP", "CMP",
                      "MYRH", "MYRH_DT", "MYRL", "MYRL_DT",
                      "SINCE", "TYPE", "ID"]

    # ---------- validate columns ----------
    if df.shape[1] != expected_cols:
        raise HTTPException(400, f"{category} file must have exactly {expected_cols} columns")
    df.columns = df_columns

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

    # ---------- check latest data_date ----------
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()

    # Insert data if:
    # 1. First upload (latest_upload is None), or
    # 2. New upload is latest (data_date >= latest_upload.data_date)
    if not latest_upload or data_date >= latest_upload.data_date:
        # Delete old data in DataModel
        db.query(DataModel).delete(synchronize_session=False)

        # ---------- parse and save records ----------
        if category == "52-week":
            records = [
                DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    WKH_52=clean_nan(row["52WKH"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    CH_RS=clean_nan(row["CH_RS"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    group_id=group_id
                )
                for _, row in df.iterrows()
            ]
        elif category == "circuit":
            records = [
                DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    VOL=row["VOL"],
                    VALUE=row["VALUE"],
                    TRADE=row["TRADE"],
                    WKH_52=clean_nan(row["52WKH"]),
                    WKH_DT_52=str(row["52WKHDT"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    WKL_DT_52=str(row["52WKLDT"]),
                    group_id=group_id
                )
                for _, row in df.iterrows()
            ]
        else:  # multi-year
            records = [
                DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    MCAP=clean_nan(row["MCAP"]),
                    CMP=clean_nan(row["CMP"]),
                    MYRH=clean_nan(row["MYRH"]),
                    MYRH_DT=str(row["MYRH_DT"]),
                    MYRL=clean_nan(row["MYRL"]),
                    MYRL_DT=str(row["MYRL_DT"]),
                    SINCE=str(row["SINCE"]),
                    TYPE=int(row["TYPE"]),
                    ID=int(row["ID"]),
                    group_id=group_id
                )
                for _, row in df.iterrows()
            ]

        db.bulk_save_objects(records)

    # ---------- commit everything ----------
    db.commit()

    return {
        "message": f"{category} data uploaded successfully",
        "group_id": group_id,
        "records": len(df)
    }
@router.get("/uploads/{category}")
def get_new_high_low_uploads(
    category: str,
    db: Session = Depends(get_db)
):
    if category not in ["52-week", "multi-year","circuit"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = (
        FiftyTwoWeekHighLowUpload
        if category == "52-week"
        else CircuitUpLowUpload
        if category == "circuit"
        else MultiYearHighLowUpload
    )

    uploads = db.query(UploadModel).order_by(
        UploadModel.upload_date.desc()
    ).all()

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
def get_latest_data_new_high_low(category: str, db: Session = Depends(get_db)):
    if category not in ["52-week", "multi-year","circuit"]:
        raise HTTPException(400, "Invalid category")

    # Select models based on category
    UploadModel = FiftyTwoWeekHighLowUpload if category == "52-week" else CircuitUpLowUpload if category == "circuit" else MultiYearHighLowUpload
    DataModel = FiftyTwoWeekHighLow if category == "52-week" else CircuitUpLow if category == "circuit" else MultiYearHighLow

    # Find latest data_date
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        return {"message": "No uploads found", "records": []}

    latest_date = latest_upload.data_date

    # Fetch all data rows corresponding to that latest data_date
    # ⚠️ Ideally, your data table should have `group_id` to filter, otherwise get all
    if hasattr(DataModel, "group_id"):
        data_rows = db.query(DataModel).filter(DataModel.group_id == latest_upload.group_id).all()
    else:
        data_rows = db.query(DataModel).all()  # fallback if no group_id

    # Convert to dictionary
    result = [row.__dict__ for row in data_rows]
    # Remove SQLAlchemy internal key
    for r in result:
        r.pop("_sa_instance_state", None)

    return {
        "latest_data_date": latest_date,
        "records": result,
        "count": len(result)
    }
@router.get("/download/{category}/{group_id}")
def download_new_high_low_file(category: str, group_id: str, db: Session = Depends(get_db)):
    if category not in ["52-week", "multi-year","circuit"]:
        raise HTTPException(400, "Invalid category")

    # Select upload model based on category
    UploadModel = FiftyTwoWeekHighLowUpload if category == "52-week" else CircuitUpLowUpload if category == "circuit" else MultiYearHighLowUpload

    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if not upload.file_path or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found on server")

    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )
@router.put("/upload/{category}/{group_id}")
async def update_new_high_low_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if category not in ["52-week", "multi-year","circuit"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = (
        FiftyTwoWeekHighLowUpload
        if category == "52-week"
        else CircuitUpLowUpload
        if category == "circuit"
        else MultiYearHighLowUpload
    )
    DataModel = (
        FiftyTwoWeekHighLow
        if category == "52-week"
        else CircuitUpLow
        if category == "circuit"
        else MultiYearHighLow
    )

    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # ---------- update dates ----------
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    # ---------- replace file ----------
    if file:
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

        # ---------- parse ----------
        if category == "52-week":
            if df.shape[1] != 7:
                raise HTTPException(400, "52-week file must have exactly 7 columns")

            df.columns = [
                "COMPANY", "ISIN", "CMP",
                "52WKH", "52WKL", "CH_RS", "CH_PER"
            ]

            records = [
                FiftyTwoWeekHighLow(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    CMP=clean_nan(r["CMP"]),
                    WKH_52=clean_nan(r["52WKH"]),
                    WKL_52=clean_nan(r["52WKL"]),
                    CH_RS=clean_nan(r["CH_RS"]),
                    CH_PER=clean_nan(r["CH_PER"])
                )
                for _, r in df.iterrows()
            ]
        elif category == "circuit": 
            if df.shape[1] != 11:
                raise HTTPException(400, "Circuit file must have exactly 11 columns")
            df.columns=["COMPANY", "ISIN", "CMP", "CH_PER", "VOL", "VALUE", "TRADE",
                       "52WKH", "52WKHDT", "52WKL", "52WKLDT"]
        else:
            if df.shape[1] != 11:
                raise HTTPException(400, "Multi-year file must have exactly 11 columns")

            df.columns = [
                "COMPANY", "ISIN", "MCAP", "CMP",
                "MYRH", "MYRH_DT", "MYRL", "MYRL_DT",
                "SINCE", "TYPE", "ID"
            ]

            records = [
                MultiYearHighLow(
                    COMPANY=clean_nan(r["COMPANY"]),
                    ISIN=r["ISIN"],
                    MCAP=clean_nan(r["MCAP"]),
                    CMP=clean_nan(r["CMP"]),
                    MYRH=clean_nan(r["MYRH"]),
                    MYRH_DT=str(r["MYRH_DT"]),
                    MYRL=clean_nan(r["MYRL"]),
                    MYRL_DT=str(r["MYRL_DT"]),
                    SINCE=str(r["SINCE"]),
                    TYPE=int(r["TYPE"]),
                    ID=int(r["ID"])
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
        FiftyTwoWeekHighLowUpload
        if category == "52-week"
        else CircuitUpLowUpload
        if category == "circuit"
        else MultiYearHighLowUpload
    )
    DataModel = (
        FiftyTwoWeekHighLow
        if category == "52-week"
        else CircuitUpLow
        if category == "circuit"
        else MultiYearHighLow
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
