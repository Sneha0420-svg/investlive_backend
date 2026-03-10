from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd
import io
import math

from app.database import SessionLocal
from app.models.managerrank import LMRank, LMRankUpload, LMSub, LMSubUpload
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3
)

router = APIRouter(prefix="/manager-rank", tags=["Manager Rank"])


# ---------------- DB session ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Helpers ----------------
def clean_nan(val):
    return None if isinstance(val, float) and math.isnan(val) else val


# ==========================================================
# Upload
# ==========================================================
@router.post("/upload/{category}")
async def upload_file(
    category: str,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Category must be 'lm_rank' or 'lm_sub'")

    group_id = str(uuid4())

    contents = await file.read()

    # Upload to S3
    s3_key = upload_file_to_s3(io.BytesIO(contents), f"manager_rank/{category}")

    # Read dataframe
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents), header=None)
    else:
        df = pd.read_excel(io.BytesIO(contents), header=None)

    # ========================================================
    # LM RANK
    # ========================================================
    if category == "lm_rank":

        UploadModel = LMRankUpload
        DataModel = LMRank

        if df.shape[1] != 20:
            raise HTTPException(400, "lm_rank file must have 20 columns")

        df = df.iloc[:, 1:]

        df.columns = [
            "LM_CODE", "LM_NAME", "COS",
            "IPO_VAL", "APPLICATIONS", "SUBS_AMOUNT",
            "LIST_VALUE", "LIST_GAIN_PER",
            "QTRLY_VALUE", "QTR_GAIN_PER",
            "HLF_YR_VALUE", "HLF_GAIN_PER",
            "YRLY_VALUE", "YR_GAIN_PER",
            "ONE_HLF_YR_VALUE", "ONE_HLF_GAIN_PER",
            "CURR_VALUE", "CUR_GAIN_PER",
            "CONSOL_RNK"
        ]

        records = [
            DataModel(
                lm_code=str(r["LM_CODE"]),
                lm_name=str(r["LM_NAME"]),
                cos=clean_nan(r["COS"]),
                ipo_val=clean_nan(r["IPO_VAL"]),
                applications=clean_nan(r["APPLICATIONS"]),
                subs_amount=clean_nan(r["SUBS_AMOUNT"]),
                list_value=clean_nan(r["LIST_VALUE"]),
                list_gain_per=clean_nan(r["LIST_GAIN_PER"]),
                qtrly_value=clean_nan(r["QTRLY_VALUE"]),
                qtr_gain_per=clean_nan(r["QTR_GAIN_PER"]),
                hlf_yr_value=clean_nan(r["HLF_YR_VALUE"]),
                hlf_gain_per=clean_nan(r["HLF_GAIN_PER"]),
                yrly_value=clean_nan(r["YRLY_VALUE"]),
                yr_gain_per=clean_nan(r["YR_GAIN_PER"]),
                one_hlf_yr_value=clean_nan(r["ONE_HLF_YR_VALUE"]),
                one_hlf_gain_per=clean_nan(r["ONE_HLF_GAIN_PER"]),
                curr_value=clean_nan(r["CURR_VALUE"]),
                cur_gain_per=clean_nan(r["CUR_GAIN_PER"]),
                consol_rnk=clean_nan(r["CONSOL_RNK"]),
                group_id=group_id
            )
            for _, r in df.iterrows()
        ]

    # ========================================================
    # LM SUB
    # ========================================================
    else:

        UploadModel = LMSubUpload
        DataModel = LMSub

        if df.shape[1] > 11:
            df = df.iloc[:, 1:]

        if df.shape[1] != 11:
            raise HTTPException(400, "lm_sub file must have 11 columns")

        df.columns = [
            "LM_CODE", "ISIN", "COMPANY",
            "ISS_OPEN", "IPO_PR", "IPO_VAL",
            "LISTED_PR", "CMP",
            "CUR_VAL", "GAIN_VAL", "GAIN_PERC"
        ]

        records = [
            DataModel(
                lm_code=str(r["LM_CODE"]),
                isin=str(r["ISIN"]),
                company=str(r["COMPANY"]),
                iss_open=pd.to_datetime(r["ISS_OPEN"]).date(),
                ipo_pr=clean_nan(r["IPO_PR"]),
                ipo_val=clean_nan(r["IPO_VAL"]),
                listed_pr=clean_nan(r["LISTED_PR"]),
                cmp=clean_nan(r["CMP"]),
                cur_val=clean_nan(r["CUR_VAL"]),
                gain_val=clean_nan(r["GAIN_VAL"]),
                gain_perc=clean_nan(r["GAIN_PERC"]),
                group_id=group_id
            )
            for _, r in df.iterrows()
        ]

    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        category=category,
        file_name=file.filename,
        file_path=s3_key
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} uploaded successfully",
        "group_id": group_id,
        "records": len(records)
    }


# ==========================================================
# Get Upload History
# ==========================================================
@router.get("/uploads/{category}")
def get_uploads(category: str, db: Session = Depends(get_db)):

    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload

    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()

    return uploads


# ==========================================================
# Get Latest Data
# ==========================================================
@router.get("/latest/{category}")
def get_latest_data(category: str, db: Session = Depends(get_db)):

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload
    DataModel = LMRank if category == "lm_rank" else LMSub

    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()

    if not latest_upload:
        raise HTTPException(404, "No upload found")

    data = db.query(DataModel).filter(DataModel.group_id == latest_upload.group_id).all()

    return data

@router.get("/{category}/{lm_code}")
def get_by_lm_code(category: str, lm_code: str, db: Session = Depends(get_db)):
    """
    Get all data for a specific LM_CODE in either 'lm_rank' or 'lm_sub'
    """
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    DataModel = LMRank if category == "lm_rank" else LMSub

    records = db.query(DataModel).filter(DataModel.lm_code == lm_code).all()

    if not records:
        raise HTTPException(404, f"No records found for LM_CODE {lm_code}")

    # Convert ORM objects to dict
    result = []
    for r in records:
        row = {}
        for column in DataModel.__table__.columns:
            attr = column.key.lower()
            row[column.name] = getattr(r, attr)
        result.append(row)

    return result
# ==========================================================
# Download File
# ==========================================================
@router.get("/download/{category}/{group_id}")
def download_file(category: str, group_id: str, db: Session = Depends(get_db)):

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload

    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    return get_file_stream_from_s3(upload.file_path)


# ==========================================================
# Update Upload
# ==========================================================
@router.put("/upload/{category}/{group_id}")
async def update_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload
    DataModel = LMRank if category == "lm_rank" else LMSub

    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date

    if data_date:
        upload.data_date = data_date

    if file:

        delete_file_from_s3(upload.file_path)

        contents = await file.read()

        s3_key = upload_file_to_s3(io.BytesIO(contents), f"manager_rank/{category}")

        upload.file_name = file.filename
        upload.file_path = s3_key

    db.commit()

    return {"message": "Upload updated successfully"}


# ==========================================================
# Delete Upload
# ==========================================================
@router.delete("/upload/{category}/{group_id}")
def delete_upload(category: str, group_id: str, db: Session = Depends(get_db)):

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload
    DataModel = LMRank if category == "lm_rank" else LMSub

    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    db.query(DataModel).filter(DataModel.group_id == group_id).delete()

    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted successfully"}