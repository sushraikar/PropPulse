"""
REST API endpoints for co-investment functionality
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

from db.database import get_db
from db.models.co_investment import CoInvestmentGroup, CapTable, KYCStatus
from integrations.idnow.idnow_api import IDnowAPI
from integrations.zoho.zoho_crm import ZohoCRM

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
co_invest_router = APIRouter(prefix="/co-invest", tags=["Co-Investment"])

# Initialize integrations
idnow_api = IDnowAPI()
zoho_crm = ZohoCRM()

@co_invest_router.post("/start")
async def start_co_investment(
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start a new co-investment group for a property
    
    Args:
        data: Request data
            - unit_id: Property unit ID
            - target_raise: Target amount to raise in AED
            - min_tick: Minimum investment amount in AED
            - name: (Optional) Name for the co-investment group
            
    Returns:
        Co-investment group data
    """
    try:
        # Validate required fields
        required_fields = ["unit_id", "target_raise", "min_tick"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Get property from Zoho CRM
        property_data = await zoho_crm.get_property(data["unit_id"])
        
        if not property_data:
            raise HTTPException(status_code=404, detail=f"Property not found: {data['unit_id']}")
        
        # Check if property is available
        if property_data.get("Status") != "Available":
            raise HTTPException(status_code=400, detail=f"Property is not available for co-investment")
        
        # Create co-investment group
        group_name = data.get("name", f"Syndicate - {property_data.get('Unit_No', 'Unknown')}")
        
        co_investment_group = CoInvestmentGroup(
            name=group_name,
            property_id=data["unit_id"],
            target_raise=data["target_raise"],
            min_tick=data["min_tick"],
            current_raise=0.0,
            status="open"
        )
        
        db.add(co_investment_group)
        db.commit()
        db.refresh(co_investment_group)
        
        # Return co-investment group data
        return {
            "status": "success",
            "message": "Co-investment group created successfully",
            "co_investment_group": {
                "id": co_investment_group.id,
                "name": co_investment_group.name,
                "property_id": co_investment_group.property_id,
                "target_raise": co_investment_group.target_raise,
                "min_tick": co_investment_group.min_tick,
                "current_raise": co_investment_group.current_raise,
                "status": co_investment_group.status,
                "created_at": co_investment_group.created_at.isoformat()
            },
            "property": {
                "id": property_data.get("id"),
                "unit_no": property_data.get("Unit_No"),
                "project_name": property_data.get("Project_Name"),
                "list_price_aed": property_data.get("List_Price_AED")
            }
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error starting co-investment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting co-investment: {str(e)}")

@co_invest_router.get("/groups")
async def get_co_investment_groups(
    status: Optional[str] = Query(None, description="Filter by status"),
    property_id: Optional[str] = Query(None, description="Filter by property ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get co-investment groups
    
    Args:
        status: (Optional) Filter by status
        property_id: (Optional) Filter by property ID
        
    Returns:
        List of co-investment groups
    """
    try:
        # Build query
        query = db.query(CoInvestmentGroup)
        
        if status:
            query = query.filter(CoInvestmentGroup.status == status)
        
        if property_id:
            query = query.filter(CoInvestmentGroup.property_id == property_id)
        
        # Execute query
        groups = query.all()
        
        # Format response
        result = []
        for group in groups:
            result.append({
                "id": group.id,
                "name": group.name,
                "property_id": group.property_id,
                "target_raise": group.target_raise,
                "min_tick": group.min_tick,
                "current_raise": group.current_raise,
                "status": group.status,
                "created_at": group.created_at.isoformat()
            })
        
        return {
            "status": "success",
            "count": len(result),
            "groups": result
        }
    
    except Exception as e:
        logger.error(f"Error getting co-investment groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting co-investment groups: {str(e)}")

@co_invest_router.get("/groups/{group_id}")
async def get_co_investment_group(
    group_id: int = Path(..., description="Co-investment group ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get co-investment group by ID
    
    Args:
        group_id: Co-investment group ID
        
    Returns:
        Co-investment group data
    """
    try:
        # Get co-investment group
        group = db.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == group_id).first()
        
        if not group:
            raise HTTPException(status_code=404, detail=f"Co-investment group not found: {group_id}")
        
        # Get property data
        property_data = await zoho_crm.get_property(group.property_id)
        
        # Get cap table entries
        cap_table_entries = db.query(CapTable).filter(CapTable.co_investment_group_id == group_id).all()
        
        # Format cap table entries
        cap_table = []
        for entry in cap_table_entries:
            cap_table.append({
                "id": entry.id,
                "investor_name": entry.investor_name,
                "investor_email": entry.investor_email,
                "investment_amount": entry.investment_amount,
                "share_percentage": entry.share_percentage,
                "token_amount": entry.token_amount,
                "investor_class": entry.investor_class.value,
                "kyc_status": entry.kyc_status.value,
                "sign_status": entry.sign_status.value,
                "token_status": entry.token_status.value,
                "created_at": entry.created_at.isoformat()
            })
        
        # Calculate funding progress
        funding_progress = (group.current_raise / group.target_raise) * 100 if group.target_raise > 0 else 0
        
        # Return co-investment group data
        return {
            "status": "success",
            "group": {
                "id": group.id,
                "name": group.name,
                "property_id": group.property_id,
                "target_raise": group.target_raise,
                "min_tick": group.min_tick,
                "current_raise": group.current_raise,
                "funding_progress": funding_progress,
                "status": group.status,
                "token_contract_address": group.token_contract_address,
                "gnosis_safe_address": group.gnosis_safe_address,
                "created_at": group.created_at.isoformat()
            },
            "property": property_data,
            "cap_table": cap_table
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting co-investment group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting co-investment group: {str(e)}")

@co_invest_router.post("/invest")
async def invest_in_group(
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Invest in a co-investment group
    
    Args:
        data: Request data
            - group_id: Co-investment group ID
            - investor_name: Investor name
            - investor_email: Investor email
            - investor_phone: Investor phone
            - investment_amount: Investment amount in AED
            - investor_class: (Optional) Investor class (class_a, class_b)
            
    Returns:
        Investment data
    """
    try:
        # Validate required fields
        required_fields = ["group_id", "investor_name", "investor_email", "investment_amount"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Get co-investment group
        group = db.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == data["group_id"]).first()
        
        if not group:
            raise HTTPException(status_code=404, detail=f"Co-investment group not found: {data['group_id']}")
        
        # Check if group is open for investment
        if group.status != "open":
            raise HTTPException(status_code=400, detail=f"Co-investment group is not open for investment")
        
        # Check if investment amount meets minimum tick
        if data["investment_amount"] < group.min_tick:
            raise HTTPException(status_code=400, detail=f"Investment amount must be at least {group.min_tick} AED")
        
        # Check if investment would exceed target raise
        if group.current_raise + data["investment_amount"] > group.target_raise:
            raise HTTPException(status_code=400, detail=f"Investment would exceed target raise")
        
        # Check if investor already exists in this group
        existing_investor = db.query(CapTable).filter(
            CapTable.co_investment_group_id == data["group_id"],
            CapTable.investor_email == data["investor_email"]
        ).first()
        
        if existing_investor:
            raise HTTPException(status_code=400, detail=f"Investor already exists in this group")
        
        # Calculate share percentage
        share_percentage = (data["investment_amount"] / group.target_raise) * 100
        
        # Create cap table entry
        cap_table_entry = CapTable(
            co_investment_group_id=data["group_id"],
            investor_name=data["investor_name"],
            investor_email=data["investor_email"],
            investor_phone=data.get("investor_phone"),
            investment_amount=data["investment_amount"],
            share_percentage=share_percentage,
            investor_class=data.get("investor_class", "class_a"),
            kyc_status=KYCStatus.PENDING,
            is_us_resident=data.get("is_us_resident", False)
        )
        
        # Check for US residents
        if cap_table_entry.is_us_resident:
            raise HTTPException(status_code=400, detail="US residents are not supported at this time")
        
        # Add to database
        db.add(cap_table_entry)
        
        # Update group current raise
        group.current_raise += data["investment_amount"]
        
        # Check if group is fully funded
        if group.current_raise >= group.target_raise:
            group.status = "funded"
        
        db.commit()
        db.refresh(cap_table_entry)
        
        # Start KYC process in background
        background_tasks.add_task(
            start_kyc_process,
            cap_table_id=cap_table_entry.id,
            investor_data=data,
            db=db
        )
        
        # Return investment data
        return {
            "status": "success",
            "message": "Investment created successfully",
            "investment": {
                "id": cap_table_entry.id,
                "group_id": cap_table_entry.co_investment_group_id,
                "investor_name": cap_table_entry.investor_name,
                "investor_email": cap_table_entry.investor_email,
                "investment_amount": cap_table_entry.investment_amount,
                "share_percentage": cap_table_entry.share_percentage,
                "kyc_status": cap_table_entry.kyc_status.value,
                "created_at": cap_table_entry.created_at.isoformat()
            },
            "next_steps": {
                "kyc_required": True,
                "message": "Please complete KYC verification to proceed with your investment"
            }
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error investing in group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error investing in group: {str(e)}")

@co_invest_router.post("/kyc/start/{cap_table_id}")
async def start_kyc_for_investor(
    cap_table_id: int = Path(..., description="Cap table entry ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start KYC process for an investor
    
    Args:
        cap_table_id: Cap table entry ID
        
    Returns:
        KYC process data
    """
    try:
        # Get cap table entry
        cap_table_entry = db.query(CapTable).filter(CapTable.id == cap_table_id).first()
        
        if not cap_table_entry:
            raise HTTPException(status_code=404, detail=f"Cap table entry not found: {cap_table_id}")
        
        # Check if KYC is already in progress or completed
        if cap_table_entry.kyc_status != KYCStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"KYC is already {cap_table_entry.kyc_status.value}")
        
        # Start KYC process
        kyc_data = await start_kyc_process(cap_table_id, {}, db)
        
        return {
            "status": "success",
            "message": "KYC process started successfully",
            "kyc_data": kyc_data
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error starting KYC process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting KYC process: {str(e)}")

@co_invest_router.get("/kyc/status/{cap_table_id}")
async def get_kyc_status(
    cap_table_id: int = Path(..., description="Cap table entry ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get KYC status for an investor
    
    Args:
        cap_table_id: Cap table entry ID
        
    Returns:
        KYC status data
    """
    try:
        # Get cap table entry
        cap_table_entry = db.query(CapTable).filter(CapTable.id == cap_table_id).first()
        
        if not cap_table_entry:
            raise HTTPException(status_code=404, detail=f"Cap table entry not found: {cap_table_id}")
        
        # Check if KYC ID exists
        if not cap_table_entry.kyc_idnow_id:
            return {
                "status": "success",
                "kyc_status": cap_table_entry.kyc_status.value,
                "message": "KYC process not started"
            }
        
        # Get KYC status from IDnow
        kyc_status_data = idnow_api.get_identification_status(cap_table_entry.kyc_idnow_id)
        
        # Update cap table entry if status has changed
        idnow_status = kyc_status_data.get("status")
        if idnow_status == "SUCCESSFUL":
            cap_table_entry.kyc_status = KYCStatus.APPROVED
            cap_table_entry.kyc_completed_at = kyc_status_data.get("completedAt")
            db.commit()
        elif idnow_status == "FAILED":
            cap_table_entry.kyc_status = KYCStatus.REJECTED
            cap_table_entry.kyc_rejection_reason = kyc_status_data.get("reason")
            db.commit()
        
        return {
            "status": "success",
            "kyc_status": cap_table_entry.kyc_status.value,
            "kyc_idnow_id": cap_table_entry.kyc_idnow_id,
            "kyc_completed_at": cap_table_entry.kyc_completed_at.isoformat() if cap_table_entry.kyc_completed_at else None,
            "kyc_rejection_reason": cap_table_entry.kyc_rejection_reason,
            "idnow_status": idnow_status
        }
    
    except Exception as e:
        logger.error(f"Error getting KYC status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting KYC status: {str(e)}")

@co_invest_router.post("/kyc/webhook")
async def kyc_webhook(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Webhook for IDnow KYC status updates
    
    Args:
        data: Webhook data from IDnow
        
    Returns:
        Webhook processing result
    """
    try:
        # Process webhook data
        processed_data = idnow_api.process_webhook(data)
        
        # Get identification ID
        identification_id = processed_data.get("identification_id")
        
        # Find cap table entry with this KYC ID
        cap_table_entry = db.query(CapTable).filter(CapTable.kyc_idnow_id == identification_id).first()
        
        if not cap_table_entry:
            logger.warning(f"Cap table entry not found for KYC ID: {identification_id}")
            return {
                "status": "error",
                "message": f"Cap table entry not found for KYC ID: {identification_id}"
            }
        
        # Update cap table entry based on webhook data
        status = processed_data.get("status")
        if status == "SUCCESSFUL":
            cap_table_entry.kyc_status = KYCStatus.APPROVED
            cap_table_entry.kyc_completed_at = data.get("completedAt")
            
            # Update compliance fields
            cap_table_entry.is_pep = processed_data.get("is_pep", False)
            cap_table_entry.is_sanctioned = processed_data.get("is_sanctioned", False)
            cap_table_entry.is_high_risk = processed_data.get("is_high_risk", False)
            
            # Check if investor should be rejected based on compliance
            if cap_table_entry.is_sanctioned:
                cap_table_entry.kyc_status = KYCStatus.REJECTED
                cap_table_entry.kyc_rejection_reason = "Investor is on sanctions list"
        
        elif status == "FAILED":
            cap_table_entry.kyc_status = KYCStatus.REJECTED
            cap_table_entry.kyc_rejection_reason = data.get("reason")
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "processed_data": processed_data
        }
    
    except Exception as e:
        logger.error(f"Error processing KYC webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing KYC webhook: {str(e)}")

async def start_kyc_process(cap_table_id: int, investor_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Start KYC process for an investor
    
    Args:
        cap_table_id: Cap table entry ID
        investor_data: Additional investor data
        db: Database session
        
    Returns:
        KYC process data
    """
    try:
        # Get cap table entry
        cap_table_entry = db.query(CapTable).filter(CapTable.id == cap_table_id).first()
        
        if not cap_table_entry:
            raise ValueError(f"Cap table entry not found: {cap_table_id}")
        
        # Get co-investment group
        group = db.query(CoInvestmentGroup).filter(CoInvestmentGroup.id == cap_table_entry.co_investment_group_id).first()
        
        if not group:
            raise ValueError(f"Co-investment group not found: {cap_table_entry.co_investment_group_id}")
        
        # Get property data
        property_data = await zoho_crm.get_property(group.property_id)
        
        # Prepare user data for IDnow
        user_data = {
            "firstName": investor_data.get("first_name", cap_table_entry.investor_name.split(" ")[0]),
            "lastName": investor_data.get("last_name", " ".join(cap_table_entry.investor_name.split(" ")[1:])),
            "email": cap_table_entry.investor_email,
            "mobilePhone": cap_table_entry.investor_phone,
            # Add other required fields from investor_data
        }
        
        # Create identification request
        identification_data = idnow_api.create_identification(user_data)
        
        # Update cap table entry
        cap_table_entry.kyc_status = KYCStatus.IN_PROGRESS
        cap_table_entry.kyc_idnow_id = identification_data.get("id")
        db.commit()
        
        return {
            "identification_id": identification_data.get("id"),
            "redirect_url": identification_data.get("redirectUrl"),
            "status": "in_progress"
        }
    
    except Exception as e:
        logger.error(f"Error starting KYC process: {str(e)}")
        raise
