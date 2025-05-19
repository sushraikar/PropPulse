"""
API routes for risk data access

This module provides API endpoints for risk data:
- GET /risk/<property_id> -> JSON {mean_irr, VaR, grade}
- GET /risk/<property_id>/export -> CSV export of simulation results
"""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from db.database import get_db
from agents.monte_carlo_irr_agent.monte_carlo_irr_agent import MonteCarloIRRAgent
from agents.risk_score_composer.risk_score_composer import RiskScoreComposer
from agents.risk_data_exporter.risk_data_exporter import RiskDataExporter
from db.models.risk_models import RiskResult, RiskGrade

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/risk",
    tags=["risk"],
    responses={404: {"description": "Not found"}}
)

@router.get("/{property_id}")
async def get_risk_data(property_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get risk data for a property
    
    Args:
        property_id: Property ID
        db: Database session
        
    Returns:
        Risk data including mean_irr, VaR, and grade
    """
    try:
        # Get latest risk result
        risk_result = db.query(RiskResult).filter(
            RiskResult.property_id == property_id
        ).order_by(
            RiskResult.timestamp.desc()
        ).first()
        
        if not risk_result:
            raise HTTPException(status_code=404, detail=f"No risk data found for property: {property_id}")
        
        # Return risk data
        return {
            "property_id": property_id,
            "mean_irr": risk_result.mean_irr,
            "var_5": risk_result.var_5,
            "var_95": risk_result.var_95,
            "prob_negative": risk_result.prob_negative,
            "prob_above_threshold": risk_result.prob_above_threshold,
            "breakeven_year": risk_result.breakeven_year,
            "yield_on_cost_year_1": risk_result.yield_on_cost_year_1,
            "risk_grade": risk_result.risk_grade.value,
            "simulation_count": risk_result.simulation_count,
            "timestamp": risk_result.timestamp.isoformat(),
            "simulation_parameters": risk_result.simulation_parameters,
            "simulation_results": risk_result.simulation_results
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to get risk data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get risk data: {str(e)}")

@router.get("/{property_id}/export")
async def export_risk_data(property_id: str, db: Session = Depends(get_db)):
    """
    Export risk data for a property as CSV
    
    Args:
        property_id: Property ID
        db: Database session
        
    Returns:
        CSV file with risk simulation results
    """
    try:
        # Initialize risk data exporter
        exporter = RiskDataExporter()
        
        # Export simulation results
        export_result = await exporter.export_simulation_results(property_id, db)
        
        if export_result.get('status') != 'success':
            raise HTTPException(status_code=500, detail=export_result.get('message', 'Export failed'))
        
        # Set content type and filename based on format
        if export_result.get('file_format') == 'zip':
            content_type = "application/zip"
            filename = f"risk_simulation_{property_id}.zip"
        else:
            content_type = "text/csv"
            filename = f"risk_simulation_{property_id}.csv"
        
        # Return file
        return Response(
            content=export_result.get('file_data'),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to export risk data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export risk data: {str(e)}")

@router.get("/distribution")
async def get_risk_distribution(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get distribution of risk grades across all properties
    
    Args:
        db: Database session
        
    Returns:
        Risk grade distribution
    """
    try:
        # Initialize risk score composer
        composer = RiskScoreComposer()
        
        # Get risk grade distribution
        distribution = await composer.get_risk_grade_distribution(db)
        
        if distribution.get('status') != 'success':
            raise HTTPException(status_code=500, detail=distribution.get('message', 'Failed to get distribution'))
        
        return distribution
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to get risk distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get risk distribution: {str(e)}")

@router.post("/{property_id}/run-simulation")
async def run_simulation(property_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation for a property
    
    Args:
        property_id: Property ID
        db: Database session
        
    Returns:
        Simulation results
    """
    try:
        # Initialize Monte Carlo IRR agent
        agent = MonteCarloIRRAgent()
        
        # Run simulation
        simulation_result = await agent.run_simulation(property_id, db)
        
        if simulation_result.get('status') != 'success':
            raise HTTPException(status_code=500, detail=simulation_result.get('message', 'Simulation failed'))
        
        # Update risk grade
        composer = RiskScoreComposer()
        grade_result = await composer.compute_risk_grade(property_id, db)
        
        if grade_result.get('status') != 'success':
            logger.warning(f"Failed to update risk grade: {grade_result.get('message')}")
        
        return simulation_result
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to run simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run simulation: {str(e)}")

@router.get("/{property_id}/history")
async def get_risk_grade_history(property_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get risk grade history for a property
    
    Args:
        property_id: Property ID
        db: Database session
        
    Returns:
        Risk grade history
    """
    try:
        # Initialize risk score composer
        composer = RiskScoreComposer()
        
        # Get risk grade history
        history = await composer.get_risk_grade_history(property_id, db)
        
        if history.get('status') != 'success':
            raise HTTPException(status_code=500, detail=history.get('message', 'Failed to get history'))
        
        return history
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to get risk grade history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get risk grade history: {str(e)}")

@router.get("/grade/{risk_grade}")
async def get_properties_by_risk_grade(risk_grade: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get properties by risk grade
    
    Args:
        risk_grade: Risk grade (green, amber, red)
        db: Database session
        
    Returns:
        Properties with specified risk grade
    """
    try:
        # Validate risk grade
        try:
            grade = RiskGrade[risk_grade.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid risk grade: {risk_grade}")
        
        # Query properties by risk grade
        properties = db.query(Property).filter(
            Property.risk_grade == grade
        ).all()
        
        # Convert to list of dictionaries
        property_list = []
        for prop in properties:
            property_list.append({
                "id": prop.id,
                "list_price_aed": prop.list_price_aed,
                "tower": prop.tower,
                "floor": prop.floor,
                "unit_type": prop.unit_type,
                "risk_grade": prop.risk_grade.value,
                "last_risk_assessment": prop.last_risk_assessment.isoformat() if prop.last_risk_assessment else None
            })
        
        return {
            "risk_grade": risk_grade,
            "count": len(property_list),
            "properties": property_list
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to get properties by risk grade: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get properties by risk grade: {str(e)}")
