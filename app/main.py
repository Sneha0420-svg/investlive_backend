from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.staticfiles import StaticFiles
import secrets
import os

# =========================
# IMPORT ROUTERS
# =========================
from app.routes.auth import router as auth_router
from app.routes.ads import router as ads_router
from app.routes.marketdate import router as marketdate_router
from app.routes.marketind import router as marketind_router
from app.routes.marketindgraph import router as marketindgraph_router
from app.routes.instocktrend import router as indstocktrend_router
from app.routes.mostvalued import router as mostvaluedhouse_router
from app.routes.volumetrade import router as volumetrade_router 
from app.routes.ipo import router as ipo_router
from app.routes.ipoevents import router as ipo_events_router
from app.routes.snapshot import router as snapshot_router
from app.routes.curtainraiser import router as curtaonraiser_router
from app.routes.primarymusings import router as primarymusings_router
from app.routes.reit import router as reit_router
from app.routes.ipoheatmap import router as ipo_heatmap_router
from app.routes.news import router as news_router
from app.routes.announcement import router as announcement_router
from app.routes.stockpulse import router as stockpulse_router
from app.routes.marketpulse import router as marketpulse_route
from app.routes.stocktrack import router as stocktrack_router
from app.routes.heatmap import router as heatmap_router
from app.routes.portfolio import router as stocks_movement_router
from app.routes.corpdiary import router as corpdiary_router
from app.routes.newhighlow import router as newhighlow_router
from app.routes.mcapgainerloser import router as mcapgainerloser_router
from app.routes.indstocksnapshot_graph import router as indstockgraph_router
from app.routes.managerrank import router as managerrank_router
from app.routes.mostvaluedcharts import router as mostvaluedcharts_router
from app.routes.pricemoving import router as pricemoving_router
from app.routes.volumemoving import router as volumemoving_router

# =========================
# APP INIT (DISABLE DEFAULT DOCS)
# =========================
app = FastAPI(
    title="Investlive API's",
    version="1.0.0",
    docs_url=None,          # disable default docs
    redoc_url=None,         # disable default redoc
    openapi_url="/openapi.json",
    root_path="/api"
)

# =========================
# STATIC FILES
# =========================
os.makedirs("uploads/news", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# BASIC AUTH FOR DOCS
# =========================
security = HTTPBasic()

DOCS_USERNAME = os.getenv("DOCS_USERNAME", "invest")
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "investlive.in")


def verify_docs(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, DOCS_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

# =========================
# PROTECTED DOCS
# =========================
@app.get("/docs", include_in_schema=False)
def custom_swagger_ui(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",  # ✅ important (match nginx path)
        title="Investlive API Docs"
    )

@app.get("/redoc", include_in_schema=False)
def custom_redoc(credentials: HTTPBasicCredentials = Depends(verify_docs)):
    return get_redoc_html(
        openapi_url="/api/openapi.json",  # ✅ important (match nginx path)
        
        title="Investlive ReDoc"
    )

# =========================
# ROOT
# =========================
@app.get("/")
def read_root():
    return {"message": "Backend run successfully"}

# =========================
# ROUTERS
# =========================
app.include_router(auth_router)
app.include_router(ads_router)
app.include_router(marketdate_router)
app.include_router(news_router)
app.include_router(announcement_router)
app.include_router(marketind_router)
app.include_router(marketindgraph_router)
app.include_router(stockpulse_router)
app.include_router(marketpulse_route)
app.include_router(stocktrack_router)
app.include_router(indstocktrend_router)
app.include_router(indstockgraph_router)
app.include_router(mostvaluedhouse_router)
app.include_router(mostvaluedcharts_router)
app.include_router(newhighlow_router)
app.include_router(mcapgainerloser_router)
app.include_router(volumetrade_router)
app.include_router(heatmap_router)
app.include_router(stocks_movement_router)
app.include_router(ipo_router)
app.include_router(ipo_events_router)
app.include_router(snapshot_router)
app.include_router(curtaonraiser_router)
app.include_router(primarymusings_router)
app.include_router(reit_router)
app.include_router(ipo_heatmap_router)
app.include_router(managerrank_router)
app.include_router(corpdiary_router)
app.include_router(pricemoving_router)
app.include_router(volumemoving_router)