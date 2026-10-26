import logging
from fastapi import APIRouter, Query
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


@router.get("/stats")
async def get_stats():
    try:
        if audit_logger:
            stats = await audit_logger.get_stats()
            if stats.get("total_requests", 0) > 0:
                return stats
    except Exception as e:
        logger.warning("Stats fetch failed: %s", e)
    return generate_mock_stats()


@router.get("/alerts")
async def get_alerts():
    try:
        if audit_logger:
            entries = await audit_logger.get_recent(50)
            if entries:
                return entries
    except Exception as e:
        logger.warning("Alerts fetch failed: %s", e)
    return generate_mock_alerts(50)


@router.get("/clients")
async def get_clients():
    try:
        if audit_logger:
            clients = await audit_logger.get_client_stats()
            if clients:
                return clients
    except Exception as e:
        logger.warning("Clients fetch failed: %s", e)
    return generate_mock_clients(10)


@router.get("/volume")
async def get_volume(hours: int = Query(default=24, ge=1, le=168)):
    return generate_mock_volume(hours)
