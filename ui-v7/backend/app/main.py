from fastapi import FastAPI
app = FastAPI()
from .api.timeline import router as timeline_router
from .api.photos import router as photos_router
from .api.pairs import router as pairs_router
from .api.calibration import router as calibration_router

app.include_router(timeline_router)
app.include_router(photos_router)
app.include_router(pairs_router)
app.include_router(calibration_router)
