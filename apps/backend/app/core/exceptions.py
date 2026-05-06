"""Custom exceptions and FastAPI exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ChefTraceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(ChefTraceError):
    def __init__(self, entity: str):
        super().__init__(f"{entity} not found", status_code=404)


class ForbiddenError(ChefTraceError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class ConflictError(ChefTraceError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ChefTraceError)
    async def cheftrace_error_handler(request: Request, exc: ChefTraceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
