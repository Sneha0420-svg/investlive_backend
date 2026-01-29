from app.database import Base, engine
from app.models.marketind import StockData,MarketIndicatorUpload   # import your model modules here
from app.models.instocktrend import InstockTrendData,Indstocktrendupload
from app.models.mostvalued import Mostvalued,MostValuedupload
from app.models.heatmap import Upload,HeatMap
from app.models.ipo import DataUpload,IPOUpload
from app.models.volumetrade import VolumeTradevolume,VolumeTradevalue,VolumeTradetrade,VolumeTradeUpload
from app.models.ipoheatmap import IPOHeatmapYear,IPOHeatmapYearUpload,IPOHeatmapData,IPOHeatmapDataUpload

# Base.metadata.drop_all(bind=engine)
# This creates all tables based on your models
Base.metadata.create_all(bind=engine)

print("Database initialized successfully in PostgreSQL!")
