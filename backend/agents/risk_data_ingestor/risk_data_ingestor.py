"""
RiskDataIngestor for PropPulse platform

This module handles ingestion of market data from various sources:
- STR Global API for RevPAR and ADR metrics
- AED swap curve / SOFR rates from Central Bank RSS
- Polygon rent index from DXB Rentals API
- Developer-specific default history from CSV

Data is stored in the market_metrics table for use in risk assessment.
"""
import os
import logging
import json
import csv
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import xml.etree.ElementTree as ET
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models.risk_models import MarketMetric, MetricType
from db.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskDataIngestor:
    """
    RiskDataIngestor for PropPulse platform
    
    Handles ingestion of market data from various sources and stores in market_metrics table
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RiskDataIngestor"""
        self.config = config or {}
        
        # Azure Key Vault configuration
        self.key_vault_name = self.config.get('key_vault_name', os.getenv('KEY_VAULT_NAME'))
        self.key_vault_url = f"https://{self.key_vault_name}.vault.azure.net"
        
        # Initialize Azure Key Vault client
        try:
            credential = DefaultAzureCredential()
            self.key_vault_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
            logger.info(f"Initialized Azure Key Vault client for {self.key_vault_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault client: {str(e)}")
            self.key_vault_client = None
        
        # API endpoints
        self.str_api_endpoint = self.config.get('str_api_endpoint', 'https://api.strglobal.com/v1/metrics')
        self.dxb_rentals_endpoint = self.config.get('dxb_rentals_endpoint', 'https://api.dxbrentals.ae/v2/index')
        self.aed_swap_curve_url = self.config.get('aed_swap_curve_url', 'https://www.centralbank.ae/en/rss/rates')
        
        # Developer default history CSV path
        self.developer_csv_path = self.config.get('developer_csv_path', '/data/developer_defaults.csv')
        
        # Historical backfill configuration
        self.historical_start_date = self.config.get('historical_start_date', '1970-01-01')
    
    async def get_secret(self, secret_name: str) -> str:
        """
        Get secret from Azure Key Vault
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value
        """
        try:
            if not self.key_vault_client:
                raise ValueError("Azure Key Vault client not initialized")
            
            secret = self.key_vault_client.get_secret(secret_name)
            return secret.value
        
        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {str(e)}")
            raise
    
    async def fetch_str_data(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch STR Global API data for RevPAR and ADR
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of STR data points
        """
        try:
            # Get API key from Key Vault
            api_key = await self.get_secret('STR_API_KEY')
            
            # Prepare request headers
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Prepare request parameters
            params = {
                'startDate': start_date,
                'endDate': end_date,
                'metrics': 'RevPAR,ADR',
                'regions': 'Dubai,RAK',
                'currency': 'AED',
                'frequency': 'daily'
            }
            
            # Make API request
            response = requests.get(
                self.str_api_endpoint,
                headers=headers,
                params=params
            )
            
            # Check response
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Extract metrics
            metrics = []
            for item in data.get('data', []):
                metrics.append({
                    'timestamp': item.get('date'),
                    'metric_type': 'str_revpar' if item.get('metric') == 'RevPAR' else 'str_adr',
                    'value': item.get('value'),
                    'region': item.get('region'),
                    'property_type': item.get('propertyType', 'all'),
                    'source': 'STR Global API',
                    'metadata': {
                        'currency': item.get('currency', 'AED'),
                        'sample_size': item.get('sampleSize')
                    }
                })
            
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to fetch STR data: {str(e)}")
            return []
    
    async def fetch_dxb_rentals_data(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch DXB Rentals API data for Polygon rent index
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of rent index data points
        """
        try:
            # Get API token from Key Vault
            api_token = await self.get_secret('DXB_RENTALS_TOKEN')
            
            # Prepare request headers
            headers = {
                'Authorization': f'Token {api_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare request parameters
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'index_type': 'rental',
                'areas': 'Dubai Marina,Palm Jumeirah,Downtown Dubai,Al Marjan Island',
                'property_types': 'apartment,villa'
            }
            
            # Make API request
            response = requests.get(
                self.dxb_rentals_endpoint,
                headers=headers,
                params=params
            )
            
            # Check response
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Extract metrics
            metrics = []
            for item in data.get('indices', []):
                metrics.append({
                    'timestamp': item.get('date'),
                    'metric_type': 'polygon_rent_index',
                    'metric_subtype': item.get('property_type'),
                    'value': item.get('index_value'),
                    'region': item.get('area'),
                    'property_type': item.get('property_type'),
                    'source': 'DXB Rentals API',
                    'metadata': {
                        'year_on_year_change': item.get('yoy_change'),
                        'month_on_month_change': item.get('mom_change'),
                        'sample_size': item.get('sample_size')
                    }
                })
            
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to fetch DXB Rentals data: {str(e)}")
            return []
    
    async def fetch_aed_swap_curve(self) -> List[Dict[str, Any]]:
        """
        Fetch AED swap curve and SOFR rates from Central Bank RSS
        
        Returns:
            List of swap curve and SOFR rate data points
        """
        try:
            # Make request to RSS feed
            response = requests.get(self.aed_swap_curve_url)
            
            # Check response
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            
            # Extract metrics
            metrics = []
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Find rate items
            for item in root.findall('.//item'):
                title = item.find('title').text
                description = item.find('description').text
                pub_date = item.find('pubDate').text
                
                # Parse publication date
                try:
                    pub_datetime = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %z')
                    pub_date_str = pub_datetime.strftime('%Y-%m-%d')
                except:
                    pub_date_str = current_date
                
                # Extract AED swap rates
                if 'AED Swap Rates' in title:
                    # Parse rates from description
                    rates = self._parse_swap_rates(description)
                    
                    for tenor, rate in rates.items():
                        metrics.append({
                            'timestamp': pub_date_str,
                            'metric_type': 'aed_swap_rate',
                            'metric_subtype': tenor,
                            'value': rate,
                            'region': 'UAE',
                            'source': 'Central Bank RSS',
                            'metadata': {
                                'title': title,
                                'publication_date': pub_date
                            }
                        })
                
                # Extract SOFR rates
                elif 'SOFR' in title:
                    # Parse rates from description
                    rates = self._parse_sofr_rates(description)
                    
                    for tenor, rate in rates.items():
                        metrics.append({
                            'timestamp': pub_date_str,
                            'metric_type': 'sofr_rate',
                            'metric_subtype': tenor,
                            'value': rate,
                            'region': 'US',
                            'source': 'Central Bank RSS',
                            'metadata': {
                                'title': title,
                                'publication_date': pub_date
                            }
                        })
            
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to fetch AED swap curve: {str(e)}")
            return []
    
    def _parse_swap_rates(self, description: str) -> Dict[str, float]:
        """
        Parse AED swap rates from description
        
        Args:
            description: Rate description text
            
        Returns:
            Dictionary of tenor to rate
        """
        rates = {}
        
        try:
            # Split description into lines
            lines = description.strip().split('\n')
            
            # Parse each line
            for line in lines:
                if ':' in line:
                    tenor, rate_str = line.split(':', 1)
                    tenor = tenor.strip()
                    rate_str = rate_str.strip().replace('%', '')
                    
                    try:
                        rate = float(rate_str)
                        rates[tenor] = rate
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Failed to parse swap rates: {str(e)}")
        
        return rates
    
    def _parse_sofr_rates(self, description: str) -> Dict[str, float]:
        """
        Parse SOFR rates from description
        
        Args:
            description: Rate description text
            
        Returns:
            Dictionary of tenor to rate
        """
        rates = {}
        
        try:
            # Split description into lines
            lines = description.strip().split('\n')
            
            # Parse each line
            for line in lines:
                if ':' in line:
                    tenor, rate_str = line.split(':', 1)
                    tenor = tenor.strip()
                    rate_str = rate_str.strip().replace('%', '')
                    
                    try:
                        rate = float(rate_str)
                        rates[tenor] = rate
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Failed to parse SOFR rates: {str(e)}")
        
        return rates
    
    async def parse_developer_defaults(self, csv_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Parse developer default history from CSV
        
        Args:
            csv_path: Path to CSV file (optional)
            
        Returns:
            List of developer default data points
        """
        try:
            # Use provided path or default
            csv_path = csv_path or self.developer_csv_path
            
            # Check if file exists
            if not os.path.isfile(csv_path):
                logger.error(f"Developer default CSV file not found: {csv_path}")
                return []
            
            # Parse CSV file
            metrics = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Extract fields
                        developer_id = row.get('developer_id')
                        developer_name = row.get('developer_name')
                        default_date = row.get('default_date')
                        severity_score = row.get('severity_score')
                        notes = row.get('notes')
                        
                        # Validate required fields
                        if not all([developer_id, developer_name, default_date, severity_score]):
                            logger.warning(f"Skipping row with missing required fields: {row}")
                            continue
                        
                        # Convert severity score to float
                        try:
                            severity_score = float(severity_score)
                        except:
                            logger.warning(f"Invalid severity score: {severity_score}")
                            continue
                        
                        # Add metric
                        metrics.append({
                            'timestamp': default_date,
                            'metric_type': 'developer_default',
                            'value': severity_score,
                            'developer_id': developer_id,
                            'notes': notes,
                            'source': 'Developer Default CSV',
                            'metadata': {
                                'developer_name': developer_name
                            }
                        })
                    
                    except Exception as e:
                        logger.error(f"Failed to parse row: {str(e)}")
            
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to parse developer defaults: {str(e)}")
            return []
    
    async def store_metrics(self, metrics: List[Dict[str, Any]], db_session: Session) -> Tuple[int, int]:
        """
        Store metrics in database
        
        Args:
            metrics: List of metrics to store
            db_session: Database session
            
        Returns:
            Tuple of (inserted_count, updated_count)
        """
        inserted_count = 0
        updated_count = 0
        
        try:
            for metric_data in metrics:
                try:
                    # Convert timestamp to datetime if string
                    if isinstance(metric_data.get('timestamp'), str):
                        metric_data['timestamp'] = datetime.fromisoformat(metric_data['timestamp'].replace('Z', '+00:00'))
                    
                    # Check if metric already exists
                    existing_metric = db_session.query(MarketMetric).filter(
                        MarketMetric.timestamp == metric_data['timestamp'],
                        MarketMetric.metric_type == metric_data['metric_type'],
                        MarketMetric.metric_subtype == metric_data.get('metric_subtype'),
                        MarketMetric.region == metric_data.get('region'),
                        MarketMetric.developer_id == metric_data.get('developer_id')
                    ).first()
                    
                    if existing_metric:
                        # Update existing metric
                        existing_metric.value = metric_data['value']
                        existing_metric.property_type = metric_data.get('property_type')
                        existing_metric.source = metric_data.get('source')
                        existing_metric.notes = metric_data.get('notes')
                        existing_metric.metadata = metric_data.get('metadata')
                        existing_metric.updated_at = datetime.utcnow()
                        updated_count += 1
                    else:
                        # Create new metric
                        new_metric = MarketMetric(
                            timestamp=metric_data['timestamp'],
                            metric_type=metric_data['metric_type'],
                            metric_subtype=metric_data.get('metric_subtype'),
                            value=metric_data['value'],
                            region=metric_data.get('region'),
                            property_type=metric_data.get('property_type'),
                            developer_id=metric_data.get('developer_id'),
                            source=metric_data.get('source'),
                            notes=metric_data.get('notes'),
                            metadata=metric_data.get('metadata')
                        )
                        db_session.add(new_metric)
                        inserted_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to store metric: {str(e)}")
            
            # Commit changes
            db_session.commit()
            
            return inserted_count, updated_count
        
        except Exception as e:
            logger.error(f"Failed to store metrics: {str(e)}")
            db_session.rollback()
            return 0, 0
    
    async def ingest_daily_data(self, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Ingest daily market data
        
        Args:
            db_session: Database session (optional)
            
        Returns:
            Ingestion result
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get date range for daily ingestion
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Fetch STR data
            str_metrics = await self.fetch_str_data(start_date, end_date)
            logger.info(f"Fetched {len(str_metrics)} STR metrics")
            
            # Fetch DXB Rentals data
            dxb_metrics = await self.fetch_dxb_rentals_data(start_date, end_date)
            logger.info(f"Fetched {len(dxb_metrics)} DXB Rentals metrics")
            
            # Fetch AED swap curve
            swap_metrics = await self.fetch_aed_swap_curve()
            logger.info(f"Fetched {len(swap_metrics)} swap curve metrics")
            
            # Combine all metrics
            all_metrics = str_metrics + dxb_metrics + swap_metrics
            
            # Store metrics
            inserted, updated = await self.store_metrics(all_metrics, db_session)
            logger.info(f"Stored {inserted} new metrics, updated {updated} existing metrics")
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return {
                'status': 'success',
                'message': f"Daily data ingestion completed successfully",
                'metrics_fetched': len(all_metrics),
                'metrics_inserted': inserted,
                'metrics_updated': updated,
                'date_range': f"{start_date} to {end_date}"
            }
        
        except Exception as e:
            logger.error(f"Failed to ingest daily data: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to ingest daily data: {str(e)}"
            }
    
    async def ingest_historical_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Ingest historical market data
        
        Args:
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            db_session: Database session (optional)
            
        Returns:
            Ingestion result
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Get date range for historical ingestion
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or self.historical_start_date
            
            # Fetch STR data
            str_metrics = await self.fetch_str_data(start_date, end_date)
            logger.info(f"Fetched {len(str_metrics)} historical STR metrics")
            
            # Fetch DXB Rentals data
            dxb_metrics = await self.fetch_dxb_rentals_data(start_date, end_date)
            logger.info(f"Fetched {len(dxb_metrics)} historical DXB Rentals metrics")
            
            # Parse developer defaults
            developer_metrics = await self.parse_developer_defaults()
            logger.info(f"Parsed {len(developer_metrics)} developer default metrics")
            
            # Combine all metrics
            all_metrics = str_metrics + dxb_metrics + developer_metrics
            
            # Store metrics
            inserted, updated = await self.store_metrics(all_metrics, db_session)
            logger.info(f"Stored {inserted} new historical metrics, updated {updated} existing metrics")
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return {
                'status': 'success',
                'message': f"Historical data ingestion completed successfully",
                'metrics_fetched': len(all_metrics),
                'metrics_inserted': inserted,
                'metrics_updated': updated,
                'date_range': f"{start_date} to {end_date}"
            }
        
        except Exception as e:
            logger.error(f"Failed to ingest historical data: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return {
                'status': 'error',
                'message': f"Failed to ingest historical data: {str(e)}"
            }
    
    async def get_latest_metrics(self, metric_type: Optional[str] = None, region: Optional[str] = None, db_session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Get latest metrics from database
        
        Args:
            metric_type: Filter by metric type (optional)
            region: Filter by region (optional)
            db_session: Database session (optional)
            
        Returns:
            List of latest metrics
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Build query
            query = db_session.query(MarketMetric)
            
            # Apply filters
            if metric_type:
                query = query.filter(MarketMetric.metric_type == metric_type)
            
            if region:
                query = query.filter(MarketMetric.region == region)
            
            # Get latest metrics
            subquery = db_session.query(
                MarketMetric.metric_type,
                MarketMetric.metric_subtype,
                MarketMetric.region,
                MarketMetric.developer_id,
                func.max(MarketMetric.timestamp).label('max_timestamp')
            ).group_by(
                MarketMetric.metric_type,
                MarketMetric.metric_subtype,
                MarketMetric.region,
                MarketMetric.developer_id
            ).subquery()
            
            query = db_session.query(MarketMetric).join(
                subquery,
                (MarketMetric.metric_type == subquery.c.metric_type) &
                (MarketMetric.metric_subtype == subquery.c.metric_subtype) &
                (MarketMetric.region == subquery.c.region) &
                (MarketMetric.developer_id == subquery.c.developer_id) &
                (MarketMetric.timestamp == subquery.c.max_timestamp)
            )
            
            # Execute query
            metrics = query.all()
            
            # Convert to dictionaries
            result = []
            for metric in metrics:
                result.append({
                    'id': metric.id,
                    'timestamp': metric.timestamp.isoformat(),
                    'metric_type': metric.metric_type,
                    'metric_subtype': metric.metric_subtype,
                    'value': metric.value,
                    'region': metric.region,
                    'property_type': metric.property_type,
                    'developer_id': metric.developer_id,
                    'source': metric.source,
                    'notes': metric.notes,
                    'metadata': metric.metadata
                })
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to get latest metrics: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return []
    
    async def get_metric_history(self, metric_type: str, start_date: Optional[str] = None, end_date: Optional[str] = None, region: Optional[str] = None, db_session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Get metric history from database
        
        Args:
            metric_type: Metric type
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            region: Filter by region (optional)
            db_session: Database session (optional)
            
        Returns:
            List of metric history
        """
        try:
            # Create database session if not provided
            if db_session is None:
                db_session = next(get_db())
                close_session = True
            else:
                close_session = False
            
            # Parse dates
            if start_date:
                start_datetime = datetime.fromisoformat(start_date)
            else:
                start_datetime = datetime(1970, 1, 1)
            
            if end_date:
                end_datetime = datetime.fromisoformat(end_date)
            else:
                end_datetime = datetime.now()
            
            # Build query
            query = db_session.query(MarketMetric).filter(
                MarketMetric.metric_type == metric_type,
                MarketMetric.timestamp >= start_datetime,
                MarketMetric.timestamp <= end_datetime
            )
            
            # Apply region filter
            if region:
                query = query.filter(MarketMetric.region == region)
            
            # Order by timestamp
            query = query.order_by(MarketMetric.timestamp)
            
            # Execute query
            metrics = query.all()
            
            # Convert to dictionaries
            result = []
            for metric in metrics:
                result.append({
                    'id': metric.id,
                    'timestamp': metric.timestamp.isoformat(),
                    'metric_type': metric.metric_type,
                    'metric_subtype': metric.metric_subtype,
                    'value': metric.value,
                    'region': metric.region,
                    'property_type': metric.property_type,
                    'developer_id': metric.developer_id,
                    'source': metric.source,
                    'notes': metric.notes,
                    'metadata': metric.metadata
                })
            
            # Close session if created here
            if close_session:
                db_session.close()
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to get metric history: {str(e)}")
            
            # Close session if created here
            if db_session is not None and close_session:
                db_session.close()
            
            return []
