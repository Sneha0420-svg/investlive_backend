import io
from datetime import date
from uuid import uuid4
import pandas as pd

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database import SessionLocal
from app.models.indstocksnapshot_graph import IndStockGraph, IndStockGraphUpload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3

router = APIRouter(prefix="/indstockgraph", tags=["IndStock Graph"])

# ---------------- DB ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- UPLOAD ----------------
@router.post("/upload")
async def upload_file(
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    group_id = str(uuid4())

    try:
        contents = await file.read()
        file_like = io.BytesIO(contents)

        # Upload to S3
        s3_folder = "indstockgraphgraph"
        s3_key = upload_file_to_s3(
            file_obj=file_like,
            folder=s3_folder,
            filename=file.filename
        )

        # Read file again
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
        df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"], errors="coerce").dt.date

        if df.empty:
            raise HTTPException(400, "Uploaded file is empty")

        # 🔥🔥🔥 DELETE ALL OLD DATA
        db.query(IndStockGraph).delete(synchronize_session=False)

        # Prepare records
        records = [
            IndStockGraph(
                TRN_DATE=r["TRN_DATE"],
                STKS_TRD=int(r["STKS_TRD"]) if r["STKS_TRD"] else 0,
                ADV=int(r["ADV"]) if r["ADV"] else 0,
                DECL=int(r["DECL"]) if r["DECL"] else 0,
                UNCHG=int(r["UNCHG"]) if r["UNCHG"] else 0,
            )
            for _, r in df.iterrows()
        ]

        upload_row = IndStockGraphUpload(
            group_id=group_id,
            upload_date=upload_date,
            data_date=data_date,
            data_type="IndStockGraph",
            file_name=file.filename,
            file_path=s3_key
        )

        db.add(upload_row)
        db.bulk_save_objects(records)
        db.commit()

        return {
            "message": "Old data deleted and new data inserted",
            "group_id": group_id,
            "records": len(records)
        }

    except Exception as e:
        db.rollback()
        delete_file_from_s3(s3_key)
        raise HTTPException(500, f"Error: {str(e)}")

# ---------------- UPLOAD LIST ----------------
@router.get("/uploads")
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IndStockGraphUpload).order_by(
        IndStockGraphUpload.upload_date.desc()
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


# ---------------- LATEST DATA ----------------
@router.get("/latest")
def get_latest(db: Session = Depends(get_db)):
    rows = db.query(IndStockGraph).all()

    return {
        "records": [
            {
                "ID": r.ID,
                "TRN_DATE": r.TRN_DATE,
                "STKS_TRD": r.STKS_TRD,
                "ADV": r.ADV,
                "DECL": r.DECL,
                "UNCHG": r.UNCHG,
            }
            for r in rows
        ]
    }


# ---------------- LATEST BY DATE ----------------
@router.get("/latest-from-graph")
def latest_by_date(db: Session = Depends(get_db)):

    latest_date = db.query(IndStockGraph.TRN_DATE)\
        .order_by(IndStockGraph.TRN_DATE.desc())\
        .first()

    if not latest_date or not latest_date[0]:
        raise HTTPException(404, "No data found")

    rows = db.query(IndStockGraph)\
        .filter(IndStockGraph.TRN_DATE == latest_date[0])\
        .all()

    return {
        "latest_date": latest_date[0],
        "records": [
            {
                "ID": r.ID,
                "TRN_DATE": r.TRN_DATE,
                "STKS_TRD": r.STKS_TRD,
                "ADV": r.ADV,
                "DECL": r.DECL,
                "UNCHG": r.UNCHG,
            }
            for r in rows
        ]
    }


# ---------------- DOWNLOAD ----------------
@router.get("/download/{group_id}")
def download_file(group_id: str, db: Session = Depends(get_db)):

    upload = db.query(IndStockGraphUpload).filter_by(group_id=group_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    if not file_stream:
        raise HTTPException(404, "File not found")

    filename = quote(upload.file_name)

    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ---------------- UPDATE ----------------
@router.put("/upload/{group_id}")
async def update_upload(
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    upload = db.query(IndStockGraphUpload)\
        .filter_by(group_id=group_id)\
        .first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:

        delete_file_from_s3(upload.file_path)

        contents = await file.read()
        file_like = io.BytesIO(contents)

        s3_key = upload_file_to_s3(
            file_obj=file_like,
            folder="indstockgraph",
            filename=file.filename
        )

        upload.file_name = file.filename
        upload.file_path = s3_key

        db.query(IndStockGraph)\
            .delete(synchronize_session=False)

        file_like.seek(0)

        if file.filename.endswith(".csv"):
            df = pd.read_csv(file_like, header=None)
        else:
            df = pd.read_excel(file_like, header=None)

        df.columns = ["ID", "TRN_DATE", "STKS_TRD", "ADV", "DECL", "UNCHG"]
        df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"], errors="coerce").dt.date

        records = [
            IndStockGraph(
                TRN_DATE=r["TRN_DATE"],
                STKS_TRD=int(r["STKS_TRD"] or 0),
                ADV=int(r["ADV"] or 0),
                DECL=int(r["DECL"] or 0),
                UNCHG=int(r["UNCHG"] or 0),
            )
            for _, r in df.iterrows()
        ]

        db.bulk_save_objects(records)

    db.commit()

    return {"message": "Updated successfully", "group_id": group_id}


# ---------------- DELETE ----------------
@router.delete("/upload/{group_id}")
def delete_upload(group_id: str, db: Session = Depends(get_db)):

    upload = db.query(IndStockGraphUpload)\
        .filter_by(group_id=group_id)\
        .first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    db.query(IndStockGraph)\
        .delete(synchronize_session=False)

    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Deleted successfully"}