from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import pandas as pd
import math
from fastapi.responses import StreamingResponse
import io 

from app.database import SessionLocal
from app.models.mcapgainerloser import (
    McapGainersLosers,
    McapGainersLosersUpload,
    Upward_DownwardMobile,
    Upward_DownwardMobileUpload,
    Up_DownTrend,
    Up_DownTrendUpload
)

from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

router = APIRouter(prefix="/gainloss", tags=["Gainers / Losers"])


# ---------------- DB Dependency ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Helper ----------------

def clean_nan(val):
    return None if isinstance(val, float) and math.isnan(val) else val


def validate_category(category):
    if category not in CATEGORIES:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )


# ---------------- Category Mapping ----------------

CATEGORIES = {
    "mcap_movers": {
        "data": McapGainersLosers,
        "upload": McapGainersLosersUpload,
        "cols": [
            "COMPANY","ISIN","CMP","MCAP_CR","CH_CR","CH_PER",
            "VOL_NOS","VOL_CH_PER","DAY_HIGH","DAY_LOW",
            "60DMA","60DMA_PER","245DMA","245DMA_PER","52WKH","52WKL"
        ]
    },

    "up_down_mobile": {
        "data": Upward_DownwardMobile,
        "upload": Upward_DownwardMobileUpload,
        "cols": [
            "COMPANY","ISIN","CMP","START","DAYS","CH_PER","PERDAY"
        ]
    },

    "up_down_trend": {
        "data": Up_DownTrend,
        "upload": Up_DownTrendUpload,
        "cols": [
            "COMPANY","ISIN","CMP","5DMA","21DMA","60DMA","245DMA","CH_PER"
        ]
    }
}


# ---------------- Upload ----------------
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

    contents = await file.read()

    # upload to S3
    s3_key = upload_file_to_s3(io.BytesIO(contents), f"gainloss/{category}")

    # select models
    if category == "mcap_movers":
        DataModel = McapGainersLosers
        UploadModel = McapGainersLosersUpload

        expected_cols = 16
        columns = [
            "COMPANY","ISIN","CMP","MCAP_CR","CH_CR","CH_PER",
            "VOL_NOS","VOL_CH_PER","DAY_HIGH","DAY_LOW",
            "60DMA","60DMA_PER","245DMA","245DMA_PER","52WKH","52WKL"
        ]

    elif category == "up_down_mobile":
        DataModel = Upward_DownwardMobile
        UploadModel = Upward_DownwardMobileUpload

        expected_cols = 7
        columns = [
            "COMPANY","ISIN","CMP","START","DAYS","CH_PER","PERDAY"
        ]

    else:
        DataModel = Up_DownTrend
        UploadModel = Up_DownTrendUpload

        expected_cols = 8
        columns = [
            "COMPANY","ISIN","CMP","5DMA","21DMA","60DMA","245DMA","CH_PER"
        ]

    # save upload record
    upload_record = UploadModel(
        group_id=str(uuid4()),
        upload_date=upload_date,
        data_date=data_date,
        category=category,
        file_name=file.filename,
        file_path=s3_key
    )

    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)

    # read dataframe
    try:
        if file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents), header=None)
        elif file.filename.endswith(".csv"):
            df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
        else:
            raise HTTPException(400, "Invalid file type")
    except Exception as e:
        raise HTTPException(400, f"Failed to read file: {e}")

    if df.shape[1] != expected_cols:
        raise HTTPException(
            400,
            f"{category} file must have exactly {expected_cols} columns"
        )

    df.columns = columns

    # delete previous latest data if newer
    latest_upload = (
        db.query(UploadModel)
        .order_by(UploadModel.data_date.desc())
        .first()
    )

    if not latest_upload or data_date >= latest_upload.data_date:
        db.query(DataModel).delete(synchronize_session=False)

    records = []

    for _, r in df.iterrows():

        if category == "mcap_movers":

            record = DataModel(
                COMPANY=r["COMPANY"],
                ISIN=r["ISIN"],
                CMP=r["CMP"],
                MCAP_CR=r["MCAP_CR"],
                CH_CR=r["CH_CR"],
                CH_PER=r["CH_PER"],
                VOL_NOS=r["VOL_NOS"],
                VOL_CH_PER=r["VOL_CH_PER"],
                DAY_HIGH=r["DAY_HIGH"],
                DAY_LOW=r["DAY_LOW"],
                DMA_60=r["60DMA"],
                DMA_PER_60=r["60DMA_PER"],
                DMA_245=r["245DMA"],
                DMA_PER_245=r["245DMA_PER"],
                WKH_52=r["52WKH"],
                WKL_52=r["52WKL"],
                group_id=upload_record.group_id
            )

        elif category == "up_down_mobile":

            record = DataModel(
                COMPANY=r["COMPANY"],
                ISIN=r["ISIN"],
                CMP=r["CMP"],
                START=r["START"],
                DAYS=r["DAYS"],
                CH_PER=r["CH_PER"],
                PERDAY=r["PERDAY"],
                group_id=upload_record.group_id
            )

        else:

            record = DataModel(
                COMPANY=r["COMPANY"],
                ISIN=r["ISIN"],
                CMP=r["CMP"],
                DMA_5=r["5DMA"],
                DMA_21=r["21DMA"],
                DMA_60=r["60DMA"],
                DMA_245=r["245DMA"],
                CH_PER=r["CH_PER"],
                group_id=upload_record.group_id
            )

        records.append(record)

    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} uploaded successfully",
        "records_inserted": len(records),
        "upload_id": upload_record.id
    }

