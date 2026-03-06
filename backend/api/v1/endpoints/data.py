"""
Data query endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.core.database import get_db_dds
from backend.data_access.repositories import OptimizationDataRepository

router = APIRouter()


@router.get("/products", response_model=List[str])
def get_products(db: Session = Depends(get_db_dds)):
    """
    Get list of all active products
    """
    repo = OptimizationDataRepository(db)
    return repo.get_products()


@router.get("/warehouses", response_model=List[str])
def get_warehouses(db: Session = Depends(get_db_dds)):
    """
    Get list of all active warehouses
    """
    repo = OptimizationDataRepository(db)
    return repo.get_warehouses()


@router.get("/time-periods", response_model=List[int])
def get_time_periods(db: Session = Depends(get_db_dds)):
    """
    Get list of all time periods
    """
    repo = OptimizationDataRepository(db)
    return repo.get_time_periods()
