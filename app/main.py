from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth import router as auth_router
from app.routes.marketind import router as marketind_router
from app.routes.marketindgraph import router as marketindgraph_router
from app.routes.instocktrend import router as indstocktrend_router
from app.routes.mostvalued import router as mostvaluedhouse_router
from app.routes.volumetrade import router as volumetrade_router 
from app.routes.ipo import router as ipo_router
from app.routes.ipoheatmap import router as ipo_heatmap_router
from app.routes.news import router as news_router
from app.routes.announcement import router as announcement_router
from app.routes.stockpulse import router as stockpulse_router
from app.routes.heatmap import router as heatmap_router
from app.routes.corpdiary import router as corpdiary_router
from app.routes.newhighlow import router as newhighlow_router
from app.routes.mcapgainerloser import router as mcapgainerloser_router
from app.routes.indstocksnapshot_graph import router as indstockgraph_router
from app.routes.managerrank import router as managerrank_router
from app.routes.mostvaluedcharts import router as mostvaluedcharts_router
from app.routes.pricemoving import router as pricemoving_router
from app.routes.volumemoving import router as volumemoving_router
from fastapi.staticfiles import StaticFiles
import os
app = FastAPI(
    title="Investlive API's",
    version="1.0.0"
)
os.makedirs("uploads/news", exist_ok=True)

# Serve the uploads folder
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# Allow CORS
origins = [
    "http://localhost:3000",  # your React frontend
    # You can add other domains here if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # or ["*"] to allow all (not recommended in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Backend run successfully"}
app.include_router(auth_router)
app.include_router(news_router)
app.include_router(announcement_router)
app.include_router(marketind_router)
app.include_router(marketindgraph_router)
app.include_router(stockpulse_router)
app.include_router(indstocktrend_router)
app.include_router(indstockgraph_router)
app.include_router(mostvaluedhouse_router)
app.include_router(mostvaluedcharts_router)
app.include_router(newhighlow_router)
app.include_router(mcapgainerloser_router)
app.include_router(volumetrade_router)
app.include_router(heatmap_router)
app.include_router(ipo_router)
app.include_router(ipo_heatmap_router)
app.include_router(managerrank_router)
app.include_router(corpdiary_router)
app.include_router(pricemoving_router)
app.include_router(volumemoving_router)