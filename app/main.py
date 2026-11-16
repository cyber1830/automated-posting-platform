"""FastAPI entrypoint.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 4000
Docs: http://localhost:4000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.platforms import build_platforms
from app.schemas import (
    HealthResponse,
    PlatformInfo,
    PostRequest,
    PostResponse,
    Summary,
    ValidationErrorResponse,
)
from app.services.posting_service import PostingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": "automated-posting/1.0"},
    ) as client:
        app.state.service = PostingService(
            platforms=build_platforms(settings),
            client=client,
            platform_timeout=settings.platform_timeout_seconds,
            verify_public=settings.verify_public_access,
        )
        yield


app = FastAPI(
    title="Automated Multi-Platform Posting",
    description="Publishes one short message (with a single CTA link) to several platforms.",
    version="1.0.0",
    lifespan=lifespan,
)


def get_service(request: Request) -> PostingService:
    return request.app.state.service


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = [str(part) for part in err["loc"] if part != "body"]
        details.append(
            {
                "field": ".".join(loc) or "body",
                "message": err["msg"].removeprefix("Value error, "),
            }
        )
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "validation_error", "details": details},
    )


@app.post(
    "/posting",
    response_model=PostResponse,
    tags=["posting"],
    summary="Post a message to all configured platforms",
    responses={422: {"model": ValidationErrorResponse, "description": "Invalid message"}},
)
async def post_message(
    payload: PostRequest, service: PostingService = Depends(get_service)
) -> PostResponse:
    results = await service.publish_all(payload.message)
    succeeded = sum(1 for r in results if r.status == "success")
    return PostResponse(
        success=succeeded > 0,
        summary=Summary(total=len(results), succeeded=succeeded, failed=len(results) - succeeded),
        results=results,
    )


@app.get(
    "/platforms",
    response_model=list[PlatformInfo],
    tags=["meta"],
    summary="Which platforms are configured",
)
async def list_platforms(service: PostingService = Depends(get_service)) -> list[PlatformInfo]:
    return [
        {
            "platform": p.name,
            "configured": p.is_configured,
            "missing_credentials": p.missing_credentials(),
        }
        for p in service.platforms
    ]


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse()
