from sqlalchemy import Column, Integer, String, Date
from app.database import Base


class IPOEvents(Base):
    __tablename__ = 'ipo_events'

    SCRIP = Column(String(20), nullable=False)
    ISS_OPEN = Column(Date, nullable=True)
    SHEDULE_CLOSE = Column(Date, nullable=True)
    LATE_CLOSE = Column(Date, nullable=True)
    ALLOTMENT = Column(Date, nullable=True)
    REFUND = Column(Date, nullable=True)
    DEMAT = Column(Date, nullable=True)
    TRADING = Column(Date, nullable=True)
    DP_DATE = Column(Date, nullable=True)
    FP_DATE = Column(Date, nullable=True)
    DRHP_DATE = Column(Date, nullable=True)
    RHP_DATE = Column(Date, nullable=True)
    PROS_DATE = Column(Date, nullable=True)
    ID = Column(Integer, primary_key=True, nullable=False)


    def __repr__(self):
        return f"<IPOEvents(SCRIP='{self.SCRIP}', ISS_OPEN='{self.ISS_OPEN}')>"

class IPOEventsUpload(Base):
    __tablename__ = "ipo_events_uploads"

    id = Column(Integer, primary_key=True, index=True)

    mkt_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL  