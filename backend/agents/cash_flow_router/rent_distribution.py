"""
Rent distribution automation for PropPulse

This module provides endpoints and CLI commands for rent distribution,
with support for manual triggering and scheduled execution.
"""
import os
import logging
import argparse
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session

from db.database import get_db
from db.models.co_investment import CoInvestmentGroup, PayoutSchedule
from agents.cash_flow_router.cash_flow_router import CashFlowRouter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router_api = APIRouter(prefix="/router", tags=["Router"])

# Initialize CashFlowRouter
cash_flow_router = CashFlowRouter()

@router_api.post("/run")
async def run_router(
    background_tasks: BackgroundTasks,
    co_investment_group_id: Optional[int] = None,
    payout_schedule_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Manually trigger rent distribution
    
    Args:
        background_tasks: Background tasks
        co_investment_group_id: Co-investment group ID (optional)
        payout_schedule_id: Payout schedule ID (optional)
        db: Database session
        
    Returns:
        Router execution result
    """
    try:
        # If payout schedule ID is provided, execute specific payout
        if payout_schedule_id:
            # Execute in background to avoid blocking
            background_tasks.add_task(
                execute_specific_payout,
                payout_schedule_id=payout_schedule_id,
                db=db
            )
            
            return {
                "status": "success",
                "message": f"Payout execution started for schedule ID: {payout_schedule_id}",
                "task_type": "specific_payout"
            }
        
        # If co-investment group ID is provided, process all pending payouts for that group
        elif co_investment_group_id:
            # Execute in background to avoid blocking
            background_tasks.add_task(
                process_group_payouts,
                co_investment_group_id=co_investment_group_id,
                db=db
            )
            
            return {
                "status": "success",
                "message": f"Payout processing started for co-investment group ID: {co_investment_group_id}",
                "task_type": "group_payouts"
            }
        
        # Otherwise, process all pending payouts
        else:
            # Execute in background to avoid blocking
            background_tasks.add_task(
                process_all_payouts,
                db=db
            )
            
            return {
                "status": "success",
                "message": "Processing started for all pending payouts",
                "task_type": "all_payouts"
            }
    
    except Exception as e:
        logger.error(f"Error triggering router: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error triggering router: {str(e)}")

@router_api.post("/schedule")
async def schedule_payout(
    co_investment_group_id: int,
    amount: float,
    description: str,
    scheduled_date: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Schedule a payout for a co-investment group
    
    Args:
        co_investment_group_id: Co-investment group ID
        amount: Payout amount in AED
        description: Payout description
        scheduled_date: Scheduled date for payout (ISO format, optional)
        db: Database session
        
    Returns:
        Payout scheduling result
    """
    try:
        # Parse scheduled date if provided, otherwise use the 5th of next month
        if scheduled_date:
            scheduled_datetime = datetime.fromisoformat(scheduled_date)
        else:
            # Get current date
            current_date = datetime.now()
            
            # If current date is before the 5th, schedule for the 5th of current month
            if current_date.day < 5:
                scheduled_datetime = datetime(current_date.year, current_date.month, 5)
            # Otherwise, schedule for the 5th of next month
            else:
                # Get next month
                if current_date.month == 12:
                    next_month = 1
                    next_year = current_date.year + 1
                else:
                    next_month = current_date.month + 1
                    next_year = current_date.year
                
                scheduled_datetime = datetime(next_year, next_month, 5)
        
        # Schedule payout
        result = await cash_flow_router.schedule_payout(
            co_investment_group_id=co_investment_group_id,
            amount=amount,
            scheduled_date=scheduled_datetime,
            description=description,
            db_session=db
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error scheduling payout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scheduling payout: {str(e)}")

@router_api.get("/pending")
async def get_pending_payouts(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get pending payouts
    
    Args:
        db: Database session
        
    Returns:
        Pending payouts
    """
    try:
        # Check pending payouts
        result = await cash_flow_router.check_pending_payouts(db)
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting pending payouts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting pending payouts: {str(e)}")

async def execute_specific_payout(payout_schedule_id: int, db: Session) -> None:
    """
    Execute specific payout
    
    Args:
        payout_schedule_id: Payout schedule ID
        db: Database session
    """
    try:
        # Execute payout
        result = await cash_flow_router.execute_payout(payout_schedule_id, db)
        
        logger.info(f"Payout execution completed for schedule ID {payout_schedule_id}: {result}")
    
    except Exception as e:
        logger.error(f"Error executing payout for schedule ID {payout_schedule_id}: {str(e)}")

async def process_group_payouts(co_investment_group_id: int, db: Session) -> None:
    """
    Process all pending payouts for a co-investment group
    
    Args:
        co_investment_group_id: Co-investment group ID
        db: Database session
    """
    try:
        # Get current date
        current_date = datetime.now()
        
        # Get pending payout schedules for this group
        pending_schedules = db.query(PayoutSchedule).filter(
            PayoutSchedule.co_investment_group_id == co_investment_group_id,
            PayoutSchedule.status == "pending",
            PayoutSchedule.scheduled_date <= current_date
        ).all()
        
        # Process each pending schedule
        for schedule in pending_schedules:
            try:
                result = await cash_flow_router.execute_payout(schedule.id, db)
                logger.info(f"Payout execution completed for schedule ID {schedule.id}: {result}")
            except Exception as e:
                logger.error(f"Error executing payout for schedule ID {schedule.id}: {str(e)}")
        
        logger.info(f"Processed {len(pending_schedules)} pending payouts for co-investment group ID {co_investment_group_id}")
    
    except Exception as e:
        logger.error(f"Error processing payouts for co-investment group ID {co_investment_group_id}: {str(e)}")

async def process_all_payouts(db: Session) -> None:
    """
    Process all pending payouts
    
    Args:
        db: Database session
    """
    try:
        # Process pending payouts
        result = await cash_flow_router.process_pending_payouts(db)
        
        logger.info(f"All pending payouts processed: {result}")
    
    except Exception as e:
        logger.error(f"Error processing all pending payouts: {str(e)}")

async def main():
    """Main function for CLI execution"""
    parser = argparse.ArgumentParser(description='PropPulse Rent Distribution CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Schedule payout command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule a payout')
    schedule_parser.add_argument('--group-id', type=int, required=True, help='Co-investment group ID')
    schedule_parser.add_argument('--amount', type=float, required=True, help='Payout amount in AED')
    schedule_parser.add_argument('--description', required=True, help='Payout description')
    schedule_parser.add_argument('--date', help='Scheduled date (ISO format, e.g., 2025-06-05)')
    
    # Execute payout command
    execute_parser = subparsers.add_parser('execute', help='Execute a payout')
    execute_parser.add_argument('--schedule-id', type=int, required=True, help='Payout schedule ID')
    
    # Process group payouts command
    group_parser = subparsers.add_parser('process-group', help='Process all pending payouts for a group')
    group_parser.add_argument('--group-id', type=int, required=True, help='Co-investment group ID')
    
    # Process all payouts command
    subparsers.add_parser('process-all', help='Process all pending payouts')
    
    # Check pending payouts command
    subparsers.add_parser('check-pending', help='Check pending payouts')
    
    args = parser.parse_args()
    
    # Import database session
    from db.database import SessionLocal
    
    # Create database session
    db = SessionLocal()
    
    try:
        if args.command == 'schedule':
            # Parse scheduled date if provided
            scheduled_date = None
            if args.date:
                scheduled_date = datetime.fromisoformat(args.date)
            
            # Schedule payout
            result = await cash_flow_router.schedule_payout(
                co_investment_group_id=args.group_id,
                amount=args.amount,
                scheduled_date=scheduled_date or datetime.now() + timedelta(days=1),
                description=args.description,
                db_session=db
            )
            
            print(f"Payout scheduled: {result}")
        
        elif args.command == 'execute':
            # Execute payout
            result = await cash_flow_router.execute_payout(args.schedule_id, db)
            
            print(f"Payout executed: {result}")
        
        elif args.command == 'process-group':
            # Process group payouts
            await process_group_payouts(args.group_id, db)
            
            print(f"Group payouts processed for group ID: {args.group_id}")
        
        elif args.command == 'process-all':
            # Process all payouts
            result = await cash_flow_router.process_pending_payouts(db)
            
            print(f"All pending payouts processed: {result}")
        
        elif args.command == 'check-pending':
            # Check pending payouts
            result = await cash_flow_router.check_pending_payouts(db)
            
            print(f"Pending payouts: {result}")
        
        else:
            parser.print_help()
    
    finally:
        db.close()

if __name__ == '__main__':
    asyncio.run(main())
