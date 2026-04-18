from typing import Any, Dict, List

from pydantic import BaseModel, Field


class PortfolioApiResponse(BaseModel):
    data: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
