from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import date
import shutil
import os
import pandas as pd
from fastapi.responses import FileResponse

from app.models.heatmap import Upload as UploadModel, HeatMap as HeatMapModel
from app.schemas.heatmap import UploadOut, HeatMapOut
from app.database import SessionLocal

router = APIRouter(
    prefix="/Heatmap",
    tags=["Heatmap"]
)

UPLOAD_DIR = "uploads\heatmap"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- UPLOAD FILE AND SAVE -----------------
@router.post("/file/", response_model=UploadOut)
async def upload_file(
    uploading_date: date = Form(...),
    data_date: date = Form(...),
    value: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filename = file.filename
        file_path = os.path.join(UPLOAD_DIR,filename)

        # Save uploaded file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Create Upload record
        db_upload = UploadModel(
            uploading_date=uploading_date,
            data_date=data_date,
            value=value,
            filename=filename,
            file_path=file_path
        )
        db.add(db_upload)
        db.commit()
        db.refresh(db_upload)


        # Read CSV or Excel (no header)
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None, engine="openpyxl")

        # Select columns: 0 (rank) + from 3rd index to end (4th column onwards)
        cols_to_keep = [0] + list(range(4, df.shape[1]))
        df = df.iloc[:, cols_to_keep]

        # Assign your column names accordingly (since you removed 2nd and 3rd columns)
        df.columns = [
            "rank",
            "name", "cos", "mcap", "daych", "daychper", "ffltmcap", "ffltrank",
            "wkch", "wkchper", "mthch", "mthchper", "qtrch", "qtrchper",
            "hrch", "hrchper", "yrch", "yrchper"
        ]


        # Insert HeatMap rows
        for _, row in df.iterrows():
            db_heat = HeatMapModel(
                upload_id=db_upload.id,
                rank=int(row["rank"]),
                name=str(row["name"]),
                cos=int(row["cos"]) if pd.notnull(row["cos"]) else None,
                mcap=int(row["mcap"]) if pd.notnull(row["mcap"]) else None,
                daych=int(row["daych"]) if pd.notnull(row["daych"]) else None,
                daychper=float(row["daychper"]) if pd.notnull(row["daychper"]) else None,
                ffltmcap=int(row["ffltmcap"]) if pd.notnull(row["ffltmcap"]) else None,
                ffltrank=int(row["ffltrank"]) if pd.notnull(row["ffltrank"]) else None,
                wkch=int(row["wkch"]) if pd.notnull(row["wkch"]) else None,
                wkchper=float(row["wkchper"]) if pd.notnull(row["wkchper"]) else None,
                mthch=int(row["mthch"]) if pd.notnull(row["mthch"]) else None,
                mthchper=float(row["mthchper"]) if pd.notnull(row["mthchper"]) else None,
                qtrch=int(row["qtrch"]) if pd.notnull(row["qtrch"]) else None,
                qtrchper=float(row["qtrchper"]) if pd.notnull(row["qtrchper"]) else None,
                hrch=int(row["hrch"]) if pd.notnull(row["hrch"]) else None,
                hrchper=float(row["hrchper"]) if pd.notnull(row["hrchper"]) else None,
                yrch=int(row["yrch"]) if pd.notnull(row["yrch"]) else None,
                yrchper=float(row["yrchper"]) if pd.notnull(row["yrchper"]) else None
            )
            db.add(db_heat)

        db.commit()
        db.refresh(db_upload)

        return db_upload

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- GET ALL UPLOADS -----------------
@router.get("/", response_model=List[UploadOut])
def get_uploads(db: Session = Depends(get_db)):
    return db.query(UploadModel).all()
# ----------------- DOWNLOAD FILE -----------------
@router.get("/download/{upload_id}")
def download_heatmap_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = upload.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=file_path, filename=upload.filename, media_type='application/octet-stream')


# ----------------- GET SINGLE UPLOAD -----------------
@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload

# ----------------- GET LATEST HEATMAP DATA -----------------
@router.get("/latest", response_model=List[HeatMapOut])
def get_latest_heatmap_data(
    value: str = None,  # Optional filter by Company/House/IndSegment
    db: Session = Depends(get_db)
):
    query = db.query(UploadModel)
    if value:
        query = query.filter(UploadModel.value == value)
    
    latest_upload = query.order_by(desc(UploadModel.data_date)).first()
    
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No heatmap data found")
    
    heatmap_data = db.query(HeatMapModel).filter(HeatMapModel.upload_id == latest_upload.id).all()
    
    return heatmap_data

# ----------------- DELETE UPLOAD -----------------
@router.delete("/{upload_id}", response_model=dict)
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if os.path.exists(upload.filename):
        os.remove(upload.filename)

    db.delete(upload)
    db.commit()
    return {"detail": "Upload deleted"}
