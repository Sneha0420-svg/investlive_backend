from sqlalchemy import Column, Integer, Date
from app.database import Base

class InstockTrendCount(Base):
    __tablename__ = "indstocktrend_count"

    id = Column(Integer, primary_key=True, index=True)

    stocks = Column(Integer)
    advances = Column(Integer)
    declines = Column(Integer)
    unchanged = Column(Integer)

    upper_circuit = Column(Integer)
    lower_circuit = Column(Integer)

    week_52_high = Column("52_week_high", Integer)
    week_52_low = Column("52_week_low", Integer)

    multiyear_high = Column(Integer)
    multiyear_low = Column(Integer)

    uptrend = Column(Integer)
    downtrend = Column(Integer)

    upwardly_mobile = Column("Upwardly_Mobile", Integer)
    on_downhill_path = Column("On_Downhill_Path", Integer)

    mkt_date = Column(Date, nullable=False)