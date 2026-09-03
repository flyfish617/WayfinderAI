"""
Global exception handling.
"""

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.exceptions.custom_exceptions import BaseAppException
from app.exceptions.error_codes import ErrorCode
from app.observability.logger import default_logger as logger, get_request_id


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id()

    if isinstance(exc, BaseAppException):
        logger.error(
            f"Business exception: {exc.message}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "error_code": exc.error_code.value,
                "error_message": exc.message,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error_code": exc.error_code.value,
                "error_message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            },
        )

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        logger.warning(
            "Request validation failed",
            extra={
                "request_id": request_id,
                "errors": errors,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error_code": ErrorCode.INVALID_PARAMETER.value,
                "error_message": "Request validation failed",
                "details": {"validation_errors": errors},
                "request_id": request_id,
            },
        )

    if isinstance(exc, (StarletteHTTPException, HTTPException)):
        status_code = exc.status_code if hasattr(exc, "status_code") else 500
        detail = exc.detail if hasattr(exc, "detail") else str(exc)
        safe_detail = detail if status_code < 500 else "Internal server error"
        error_code = (
            ErrorCode.RATE_LIMIT_EXCEEDED.value
            if status_code == 429
            else ErrorCode.UNKNOWN_ERROR.value
        )

        logger.warning(
            "HTTP exception",
            extra={
                "request_id": request_id,
                "status_code": status_code,
                "detail": safe_detail,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error_code": error_code,
                "error_message": safe_detail,
                "request_id": request_id,
            },
        )

    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": ErrorCode.UNKNOWN_ERROR.value,
            "error_message": "Internal server error",
            "details": (
                {
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                }
                if settings.EXPOSE_INTERNAL_ERRORS
                else None
            ),
            "request_id": request_id,
        },
    )
