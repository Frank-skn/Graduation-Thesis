"""
Scenario management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.core.database import get_db_nds
from backend.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioList
from backend.data_access.repositories import ScenarioRepository

router = APIRouter()


@router.post("/", response_model=ScenarioResponse, status_code=201)
def create_scenario(
    scenario: ScenarioCreate,
    db: Session = Depends(get_db_nds)
):
    """
    Create a new scenario
    
    - **scenario_name**: Unique name for the scenario
    - **description**: Optional description
    - **created_by**: User/analyst creating the scenario
    """
    repo = ScenarioRepository(db)
    scenario_id = repo.create_scenario(
        name=scenario.scenario_name,
        description=scenario.description,
        created_by=scenario.created_by
    )
    
    scenario_data = repo.get_scenario(scenario_id)
    if not scenario_data:
        raise HTTPException(status_code=500, detail="Failed to create scenario")
    
    return ScenarioResponse(**scenario_data)


@router.get("/", response_model=ScenarioList)
def list_scenarios(
    limit: int = 50,
    db: Session = Depends(get_db_nds)
):
    """
    List all scenarios
    
    - **limit**: Maximum number of scenarios to return (default: 50)
    """
    repo = ScenarioRepository(db)
    scenarios = repo.list_scenarios(limit=limit)
    
    return ScenarioList(
        scenarios=[ScenarioResponse(**s) for s in scenarios],
        total=len(scenarios)
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db_nds)
):
    """
    Get scenario details by ID
    """
    repo = ScenarioRepository(db)
    scenario = repo.get_scenario(scenario_id)
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    return ScenarioResponse(**scenario)


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db_nds)
):
    """
    Delete a scenario and all associated runs
    """
    repo = ScenarioRepository(db)
    success = repo.delete_scenario(scenario_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    return None
