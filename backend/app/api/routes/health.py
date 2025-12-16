from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """
    Docstring for health_check
    Health Chech Endpoint
    Checking if the API is running properly
    """
    
    return {"status": "healthy"}