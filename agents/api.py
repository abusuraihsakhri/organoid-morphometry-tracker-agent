"""
FastAPI REST API Server for Organoid Morphometry Tracker Agent.
"""
import hmac
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from .base import AuditLogger, PHIGuard, SecurityException, ResourceLimitExceededException
from .metrics import GLOBAL_METRICS
from .models import SystemTaskPayload, ConsensusDossier
from .supervisor import SystemSupervisor

supervisor = SystemSupervisor(model_provider="mock")

app = FastAPI(
    title="Organoid Morphometry Tracker Agent API",
    description="Research demonstration of numeric threshold screening; not validated clinical decision support",
    version="3.0.0-ENTERPRISE",
)


@app.middleware("http")
async def api_token_guard(request: Request, call_next):
    """Protect API operations when AUDIT_API_TOKEN is configured."""
    token = os.environ.get("AUDIT_API_TOKEN")
    if token and (request.url.path.startswith("/api/") or request.url.path in ("/metrics", "/metrics/prometheus")):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + token):
            return JSONResponse(status_code=401, content={"detail": "Bearer token required"})
    return await call_next(request)


class ChatRequest(BaseModel):
    query: str


@app.exception_handler(SecurityException)
async def security_error_handler(request: Request, exc: SecurityException):
    GLOBAL_METRICS.record_phi_block()
    return JSONResponse(status_code=400, content={"detail": "Input contains a potentially sensitive identifier."})


@app.exception_handler(ResourceLimitExceededException)
async def resource_error_handler(request: Request, exc: ResourceLimitExceededException):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).resolve().parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "HEALTHY", "service": "organoid-morphometry-tracker-agent", "domain": "Numeric screening demonstration", "standard": "Repository-defined thresholds", "version": "3.0.0-ENTERPRISE"}


@app.get("/metrics")
def metrics():
    return {
        "dossiers_processed_total": len(supervisor.dossier_registry),
        "audit_blocks_total": len(AuditLogger.get_trail()),
        "system_status": "AVAILABLE"
    }


@app.get("/metrics/prometheus")
def prometheus_metrics():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(GLOBAL_METRICS.export_prometheus_text())


@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload):
    dossier = supervisor.process_task(payload)
    return dossier.to_dict()


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        ans = supervisor.query_supervisory_chat(req.query)
        return {"response": ans}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/audit/logs")
def api_audit_logs():
    return {"audit_trail": AuditLogger.get_trail(), "verified": AuditLogger.verify_integrity()}