# ---------------- Upload History ----------------

@router.get("/uploads/{category}")
def get_uploads(category: str, db: Session = Depends(get_db)):

    validate_category(category)

    UploadModel = CATEGORIES[category]["upload"]

    uploads = db.query(UploadModel).order_by(
        UploadModel.upload_date.desc()
    ).all()

    return [
        {
            "id": u.id,
            "group_id": u.group_id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "file_name": u.file_name,
            "file_url": get_s3_file_url(u.file_path)
        }
        for u in uploads
    ]


# ---------------- Latest Data ----------------

@router.get("/latest/{category}")
def get_latest_data(category: str, db: Session = Depends(get_db)):

    validate_category(category)

    UploadModel = CATEGORIES[category]["upload"]
    DataModel = CATEGORIES[category]["data"]

    latest_upload = (
        db.query(UploadModel)
        .order_by(UploadModel.data_date.desc())
        .first()
    )

    if not latest_upload:
        return {"latest_data_date": None, "records": [], "count": 0}

    rows = db.query(DataModel).filter(
        DataModel.group_id == latest_upload.group_id
    ).all()

    records = []

    for r in rows:
        row = r.__dict__.copy()
        row.pop("_sa_instance_state", None)
        records.append(row)

    return {
        "latest_data_date": latest_upload.data_date,
        "records": records,
        "count": len(records)
    }
@router.get("/count/ch_per/{category}")
def get_counts_by_ch_per(category: str, db: Session = Depends(get_db)):

    if category not in ["up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'up_down_mobile' or 'up_down_trend'"
        )

    UploadModel = CATEGORIES[category]["upload"]
    DataModel = CATEGORIES[category]["data"]

    latest_upload = (
        db.query(UploadModel)
        .order_by(UploadModel.data_date.desc())
        .first()
    )

    if not latest_upload:
        return {
            "latest_data_date": None,
            "total_count": 0,
            "up_count": 0,
            "down_count": 0
        }

    rows = db.query(DataModel).filter(
        DataModel.group_id == latest_upload.group_id
    ).all()

    # count based on CH_PER
    up_count = len([r for r in rows if getattr(r, "CH_PER", 0) > 0])
    down_count = len([r for r in rows if getattr(r, "CH_PER", 0) < 0])

    # assign meaningful labels
    if category == "up_down_mobile":
        up_label = "up_wardly_mobile"
        down_label = "downhillpath"
    else:
        up_label = "up_trend"
        down_label = "down_trend"

    return {
        "latest_data_date": latest_upload.data_date,
        "total_count": len(rows),
        up_label: up_count,
        down_label: down_count
    }
# ---------------- Download File ----------------

@router.get("/download/{category}/{group_id}")
def download_file(category: str, group_id: str, db: Session = Depends(get_db)):

    validate_category(category)

    UploadModel = CATEGORIES[category]["upload"]

    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={upload.file_name}"
        }
    )
