from typing import List, Optional

from pydantic import BaseModel, Field

from .common_model import Attraction, Dining, Hotel, Location, Weather


class TripPlanRequest(BaseModel):
    """Trip planning request payload."""

    destination: str = Field(..., description="Destination city", example="Beijing")
    start_date: str = Field(..., description="Start date", example="2024-10-01")
    end_date: str = Field(..., description="End date", example="2024-10-03")
    preferences: List[str] = Field(default_factory=list, description="Travel preferences")
    hotel_preferences: List[str] = Field(default_factory=list, description="Hotel preferences")
    budget: str = Field("medium", description="Budget level")


class BudgetBreakdown(BaseModel):
    """Whole-trip budget breakdown."""

    transport_cost: float = Field(0.0)
    dining_cost: float = Field(0.0)
    hotel_cost: float = Field(0.0)
    attraction_ticket_cost: float = Field(0.0)
    total: float = Field(0.0)


class DailyBudget(BaseModel):
    """Single-day budget breakdown."""

    transport_cost: float = Field(0.0)
    dining_cost: float = Field(0.0)
    hotel_cost: float = Field(0.0)
    attraction_ticket_cost: float = Field(0.0)
    total: float = Field(0.0)


class DailyPlan(BaseModel):
    """Daily trip plan."""

    day: int
    theme: str = ""
    weather: Optional[Weather] = None
    recommended_hotel: Optional[Hotel] = None
    attractions: List[Attraction] = Field(default_factory=list)
    dinings: List[Dining] = Field(default_factory=list)
    budget: DailyBudget = Field(default_factory=DailyBudget)


class TripPlanResponse(BaseModel):
    """Trip planning response payload."""

    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[int] = 1
    city_support_level: Optional[str] = None
    city_support_message: Optional[str] = None
    trip_title: str
    total_budget: BudgetBreakdown
    hotels: List[Hotel] = Field(default_factory=list)
    days: List[DailyPlan]


class TripTaskResponse(BaseModel):
    """Asynchronous trip planning task status."""

    task_id: str
    status: str
    progress: int
    message: str
    result_trip_id: Optional[str] = None
    error: Optional[str] = None
    city_support_level: Optional[str] = None
    city_support_message: Optional[str] = None
    updated_at: Optional[str] = None


class TripVersionItem(BaseModel):
    """Trip version history entry."""

    version: int
    snapshot_at: str
    trip_title: str


class TripVersionsResponse(BaseModel):
    """Trip version history response."""

    trip_id: str
    versions: List[TripVersionItem] = Field(default_factory=list)


class CitySupportResponse(BaseModel):
    """City support capability response."""

    city: str
    level: str
    message: str


class CityListResponse(BaseModel):
    """Supported cities response."""

    count: int
    cities: List[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    """Simple operation result."""

    message: str
