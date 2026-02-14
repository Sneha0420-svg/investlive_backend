from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date
from uuid import uuid4
import pandas as pd
import os
import math
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models.managerrank import LMRank, LMRankUpload, LMSub, LMSubUpload

UPLOAD_FOLDER = "uploads/manager_rank"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# ---------------- Upload ----------------
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
    filename = f"{date.today()}_{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 🔥 IMPORTANT: No header in Excel
    if filename.endswith(".csv"):
        df = pd.read_csv(file_path, header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    # ========================================================
    # LM RANK
    # ========================================================
    if category == "lm_rank":

        UploadModel = LMRankUpload
        DataModel = LMRank

        # Expecting 20 columns (ID + 19 actual columns)
        if df.shape[1] != 20:
            raise HTTPException(
                400,
                "lm_rank file must have 20 columns (first column is ID and will be ignored)"
            )

        # 🔥 Ignore first column (ID)
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

        # Full refresh
        db.query(DataModel).delete(synchronize_session=False)

        records = [
            DataModel(
                lm_code=str(r["LM_CODE"]),
                lm_name=str(r["LM_NAME"]),
                cos=int(r["COS"]),

                ipo_val=r["IPO_VAL"],
                applications=r["APPLICATIONS"],
                subs_amount=r["SUBS_AMOUNT"],

                list_value=r["LIST_VALUE"],
                list_gain_per=r["LIST_GAIN_PER"],

                qtrly_value=r["QTRLY_VALUE"],
                qtr_gain_per=r["QTR_GAIN_PER"],

                hlf_yr_value=r["HLF_YR_VALUE"],
                hlf_gain_per=r["HLF_GAIN_PER"],

                yrly_value=r["YRLY_VALUE"],
                yr_gain_per=r["YR_GAIN_PER"],

                one_hlf_yr_value=r["ONE_HLF_YR_VALUE"],
                one_hlf_gain_per=r["ONE_HLF_GAIN_PER"],

                curr_value=r["CURR_VALUE"],
                cur_gain_per=r["CUR_GAIN_PER"],

                consol_rnk=r["CONSOL_RNK"],
                group_id=group_id,
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
            raise HTTPException(
                400,
                "lm_sub file must have 11 columns"
            )
        


        df.columns = [
            "LM_CODE", "ISIN", "COMPANY",
            "ISS_OPEN", "IPO_PR", "IPO_VAL",
            "LISTED_PR", "CMP",
            "CUR_VAL", "GAIN_VAL", "GAIN_PERC"
        ]

        db.query(DataModel).delete(synchronize_session=False)

        records = [
            DataModel(
                lm_code=str(r["LM_CODE"]),
                isin=str(r["ISIN"]),
                company=str(r["COMPANY"]),
                iss_open=pd.to_datetime(r["ISS_OPEN"]).date(),

                ipo_pr=r["IPO_PR"],
                ipo_val=r["IPO_VAL"],
                listed_pr=r["LISTED_PR"],
                cmp=r["CMP"],
                cur_val=r["CUR_VAL"],
                gain_val=r["GAIN_VAL"],
                gain_perc=r["GAIN_PERC"],
                group_id=group_id,
            )
            for _, r in df.iterrows()
        ]

    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        category=category,
        file_name=filename,
        file_path=file_path
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} uploaded successfully",
        "group_id": group_id,
        "records": len(records)
    }

# ---------------- Get Uploads ----------------
@router.get("/uploads/{category}")
def get_uploads(category: str, db: Session = Depends(get_db)):
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")
    UploadModel = LMRankUpload if category=="lm_rank" else LMSubUpload
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
    return [
        {"id": u.id, "group_id": u.group_id, "upload_date": u.upload_date,
         "data_date": u.data_date, "file_name": u.file_name}
        for u in uploads
    ]
# ---------------- Get Latest Data ----------------
@router.get("/latest/{category}")
def get_latest_data(category: str, db: Session = Depends(get_db)):
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload
    DataModel = LMRank if category == "lm_rank" else LMSub

    # Get latest upload by data_date
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(404, "No upload found")

    # Get data for that upload's group_id
    latest_records = db.query(DataModel).filter(DataModel.group_id == latest_upload.group_id).all()

    # Use correct attribute names (case-sensitive)
    result = []
    for r in latest_records:
        row = {}
        for column in DataModel.__table__.columns:
            attr = column.key.lower()  # force lowercase
            row[column.name] = getattr(r, attr)
        result.append(row)

    return result


# ---------------- Download Uploaded File ----------------
@router.get("/download/{category}/{group_id}")
def download_file(category: str, group_id: str, db: Session = Depends(get_db)):
    """
    Download the uploaded file for a specific category and group_id.
    """
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = LMRankUpload if category == "lm_rank" else LMSubUpload

    # Get the upload record
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found on server")

    # Return the file for download
    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )
# ---------------- Get data by LM_CODE ----------------
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

# ---------------- Update ----------------
@router.put("/upload/{category}/{group_id}")
async def update_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = LMRankUpload if category=="lm_rank" else LMSubUpload
    DataModel = LMRank if category=="lm_rank" else LMSub
    upload = db.query(UploadModel).filter(UploadModel.group_id==group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:
        # delete old file
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        upload.file_name = filename
        upload.file_path = file_path

        # Delete old data
        db.query(DataModel).delete(synchronize_session=False)

        # Read new file (no header)
        if filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)

        # Ignore first column (index/ID)
        if df.shape[1] > 1:
            df = df.iloc[:, 1:]

        # LM Rank
        if category=="lm_rank":
            if df.shape[1] != 19:
                raise HTTPException(400, "lm_rank file must have 20 columns including index, 19 actual columns expected after ignoring first column")
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
                    group_id=group_id,
                )
                for _, r in df.iterrows()
            ]
        else:  # LM Sub
            if df.shape[1] != 11:
                raise HTTPException(400, "lm_sub file must have 11 columns after ignoring first column")
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
                    group_id=group_id,
                )
                for _, r in df.iterrows()
            ]

        db.bulk_save_objects(records)

    db.commit()
    return {"message": "Upload updated successfully", "group_id": group_id}

# ---------------- Delete ----------------
@router.delete("/upload/{category}/{group_id}")
def delete_upload(category: str, group_id: str, db: Session = Depends(get_db)):
    if category not in ["lm_rank", "lm_sub"]:
        raise HTTPException(400, "Invalid category")

    UploadModel = LMRankUpload if category=="lm_rank" else LMSubUpload
    DataModel = LMRank if category=="lm_rank" else LMSub
    upload = db.query(UploadModel).filter(UploadModel.group_id==group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # Delete data
    db.query(DataModel).filter(DataModel.group_id==group_id).delete(synchronize_session=False)

    # Delete file
    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    # Delete upload record
    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted successfully"}
