from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import date

class PlanRequest(BaseModel):
    festival: str = Field(default="Goa Carnival", min_length=2, max_length=100)
    start_date: date
    days: int = Field(default=3, ge=1, le=10)
    travellers: int = Field(default=1, ge=1, le=20)
    budget_inr: float = Field(default=8000, gt=0, le=10000000)
    interests: list[str] = Field(default_factory=lambda: ["beaches", "heritage"])
    food_preferences: list[str] = Field(default_factory=lambda: ["Goan food"])
    travel_style: Literal["budget", "balanced", "comfortable"] = "balanced"
    accommodation: Literal["hostel", "budget hotel", "mid-range hotel", "already booked"] = "budget hotel"
    arrival_time: str = "10:00"
    departure_time: str = "18:00"

    @field_validator("interests", "food_preferences")
    @classmethod
    def cap_lists(cls, v):
        return v[:10]
