"""
API v1 router aggregation
"""
from fastapi import APIRouter
from backend.api.v1.endpoints import (
    scenarios,
    optimization,
    data,
    data_overview,
    results,
    whatif,
    sensitivity,
    insights,
)

api_router = APIRouter()

api_router.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"])
api_router.include_router(optimization.router, prefix="/optimize", tags=["Optimization"])
api_router.include_router(data.router, prefix="/data", tags=["Data"])
api_router.include_router(data_overview.router, prefix="/data-overview", tags=["Data Overview"])
api_router.include_router(results.router, prefix="/results", tags=["Results"])
api_router.include_router(whatif.router, prefix="/whatif", tags=["What-If"])
api_router.include_router(sensitivity.router, prefix="/sensitivity", tags=["Sensitivity"])
api_router.include_router(insights.router, prefix="/insights", tags=["Insights"])
