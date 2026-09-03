# 行程规划，含同步/异步/版本回滚
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_trip_service
from app.middleware.auth import get_user_id
from app.models.trip_model import (
    CityListResponse,
    CitySupportResponse,
    MessageResponse,
    TripPlanRequest,
    TripPlanResponse,
    TripTaskResponse,
    TripVersionsResponse,
)
from app.services.city_service import city_support_service
from app.services.trip_service import TripService

router = APIRouter()


@router.post("/plan", response_model=TripPlanResponse)
def plan_trip(
    request: TripPlanRequest,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.plan_trip(request=request, user_id=get_user_id(http_request))


@router.post("/plan-async", response_model=TripTaskResponse)
def plan_trip_async(
    request: TripPlanRequest,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.create_trip_task(request=request, user_id=get_user_id(http_request))


@router.get("/tasks/{task_id}", response_model=TripTaskResponse)
def get_trip_task(
    task_id: str,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.get_trip_task(task_id=task_id, user_id=get_user_id(http_request))


@router.get("/list", response_model=List[TripPlanResponse])
def get_trip_list(
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.list_trips(user_id=get_user_id(http_request))


@router.get("/city-support", response_model=CityListResponse)
def list_city_support():
    cities = city_support_service.list_cities()
    city_names = list(cities.keys()) if isinstance(cities, dict) else list(cities)
    return CityListResponse(count=len(city_names), cities=city_names)


@router.get("/city-support/{city}", response_model=CitySupportResponse)
def get_city_support(city: str):
    support = city_support_service.get_city_support_info(city)
    return CitySupportResponse(
        city=city,
        level=support.get("level", "unknown"),
        message=support.get("message", ""),
    )


@router.get("/{trip_id}", response_model=TripPlanResponse)
def get_trip(
    trip_id: str,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.get_trip(trip_id=trip_id, user_id=get_user_id(http_request))


@router.delete("/{trip_id}", response_model=MessageResponse)
def delete_trip(
    trip_id: str,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.delete_trip(trip_id=trip_id, user_id=get_user_id(http_request))


@router.put("/{trip_id}", response_model=TripPlanResponse)
def update_trip(
    trip_id: str,
    request: TripPlanResponse,
    http_request: Request,
    if_match_version: Optional[int] = Header(default=None, alias="If-Match-Version"),
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.update_trip(
        trip_id=trip_id,
        user_id=get_user_id(http_request),
        request=request,
        if_match_version=if_match_version,
    )


@router.get("/{trip_id}/versions", response_model=TripVersionsResponse)
def get_trip_versions(
    trip_id: str,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.list_trip_versions(trip_id=trip_id, user_id=get_user_id(http_request))


@router.post("/{trip_id}/rollback", response_model=TripPlanResponse)
def rollback_trip(
    trip_id: str,
    target_version: int,
    http_request: Request,
    trip_service: TripService = Depends(get_trip_service),
):
    return trip_service.rollback_trip(
        trip_id=trip_id,
        user_id=get_user_id(http_request),
        target_version=target_version,
    )
