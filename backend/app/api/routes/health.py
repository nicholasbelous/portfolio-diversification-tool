import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check endpoint - confirms API is running properly"""
    logger.debug("Health check requested")
    return {"status": "healthy"}