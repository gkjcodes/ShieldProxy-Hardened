import logging
from typing import Optional
from fastapi import APIRouter, Query, Depends
from middleware.auth import TenantContext, get_current_tenant, require_admin_role
from config import settings, AppMode
from utils.mock_data import (
    generate_mock_stats,
    generate_mock_alerts,
    generate_mock_clients,
    generate_mock_volume,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])

# Injected by main.py
audit_logger = None


def init_dashboard(al):
    global audit_logger
    audit_logger = al


def _ensure_dashboard_initialized():
    global audit_logger
    if audit_logger is None:
        from utils.redis_client import MockRedis
        from middleware.audit_logger import AuditLogger
        audit_logger = AuditLogger(MockRedis())


@router.get("/stats")
async def get_stats(tenant: TenantContext = Depends(get_current_tenant)):
    _ensure_dashboard_initialized()
    try:
        tenant_filter = None if tenant.is_admin() else tenant.tenant_id
        stats = await audit_logger.get_stats(tenant_id=tenant_filter)
        if stats.get("total_requests", 0) > 0 or settings.APP_MODE == AppMode.PROTECTED:
            return stats
    except Exception as e:
        logger.warning("Stats fetch failed: %s", e)

    if settings.APP_MODE == AppMode.DEVELOPMENT:
        return generate_mock_stats()
    return {
        "total_requests": 0,
        "total_blocked": 0,
        "total_passed": 0,
        "block_rate": 0.0,
        "threats_by_type": {},
        "avg_latency_ms": 0.0,
        "requests_last_hour": 0,
    }


@router.get("/alerts")
async def get_alerts(
    count: int = Query(default=50, ge=1, le=200),
    tenant: TenantContext = Depends(get_current_tenant),
):
    _ensure_dashboard_initialized()
    try:
        tenant_filter = None if tenant.is_admin() else tenant.tenant_id
        entries = await audit_logger.get_recent(count, tenant_id=tenant_filter)
        if entries or settings.APP_MODE == AppMode.PROTECTED:
            return entries
    except Exception as e:
        logger.warning("Alerts fetch failed: %s", e)

    if settings.APP_MODE == AppMode.DEVELOPMENT:
        return generate_mock_alerts(count)
    return []


@router.get("/clients")
async def get_clients(admin: TenantContext = Depends(require_admin_role)):
    _ensure_dashboard_initialized()
    try:
        clients = await audit_logger.get_client_stats()
        if clients or settings.APP_MODE == AppMode.PROTECTED:
            return clients
    except Exception as e:
        logger.warning("Clients fetch failed: %s", e)

    if settings.APP_MODE == AppMode.DEVELOPMENT:
        return generate_mock_clients(10)
    return []


@router.get("/volume")
async def get_volume(
    hours: int = Query(default=24, ge=1, le=168),
    tenant: TenantContext = Depends(get_current_tenant),
):
    if settings.APP_MODE == AppMode.DEVELOPMENT:
        return generate_mock_volume(hours)
    return []