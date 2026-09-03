from __future__ import annotations

from datetime import datetime
from threading import Lock, Thread
from typing import Any, Callable, Dict, Optional
import uuid
import json

from fastapi import HTTPException

from app.agents.planner import PlannerAgent
from app.config import settings
from app.exceptions.custom_exceptions import BusinessException
from app.exceptions.error_codes import ErrorCode
from app.models.trip_model import (
    CityListResponse,
    CitySupportResponse,
    MessageResponse,
    TripPlanRequest,
    TripPlanResponse,
    TripTaskResponse,
    TripVersionsResponse,
)
from app.observability.logger import default_logger as logger
from app.services.city_service import city_support_service
from app.services.llm_service import LLMService
from app.services.redis_service import RedisService
from app.services.vector_memory_service import vector_memory_service


class TripService:
    """Application service for trip planning workflows."""

    _worker_lock = Lock()
    _worker_started = False
    _worker_threads: list[Thread] = []

    def __init__(
        self,
        redis_service: RedisService,
        planner_agent: Optional[PlannerAgent] = None,
    ) -> None:
        self.redis_service = redis_service
        self.planner_agent = planner_agent

    def _get_planner_agent(self) -> PlannerAgent:
        if self.planner_agent is None:
            self.planner_agent = PlannerAgent(
                llm_service=LLMService,
                memory_service=vector_memory_service,
            )
        return self.planner_agent

    def plan_trip(
        self,
        request: TripPlanRequest,
        user_id: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> TripPlanResponse:
        self._validate_request(request)
        city_info = city_support_service.get_city_support_info(request.destination)
        logger.info(
            "Trip planning requested",
            extra={
                "user_id": user_id,
                "destination": request.destination,
                "city_support_level": city_info.get("level"),
            },
        )
        return self._build_and_store_plan(
            request=request, user_id=user_id, city_info=city_info, progress_callback=progress_callback
        )

    def create_trip_task(self, request: TripPlanRequest, user_id: str) -> TripTaskResponse:
        self._validate_request(request)
        task_id = str(uuid.uuid4())
        request_data = request.model_dump()
        if not self.redis_service.create_trip_task(task_id, user_id, request_data):
            raise BusinessException(ErrorCode.TRIP_PLAN_FAILED, message="Failed to create trip task")
        if not self.redis_service.enqueue_trip_task(task_id):
            self.redis_service.update_trip_task(
                task_id,
                status="failed",
                message="Failed to enqueue trip task",
                error="queue_error",
            )
            raise BusinessException(ErrorCode.TRIP_PLAN_FAILED, message="Failed to enqueue trip task")
        return TripTaskResponse(
            task_id=task_id,
            status="pending",
            progress=0,
            message="Task created",
        )

    def start_async_workers(self) -> None:
        with self._worker_lock:
            if self.__class__._worker_started:
                return

            requeued = self.redis_service.requeue_incomplete_trip_tasks()
            worker_count = max(1, settings.ASYNC_TASK_WORKER_COUNT)
            logger.info(
                "Starting trip task workers",
                extra={"worker_count": worker_count, "requeued_tasks": requeued},
            )
            for index in range(worker_count):
                worker = Thread(
                    target=self._task_worker_loop,
                    args=(f"trip-worker-{index + 1}",),
                    daemon=True,
                    name=f"trip-worker-{index + 1}",
                )
                worker.start()
                self.__class__._worker_threads.append(worker)
            self.__class__._worker_started = True

    def get_trip_task(self, task_id: str, user_id: str) -> TripTaskResponse:
        task = self.redis_service.get_trip_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        return TripTaskResponse(
            task_id=task.get("task_id", task_id),
            status=task.get("status", "pending"),
            progress=int(task.get("progress", "0")),
            message=task.get("message", ""),
            result_trip_id=task.get("result_trip_id") or None,
            error=task.get("error") or None,
            city_support_level=task.get("city_support_level") or None,
            city_support_message=task.get("city_support_message") or None,
            updated_at=task.get("updated_at"),
        )

    def list_trips(self, user_id: str) -> list[TripPlanResponse]:
        try:
            return [TripPlanResponse(**trip) for trip in self.redis_service.list_user_trips(user_id)]
        except Exception as exc:
            logger.error("Failed to list trips", extra={"user_id": user_id, "error": str(exc)})
            raise BusinessException(ErrorCode.TRIP_PLAN_FAILED, message="Failed to load trips")

    def get_trip(self, trip_id: str, user_id: str) -> TripPlanResponse:
        trip_data = self.redis_service.get_trip(trip_id)
        if not trip_data:
            raise HTTPException(status_code=404, detail="Trip not found")

        user_trips = {trip.get("id") for trip in self.redis_service.list_user_trips(user_id)}
        if trip_id not in user_trips:
            raise HTTPException(status_code=403, detail="Forbidden")

        return TripPlanResponse(**trip_data)

    def delete_trip(self, trip_id: str, user_id: str) -> MessageResponse:
        success = self.redis_service.delete_trip(user_id, trip_id)
        if not success:
            raise HTTPException(status_code=404, detail="Trip not found or delete failed")
        return MessageResponse(message="Trip deleted")

    def update_trip(
        self,
        trip_id: str,
        user_id: str,
        request: TripPlanResponse,
        if_match_version: Optional[int],
    ) -> TripPlanResponse:
        expected_version = if_match_version if if_match_version is not None else request.version
        success, reason = self.redis_service.update_trip(
            user_id=user_id,
            trip_id=trip_id,
            trip_data=request.model_dump(),
            expected_version=expected_version,
        )
        if not success:
            if reason == "version_conflict":
                raise HTTPException(status_code=409, detail="Trip version conflict")
            if reason == "forbidden":
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=404, detail="Trip not found or update failed")

        updated_trip = self.redis_service.get_trip(trip_id)
        if not updated_trip:
            raise HTTPException(status_code=404, detail="Trip not found after update")
        return TripPlanResponse(**updated_trip)

    def list_trip_versions(self, trip_id: str, user_id: str) -> TripVersionsResponse:
        versions = self.redis_service.list_trip_versions(user_id=user_id, trip_id=trip_id)
        return TripVersionsResponse(trip_id=trip_id, versions=versions)

    def rollback_trip(self, trip_id: str, user_id: str, target_version: int) -> TripPlanResponse:
        success, reason = self.redis_service.rollback_trip(
            user_id=user_id,
            trip_id=trip_id,
            target_version=target_version,
        )
        if not success:
            if reason == "forbidden":
                raise HTTPException(status_code=403, detail="Forbidden")
            if reason in {"version_not_found", "not_found"}:
                raise HTTPException(status_code=404, detail="Trip or version not found")
            raise HTTPException(status_code=500, detail="Rollback failed")

        trip = self.redis_service.get_trip(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found after rollback")
        return TripPlanResponse(**trip)

    def get_city_support(self, city: str) -> CitySupportResponse:
        support = city_support_service.get_city_support_info(city)
        return CitySupportResponse(
            city=city,
            level=support.get("level", "unknown"),
            message=support.get("message", ""),
        )

    def list_city_support(self) -> CityListResponse:
        cities = city_support_service.list_cities()
        city_names = list(cities.keys()) if isinstance(cities, dict) else list(cities)
        return CityListResponse(count=len(city_names), cities=city_names)

    def _validate_request(self, request: TripPlanRequest) -> None:
        if not request.destination or not request.destination.strip():
            raise BusinessException(
                ErrorCode.MISSING_PARAMETER,
                details={"field": "destination", "message": "Destination is required"},
            )
        if not request.start_date or not request.end_date:
            raise BusinessException(
                ErrorCode.MISSING_PARAMETER,
                details={"field": "date_range", "message": "Date range is required"},
            )

    def _build_and_store_plan(
        self,
        request: TripPlanRequest,
        user_id: str,
        city_info: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> TripPlanResponse:
        city_info = city_info or city_support_service.get_city_support_info(request.destination)
        final_plan = self._get_planner_agent().plan_trip(
            request=request, user_id=user_id, progress_callback=progress_callback
        )
        if not final_plan:
            raise BusinessException(
                ErrorCode.TRIP_PLAN_FAILED,
                details={"message": "Failed to generate trip plan"},
            )

        trip_data = {
            "destination": request.destination,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "preferences": request.preferences,
            "hotel_preferences": request.hotel_preferences,
            "budget": request.budget,
            "trip_title": final_plan.trip_title,
            "days": [day.model_dump() for day in final_plan.days],
        }
        vector_memory_service.store_user_trip(user_id, trip_data)
        vector_memory_service.store_user_preference(
            user_id,
            "trip_preferences",
            {
                "destination": request.destination,
                "preferences": request.preferences,
                "hotel_preferences": request.hotel_preferences,
                "budget": request.budget,
            },
        )
        vector_memory_service.schedule_save()

        trip_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        full_trip_data = final_plan.model_dump()
        full_trip_data.update(
            {
                "id": trip_id,
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "city_support_level": city_info.get("level"),
                "city_support_message": city_info.get("message"),
            }
        )
        self.redis_service.store_trip(user_id, trip_id, full_trip_data)
        return TripPlanResponse(**full_trip_data)

    def _plan_task_worker(self, task_id: str, user_id: str, request_data: Dict[str, Any]) -> None:
        try:
            self.redis_service.update_trip_task(
                task_id,
                status="running",
                progress=10,
                message="Task started",
            )
            request = TripPlanRequest(**request_data)
            city_info = city_support_service.get_city_support_info(request.destination)
            self.redis_service.update_trip_task(
                task_id,
                progress=20,
                message="City support evaluated",
                city_support_level=city_info.get("level"),
                city_support_message=city_info.get("message"),
            )
            result = self._build_and_store_plan(
                request,
                user_id,
                city_info=city_info,
                progress_callback=lambda p, m: self.redis_service.update_trip_task(
                    task_id, progress=p, message=m
                ),
            )
            self.redis_service.update_trip_task(
                task_id,
                status="succeeded",
                progress=100,
                message="Trip generated",
                result_trip_id=result.id or "",
            )
        except Exception as exc:
            logger.error(
                "Async trip task failed",
                exc_info=True,
                extra={"task_id": task_id, "user_id": user_id, "error": str(exc)},
            )
            self.redis_service.update_trip_task(
                task_id,
                status="failed",
                progress=100,
                message="Trip generation failed",
                error="trip_generation_failed",
            )

    def _task_worker_loop(self, worker_id: str) -> None:
        logger.info("Trip task worker started", extra={"worker_id": worker_id})
        while True:
            task_id = self.redis_service.dequeue_trip_task(timeout_seconds=5)
            if not task_id:
                continue

            claimed_task = self.redis_service.claim_trip_task(
                task_id=task_id,
                worker_id=worker_id,
                lease_seconds=settings.ASYNC_TASK_LEASE_SECONDS,
            )
            if not claimed_task:
                continue

            request_data_raw = claimed_task.get("request_data", "{}")
            try:
                request_data = (
                    json.loads(request_data_raw)
                    if isinstance(request_data_raw, str)
                    else dict(request_data_raw)
                )
            except Exception:
                self.redis_service.update_trip_task(
                    task_id,
                    status="failed",
                    progress=100,
                    message="Invalid task payload",
                    error="invalid_request_payload",
                )
                continue

            self._plan_task_worker(
                task_id=task_id,
                user_id=claimed_task.get("user_id", ""),
                request_data=request_data,
            )
