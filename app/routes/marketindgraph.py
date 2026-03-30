# app/routes/mktgraph.py

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException,Query
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import insert
from datetime import datetime
import csv

from app.models.marketindgraph import MktGraph, MktGraphUploads
from app.database import SessionLocal

router = APIRouter(prefix="/mktgraph", tags=["MktGraph"])

# ----------------------
# DB Dependency
# ----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload")
def upload_mktgraph(
    files: list[UploadFile] = File(...),
    mrk_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    total_records_attempted = 0
    total_records_inserted = 0
    errors = []

    # Optional: clear existing data (comment if you want incremental uploads)
    # db.query(MktGraph).delete(synchronize_session=False)
    # db.commit()

    for file in files:
        if not file.filename.lower().endswith(".csv"):
            errors.append(f"{file.filename} is not a CSV file")
            continue

        try:
            content = file.file.read().decode("utf-8-sig").splitlines()
            if not content:
                errors.append(f"{file.filename} is empty")
                continue

            reader = csv.reader(content)
            rows_to_insert = []
            for row in reader:
                if not row or len(row) < 7:
                    errors.append(f"Invalid row in {file.filename}: {row}")
                    continue
                try:
                    scrip = row[0].strip()
                    pr_date = datetime.strptime(row[1].strip(), "%Y-%m-%d").date()
                    cur_ch = float(row[2].strip())
                    dma5 = float(row[3].strip())
                    dma21 = float(row[4].strip())
                    dma60 = float(row[5].strip())
                    dma245 = float(row[6].strip())
                    idx_id = int(row[7].strip()) if len(row) > 7 and row[7].strip() else 0

                    rows_to_insert.append({
                        "SCRIP": scrip,
                        "PR_DATE": pr_date,
                        "CUR_CH": cur_ch,
                        "DMA5": dma5,
                        "DMA21": dma21,
                        "DMA60": dma60,
                        "DMA245": dma245,
                        "IDX_ID": idx_id
                    })
                    total_records_attempted += 1

                except Exception as e:
                    errors.append(f"Error parsing row in {file.filename}: {row} -> {e}")

            # Use PostgreSQL "ON CONFLICT DO NOTHING" to skip duplicates
            if rows_to_insert:
                stmt = insert(MktGraph).values(rows_to_insert)
                stmt = stmt.on_conflict_do_nothing(index_elements=["SCRIP", "PR_DATE"])
                result = db.execute(stmt)
                total_records_inserted += result.rowcount

        except Exception as e:
            errors.append(f"Failed to process {file.filename}: {e}")

    db.commit()

    # Log upload
    upload_log = MktGraphUploads(
        filename=", ".join([f.filename for f in files]),
        mrk_date=mrk_date,
        upload_time=datetime.now(),
        total_records=total_records_inserted,
        errors=len(errors)
    )
    db.add(upload_log)
    db.commit()

    return {
        "files_uploaded": len(files),
        "total_records_attempted": total_records_attempted,
        "total_records_inserted": total_records_inserted,
        "errors": errors
    }

@router.get("/uploads")
def get_upload_logs(db: Session = Depends(get_db)):
    logs = db.query(MktGraphUploads).order_by(MktGraphUploads.upload_time.desc()).all()
    return [
        {
            "id": l.id,
            "filename": l.filename,
            "upload_time": l.upload_time.isoformat(),
            "mrk_date": l.mrk_date.isoformat(),
            "total_records": l.total_records,
            "errors": l.errors
        }
        for l in logs
    ]
# ----------------------
# Get all market graph data (with pagination)
# ----------------------
@router.get("/all")
def get_all_mktgraph(
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Returns all records from mkt_graph table with pagination.
    """
    data = (
        db.query(MktGraph)
        .order_by(MktGraph.PR_DATE.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "SCRIP": d.SCRIP,
            "PR_DATE": d.PR_DATE.isoformat() if d.PR_DATE else None,
            "CUR_CH": float(d.CUR_CH) if d.CUR_CH else None,
            "DMA5": float(d.DMA5) if d.DMA5 else None,
            "DMA21": float(d.DMA21) if d.DMA21 else None,
            "DMA60": float(d.DMA60) if d.DMA60 else None,
            "DMA245": float(d.DMA245) if d.DMA245 else None,
            "IDX_ID": d.IDX_ID,
        }
        for d in data
    ]   
    
    

# ----------------------
# Get all market graph data by IDX_ID
# ----------------------
@router.get("/by-idx")
def get_mktgraph_by_idx(
    idx_id: int = Query(..., description="Index ID to filter data"),
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Returns all records from mkt_graph filtered by IDX_ID with pagination.
    """
    data = (
        db.query(MktGraph)
        .filter(MktGraph.IDX_ID == idx_id)
        .order_by(MktGraph.PR_DATE.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not data:
        raise HTTPException(status_code=404, detail=f"No data found for IDX_ID {idx_id}")

    return [
        {
            "SCRIP": d.SCRIP,
            "PR_DATE": d.PR_DATE.isoformat() if d.PR_DATE else None,
            "CUR_CH": float(d.CUR_CH) if d.CUR_CH else None,
            "DMA5": float(d.DMA5) if d.DMA5 else None,
            "DMA21": float(d.DMA21) if d.DMA21 else None,
            "DMA60": float(d.DMA60) if d.DMA60 else None,
            "DMA245": float(d.DMA245) if d.DMA245 else None,
            "IDX_ID": d.IDX_ID,
        }
        for d in data
    ]
# Delete an upload log by ID
@router.delete("/uploads/{upload_id}")
def delete_upload_log(upload_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific upload log from mkt_graph_uploads by its ID
    """
    # Check if upload exists
    upload = db.query(MktGraphUploads).filter(MktGraphUploads.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail=f"Upload log with ID {upload_id} not found")

    try:
        db.delete(upload)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete upload log: {e}")

    return {"message": f"Upload log with ID {upload_id} deleted successfully"}