from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class PortfolioHoldingInput(BaseModel):
    ticker: str = Field(min_length=1, description="Ticker symbol")
    amount: Optional[float] = Field(default=None, ge=0, description="Dollar amount in position")
    weight: Optional[float] = Field(default=None, ge=0, description="Portfolio weight (0 to 1)")

    @model_validator(mode="after")
    def validate_amount_or_weight(self):
        if self.amount is None and self.weight is None:
            raise ValueError("Each holding must include either amount or weight")
        return self


class PortfolioAnalyzeRequest(BaseModel):
    holdings: List[PortfolioHoldingInput] = Field(min_length=1)


class PortfolioOptimizeRequest(BaseModel):
    holdings: List[PortfolioHoldingInput] = Field(min_length=1)
    max_changes: int = Field(default=5, ge=1, le=20)
    transaction_cost_rate: float = Field(default=0.0015, ge=0, le=0.05)
    include_sp500_additions: bool = True
    include_etfs: bool = True
    candidate_limit: int = Field(default=120, ge=20, le=500)
    random_portfolios: int = Field(default=3500, ge=500, le=15000)


class PortfolioProjectRequest(BaseModel):
    holdings: List[PortfolioHoldingInput] = Field(min_length=1)
    horizon_months: int = Field(default=12, ge=1, le=36)
    simulations: int = Field(default=3000, ge=500, le=20000)


class PortfolioTargetWeightInput(BaseModel):
    ticker: str = Field(min_length=1, description="Ticker symbol")
    weight: float = Field(ge=0, description="Target portfolio weight (0 to 1)")


class PortfolioCompareHistoryRequest(BaseModel):
    holdings: List[PortfolioHoldingInput] = Field(min_length=1)
    optimized_weights: Optional[List[PortfolioTargetWeightInput]] = None
    lookback_days: int = Field(default=504, ge=30, le=2000)
    include_benchmark: bool = True
