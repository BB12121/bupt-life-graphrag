import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .config import Settings
from .frontend import FrontendFiles
from .models import (
    AppError,
    DocumentDetail,
    DocumentList,
    EntityList,
    ErrorResponse,
    KnowledgeStatus,
    QARequest,
    QAResponse,
    SelectedCampus,
    SyncRequest,
    SyncResponse,
)
from .retrieval import scope_matches
from .service import KnowledgeService

log = logging.getLogger(__name__)


def create_app(settings=None, service=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = service or KnowledgeService(settings)
        yield
        app.state.service.close()

    app = FastAPI(
        title="北邮生活指南 GraphRAG",
        version="0.1.0",
        lifespan=lifespan,
        description="基于固定指南快照的可追溯问答；单进程运行。",
        responses={code: {"model": ErrorResponse} for code in (404, 422, 500, 503)},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Admin-Key"],
    )

    def error(code, message, status):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return error(exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error("invalid_request", "请求参数不符合接口约定，请检查字段类型、枚举和必填值。", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error("http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error("Unhandled backend error", exc_info=(type(exc), exc, exc.__traceback__))
        return error("internal_error", "服务内部错误，请查看后端日志。", 500)

    @app.get("/healthz", tags=["health"])
    def health():
        return {"status": "ok"}

    @app.post("/api/v1/knowledge/sync", response_model=SyncResponse, tags=["knowledge"])
    def sync(body: SyncRequest, request: Request, x_admin_key: str | None = Header(default=None)):
        if settings.admin_key and not hmac.compare_digest(x_admin_key or "", settings.admin_key):
            raise AppError("unauthorized", "同步操作需要有效的 X-Admin-Key。", 401)
        return request.app.state.service.sync(body.ref)

    @app.get("/api/v1/knowledge/status", response_model=KnowledgeStatus, tags=["knowledge"])
    def status(request: Request):
        svc = request.app.state.service
        with svc.lock:
            return svc.status()

    @app.get("/api/v1/documents", response_model=DocumentList, tags=["documents"])
    def documents(request: Request):
        svc = request.app.state.service
        with svc.lock:
            return {
                "items": [r["document"] for r in svc.snapshot["payload"]["documents"].values()]
                if svc.snapshot
                else []
            }

    @app.get("/api/v1/documents/{doc_id}", response_model=DocumentDetail, tags=["documents"])
    def get_document(
        doc_id: str,
        request: Request,
        source_commit: str | None = Query(default=None, pattern=r"^[a-f0-9]{40}$"),
    ):
        svc = request.app.state.service
        with svc.lock:
            return svc.get_document(doc_id, source_commit)

    @app.get("/api/v1/entities", response_model=EntityList, tags=["entities"])
    def entities(
        request: Request, q: str = Query(default="", max_length=200), campus: SelectedCampus | None = None
    ):
        svc = request.app.state.service
        with svc.lock:
            values = svc.index.entities.values() if svc.index else []
            return {
                "items": [
                    e
                    for e in values
                    if scope_matches(e.campus, campus)
                    and any(q.casefold() in n.casefold() for n in [e.name, *e.aliases])
                ]
            }

    @app.post("/api/v1/qa", response_model=QAResponse, tags=["qa"])
    def qa(body: QARequest, request: Request):
        return request.app.state.service.ask(body)

    if (settings.frontend_dist / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=settings.frontend_dist), name="frontend")

    return app


app = create_app()
