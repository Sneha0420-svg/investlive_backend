from app.database import Base, engine
from app.models.marketind import StockData,MarketIndicatorUpload 
from app.models.marketindgraph import MktGraph, MktGraphUploads
from app.models.auth import User
from app.models.instocktrend import InstockTrendData,Indstocktrendupload
from app.models.mostvalued import Mostvalued,MostValuedupload
from app.models.ipo import DataUpload,IPOUpload
from app.models.snapshot import Snapshot
from app.models.curtainraiser import CurtainRaiser
from app.models.primarymusings import PrimaryMusings
from app.models.volumetrade import VolumeTradevolume,VolumeTradevalue,VolumeTradetrade,VolumeTradeUpload
from app.models.ipoheatmap import IPOHeatmapYear,IPOHeatmapYearUpload,IPOHeatmapData,IPOHeatmapDataUpload
from app.models.news import News
from app.models.announcement import Announcement
from app.models.stockpulse import StockPulseData, StockPulseUpload
from app.models.heatmap import Company,House,Industry,Sector,CompanyUpload,HouseUpload,IndustryUpload,SectorUpload
from app.models.corpdiary import Bonus,BonusUpload,Split,SplitUpload,Div,DivUpload
from app.models.newhighlow import FiftyTwoWeekHighLow, MultiYearHighLow
from app.models.mcapgainerloser import (
    McapGainersLosers,
    McapGainersLosersUpload,
   Upward_DownwardMobile,
   Upward_DownwardMobileUpload,
   Up_DownTrend,
    Up_DownTrendUpload
)
from app.models.indstocksnapshot_graph import (
    IndStockGraph,
    IndStockGraphUpload
)
from app.models.managerrank import (
    LMRank,
    LMRankUpload,
    LMSub,
    LMSubUpload
)
from app.models.mostvaluedcharts import (
    MostValCompanyChart,
    MostValCompanyChartUpload,
    MostValHouseChart,
    MostValHouseChartUpload
)

from app.models.pricemoving import PriceMoving
from app.models.volumemoving import VolumeMoving


# Base.metadata.drop_all(bind=engine)
# This creates all tables based on your models
Base.metadata.create_all(bind=engine)

print("Database initialized successfully in PostgreSQL!")
