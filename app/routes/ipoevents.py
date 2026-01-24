from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import SessionLocal
from app.models.ipoevents import IpoEvent
from app.schemas.ipoevents import IpoEventCreate,IpoEventResponse,IpoEventBase,IpoEventUpdate

router = APIRouter(prefix="/ipo-events", tags=["IPO Events"])
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ➕ Create IPO Event
@router.post("/", response_model=IpoEventResponse)
def create_ipo_event(
    data:IpoEventCreate,
    db: Session = Depends(get_db)
):
    ipo_event = IpoEvent(**data.dict())
    db.add(ipo_event)
    db.commit()
    db.refresh(ipo_event)
    return ipo_event


# 📄 Get all IPO Events
@router.get("/", response_model=List[IpoEventResponse])
def get_ipo_events(db: Session = Depends(get_db)):
    return db.query(IpoEvent).order_by(IpoEvent.event_date).all()


# ✏️ Update IPO Event
@router.put("/{event_id}", response_model=IpoEventResponse)
def update_ipo_event(
    event_id: int,
    data: IpoEventUpdate,
    db: Session = Depends(get_db)
):
    ipo_event = db.query(IpoEvent).filter(IpoEvent.id == event_id).first()

    if not ipo_event:
        raise HTTPException(status_code=404, detail="IPO Event not found")

    for key, value in data.dict().items():
        setattr(ipo_event, key, value)

    db.commit()
    db.refresh(ipo_event)
    return ipo_event


# ❌ Delete IPO Event
@router.delete("/{event_id}")
def delete_ipo_event(event_id: int, db: Session = Depends(get_db)):
    ipo_event = db.query(IpoEvent).filter(IpoEvent.id == event_id).first()

    if not ipo_event:
        raise HTTPException(status_code=404, detail="IPO Event not found")

    db.delete(ipo_event)
    db.commit()
    return {"message": "IPO Event deleted successfully"}
