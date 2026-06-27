from pydantic import BaseModel, Field


class PayrollGenerationRequest(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)

