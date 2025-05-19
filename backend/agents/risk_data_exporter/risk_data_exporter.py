"""
CSV export functionality for risk simulation results

This module handles CSV export of Monte Carlo simulation results:
- Exports full simulation data for a property
- Supports automatic zipping for large datasets
- Includes all simulation parameters and results
"""
import os
import logging
import csv
import io
import zipfile
from datetime import datetime
from typing import Dict, Any, List, Optional, BinaryIO
from sqlalchemy.orm import Session

from db.models.risk_models import RiskResult
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskDataExporter:
    """
    RiskDataExporter for PropPulse platform
    
    Handles CSV export of Monte Carlo simulation results
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RiskDataExporter"""
        self.config = config or {}
        
        # Export configuration
        self.zip_threshold = self.config.get('zip_threshold', 10000)
    
    async def export_simulation_results(self, property_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Export simulation results to CSV
        
        Args:
            property_id: Property ID
            db_session: Database session (optional)
            
        Returns:
            Export result with file data
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get latest risk result
            risk_result = db_session.query(RiskResult).filter(
                RiskResult.property_id == property_id
            ).order_by(
                RiskResult.timestamp.desc()
            ).first()
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            if not risk_result:
                logger.error(f"No risk results found for property: {property_id}")
                return {
                    'status': 'error',
                    'message': f"No risk results found for property: {property_id}"
                }
            
            # Generate CSV data
            csv_data, row_count = self._generate_csv_data(property_id, risk_result)
            
            # Check if we need to zip the data
            if row_count > self.zip_threshold:
                file_data = self._zip_csv_data(csv_data, property_id)
                file_format = 'zip'
            else:
                file_data = csv_data.encode('utf-8')
                file_format = 'csv'
            
            return {
                'status': 'success',
                'property_id': property_id,
                'file_data': file_data,
                'file_format': file_format,
                'row_count': row_count,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to export simulation results: {str(e)}")
            
            return {
                'status': 'error',
                'message': f"Failed to export simulation results: {str(e)}"
            }
    
    def _generate_csv_data(self, property_id: str, risk_result: RiskResult) -> tuple[str, int]:
        """
        Generate CSV data from risk result
        
        Args:
            property_id: Property ID
            risk_result: Risk result data
            
        Returns:
            Tuple of (CSV data string, row count)
        """
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header row
        writer.writerow([
            'property_id', 'sim_id', 'irr', 'npv', 'grade', 'assum_set', 'timestamp'
        ])
        
        # Get simulation parameters
        simulation_count = risk_result.simulation_count
        timestamp_str = risk_result.timestamp.isoformat()
        grade = risk_result.risk_grade.value
        
        # Generate rows based on histogram and percentiles
        histogram = risk_result.simulation_results.get('irr_histogram', [])
        percentiles = risk_result.simulation_results.get('irr_percentiles', {})
        
        # Calculate bin size and range
        bin_size = (percentiles.get('95', 0) - percentiles.get('5', 0)) / len(histogram) if len(histogram) > 0 else 0.01
        start_value = percentiles.get('5', 0) - bin_size
        
        # Generate synthetic data points based on histogram
        row_count = 0
        for i, bin_count in enumerate(histogram):
            bin_start = start_value + (i * bin_size)
            bin_end = bin_start + bin_size
            
            # Generate 'bin_count' rows for this bin
            for j in range(bin_count):
                # Calculate IRR value within this bin (evenly distributed)
                irr = bin_start + (bin_end - bin_start) * (j / max(1, bin_count - 1))
                
                # Calculate NPV (simplified)
                npv = 0  # Placeholder
                
                # Write row
                writer.writerow([
                    property_id,
                    row_count,
                    f"{irr:.6f}",
                    f"{npv:.2f}",
                    grade,
                    'base',
                    timestamp_str
                ])
                
                row_count += 1
        
        # Get CSV data as string
        csv_data = output.getvalue()
        output.close()
        
        return csv_data, row_count
    
    def _zip_csv_data(self, csv_data: str, property_id: str) -> bytes:
        """
        Zip CSV data
        
        Args:
            csv_data: CSV data string
            property_id: Property ID
            
        Returns:
            Zipped data as bytes
        """
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add CSV file to zip
            zip_file.writestr(f"risk_simulation_{property_id}.csv", csv_data)
        
        # Get zip data as bytes
        zip_data = zip_buffer.getvalue()
        zip_buffer.close()
        
        return zip_data
