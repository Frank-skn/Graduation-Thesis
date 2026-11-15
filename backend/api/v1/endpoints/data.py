"""
Data query endpoints
"""
from fastapi import APIRouter, Depends
from typing import List
from backend.core.database import get_csv_data
from backend.data_access.csv_repository import CsvOptimizationDataRepository

router = APIRouter()


@router.get("/products", response_model=List[str])
def get_products(repo: CsvOptimizationDataRepository = Depends(get_csv_data)):
    """
    Get list of all active products
    """
    return repo.get_products()


@router.get("/warehouses", response_model=List[str])
def get_warehouses(repo: CsvOptimizationDataRepository = Depends(get_csv_data)):
    """
    Get list of all active warehouses
    """
    return repo.get_warehouses()


@router.get("/time-periods", response_model=List[int])
def get_time_periods(repo: CsvOptimizationDataRepository = Depends(get_csv_data)):
    """
    Get list of all time periods
    """
    return repo.get_time_periods()
