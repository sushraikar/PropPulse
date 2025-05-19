"""
Google Places API integration for PropPulse
"""
import os
import requests
import logging
from typing import Dict, Any, List, Optional, Union
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GooglePlacesAPI:
    """
    Google Places API integration for location-based services
    
    Provides methods for:
    - Geocoding addresses to coordinates
    - Searching for nearby places by type
    - Getting place details
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Google Places API client"""
        self.config = config or {}
        
        # API endpoints
        self.places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        self.geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.place_details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        # Get API key
        self.api_key = self._get_api_key()
        
        # Default search radius (in meters)
        self.default_radius = 3000
    
    def _get_api_key(self) -> str:
        """
        Get Google Places API key from environment or Azure Key Vault
        
        Returns:
            API key string
        """
        # First try environment variable
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        
        if api_key:
            return api_key
        
        # If not in environment, try to get from Azure Key Vault
        # This assumes the application has managed identity access to Key Vault
        try:
            key_vault_name = os.getenv('KEY_VAULT_NAME')
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net"
            
            credential = DefaultAzureCredential()
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            api_key = secret_client.get_secret("GOOGLE_PLACES_API_KEY").value
            return api_key
        except Exception as e:
            logger.error(f"Error retrieving API key from Key Vault: {str(e)}")
            
            # For development/testing, use a placeholder key
            if os.getenv('ENVIRONMENT') == 'development':
                return "PLACEHOLDER_API_KEY_FOR_DEVELOPMENT"
            
            raise ValueError("Google Places API key not found")
    
    def geocode(self, address: str) -> Optional[tuple]:
        """
        Geocode address to coordinates
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        params = {
            "address": address,
            "key": self.api_key
        }
        
        try:
            response = requests.get(self.geocode_url, params=params)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                location = data['results'][0]['geometry']['location']
                return location['lat'], location['lng']
            
            if data['status'] != 'ZERO_RESULTS':
                logger.warning(f"Google Geocoding API error: {data['status']}")
            
            return None
        except Exception as e:
            logger.error(f"Error geocoding address: {str(e)}")
            return None
    
    def search_nearby(
        self, 
        latitude: float, 
        longitude: float, 
        place_type: str,
        radius: Optional[int] = None,
        keyword: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            place_type: Place type (e.g., 'restaurant', 'hotel')
            radius: Search radius in meters (default: 3000)
            keyword: Additional search keyword
            min_price: Minimum price level (0-4)
            max_price: Maximum price level (0-4)
            
        Returns:
            List of place results
        """
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius or self.default_radius,
            "type": place_type,
            "key": self.api_key
        }
        
        if keyword:
            params["keyword"] = keyword
        
        if min_price is not None:
            params["minprice"] = min_price
        
        if max_price is not None:
            params["maxprice"] = max_price
        
        try:
            response = requests.get(self.places_url, params=params)
            data = response.json()
            
            if data['status'] != 'OK':
                if data['status'] == 'ZERO_RESULTS':
                    return []
                
                if data['status'] in ['OVER_QUERY_LIMIT', 'REQUEST_DENIED']:
                    logger.warning(f"Google Places API error: {data['status']}")
                    return []
                
                raise ValueError(f"Google Places API error: {data['status']}")
            
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error searching nearby places: {str(e)}")
            return []
    
    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a place
        
        Args:
            place_id: Google Place ID
            
        Returns:
            Place details dictionary or None if request fails
        """
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,geometry,rating,url,website,formatted_phone_number,opening_hours,price_level,photo",
            "key": self.api_key
        }
        
        try:
            response = requests.get(self.place_details_url, params=params)
            data = response.json()
            
            if data['status'] != 'OK':
                logger.warning(f"Google Place Details API error: {data['status']}")
                return None
            
            return data.get('result')
        except Exception as e:
            logger.error(f"Error getting place details: {str(e)}")
            return None
    
    def is_api_key_valid(self) -> bool:
        """
        Check if the API key is valid
        
        Returns:
            True if API key is valid, False otherwise
        """
        # Try a simple geocoding request to validate the key
        params = {
            "address": "Dubai, UAE",
            "key": self.api_key
        }
        
        try:
            response = requests.get(self.geocode_url, params=params)
            data = response.json()
            
            return data['status'] not in ['REQUEST_DENIED', 'INVALID_REQUEST']
        except Exception:
            return False