@router.put("/upload/{category}/{group_id}")
async def update_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    if category not in ["mcap_movers", "up_down_mobile", "up_down_trend"]:
        raise HTTPException(
            400,
            "Category must be 'mcap_movers', 'up_down_mobile', or 'up_down_trend'"
        )

    # select models
    if category == "mcap_movers":
        DataModel = McapGainersLosers
        UploadModel = McapGainersLosersUpload
        expected_cols = 16
        columns = [
            "COMPANY","ISIN","CMP","MCAP_CR","CH_CR","CH_PER",
            "VOL_NOS","VOL_CH_PER","DAY_HIGH","DAY_LOW",
            "60DMA","60DMA_PER","245DMA","245DMA_PER","52WKH","52WKL"
        ]

    elif category == "up_down_mobile":
        DataModel = Upward_DownwardMobile
        UploadModel = Upward_DownwardMobileUpload
        expected_cols = 7
        columns = ["COMPANY","ISIN","CMP","START","DAYS","CH_PER","PERDAY"]

    else:
        DataModel = Up_DownTrend
        UploadModel = Up_DownTrendUpload
        expected_cols = 8
        columns = ["COMPANY","ISIN","CMP","5DMA","21DMA","60DMA","245DMA","CH_PER"]

    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # update metadata
    if upload_date:
        upload.upload_date = upload_date

    if data_date:
        upload.data_date = data_date

    if file:

        contents = await file.read()

        # delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # upload new file
        s3_key = upload_file_to_s3(io.BytesIO(contents), f"gainloss/{category}")

        upload.file_name = file.filename
        upload.file_path = s3_key

        # read dataframe
        try:
            if file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        if df.shape[1] != expected_cols:
            raise HTTPException(
                400,
                f"{category} file must have exactly {expected_cols} columns"
            )

        df.columns = columns

        # delete old records for this upload
        db.query(DataModel).filter(
            DataModel.group_id == group_id
        ).delete(synchronize_session=False)

        records = []

        for _, r in df.iterrows():

            if category == "mcap_movers":
                record = DataModel(
                    COMPANY=r["COMPANY"],
                    ISIN=r["ISIN"],
                    CMP=r["CMP"],
                    MCAP_CR=r["MCAP_CR"],
                    CH_CR=r["CH_CR"],
                    CH_PER=r["CH_PER"],
                    VOL_NOS=r["VOL_NOS"],
                    VOL_CH_PER=r["VOL_CH_PER"],
                    DAY_HIGH=r["DAY_HIGH"],
                    DAY_LOW=r["DAY_LOW"],
                    DMA_60=r["60DMA"],
                    DMA_PER_60=r["60DMA_PER"],
                    DMA_245=r["245DMA"],
                    DMA_PER_245=r["245DMA_PER"],
                    WKH_52=r["52WKH"],
                    WKL_52=r["52WKL"],
                    group_id=group_id
                )

            elif category == "up_down_mobile":
                record = DataModel(
                    COMPANY=r["COMPANY"],
                    ISIN=r["ISIN"],
                    CMP=r["CMP"],
                    START=r["START"],
                    DAYS=r["DAYS"],
                    CH_PER=r["CH_PER"],
                    PERDAY=r["PERDAY"],
                    group_id=group_id
                )

            else:
                record = DataModel(
                    COMPANY=r["COMPANY"],
                    ISIN=r["ISIN"],
                    CMP=r["CMP"],
                    DMA_5=r["5DMA"],
                    DMA_21=r["21DMA"],
                    DMA_60=r["60DMA"],
                    DMA_245=r["245DMA"],
                    CH_PER=r["CH_PER"],
                    group_id=group_id
                )

            records.append(record)

        db.bulk_save_objects(records)

    db.commit()

    return {
        "message": "Upload updated successfully",
        "group_id": group_id
    }
# ---------------- Delete Upload ----------------

@router.delete("/upload/{category}/{group_id}")
def delete_file_upload(
    category: str,
    group_id: str,
    db: Session = Depends(get_db)
):

    validate_category(category)

    DataModel = CATEGORIES[category]["data"]
    UploadModel = CATEGORIES[category]["upload"]

    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    db.query(DataModel).filter(
        DataModel.group_id == group_id
    ).delete(synchronize_session=False)

    delete_file_from_s3(upload.file_path)

    db.delete(upload)

    db.commit()

    return {"message": "Upload deleted successfully"}