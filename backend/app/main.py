from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health

app = FastAPI(
    title="Portfolio Diversification API",
    version="0.1.0",
    description="API for analyzing portfolio diversification"
)

# CORS Config

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", #DEV Server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Registering the routers
app.include_router(health.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Portfolio Diversification API is running"}