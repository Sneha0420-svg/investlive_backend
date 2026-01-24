from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.marketind import router as marketind_router
from app.routes.instocktrend import router as indstocktrend_router
from app.routes.mostvalued import router as mostvaluedhouse_router
from app.routes.ipoevents import router as ipo_events_router 
from app.routes.heatmap import router as heatmap_router

app = FastAPI(
    title="Investlive API's",
   
)

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

app.include_router(marketind_router)
app.include_router(indstocktrend_router)
app.include_router(mostvaluedhouse_router)
app.include_router(ipo_events_router)
app.include_router(heatmap_router)
