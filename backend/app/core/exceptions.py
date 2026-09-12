from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            content=jsonable_encoder(error_payload(exc.code, exc.message, exc.details)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        message = "Request validation failed"
        if _.url.path.endswith("/payment-settings") and any(
            error["loc"][-1] in ("mode", "key_id") for error in exc.errors()
        ):
            message = "Only TEST mode and rzp_test_ credentials are accepted"
        return JSONResponse(
            status_code=400,
            headers={"Cache-Control": "no-store"},
            content=jsonable_encoder(
                error_payload(
                    "VALIDATION_ERROR",
                    message,
                    [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()],
                )
            ),
        )
