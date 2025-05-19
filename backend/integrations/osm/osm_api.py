"""
OpenStreetMap API integration for PropPulse
"""
import requests
import logging
from typing import Dict, Any, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenStreetMapAPI:
    """
    OpenStreetMap API integration for location-based services
    
    Provides methods for:
    - Geocoding addresses to coordinates
    - Searching for nearby places by type
    - Fallback for Google Places API
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the OpenStreetMap API client"""
        self.config = config or {}
        
        # API endpoints
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        
        # User agent (required by OSM)
        self.user_agent = config.get('user_agent', 'PropPulse/1.0')
        
        # Default search radius (in meters)
        self.default_radius = 3000
    
    def geocode(self, address: str) -> Optional[tuple]:
        """
        Geocode address to coordinates
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.get(self.nominatim_url, params=params, headers=headers)
            data = response.json()
            
            if data and len(data) > 0:
                return float(data[0]['lat']), float(data[0]['lon'])
            
            return None
        except Exception as e:
            logger.error(f"Error geocoding address with OSM: {str(e)}")
            return None
    
    def search_nearby(
        self, 
        latitude: float, 
        longitude: float, 
        place_type: str,
        radius: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places using Overpass API
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            place_type: Place type (e.g., 'restaurant', 'hotel')
            radius: Search radius in meters (default: 3000)
            
        Returns:
            List of place results
        """
        # Map common place types to OSM tags
        osm_tags = self._map_place_type_to_osm_tags(place_type)
        if not osm_tags:
            logger.warning(f"Unsupported place type for OSM: {place_type}")
            return []
        
        # Build Overpass query
        search_radius = radius or self.default_radius
        search_radius_km = search_radius / 1000  # Convert to km for query
        
        # Build tag filters
        tag_filters = []
        for key, value in osm_tags:
            if value:
                tag_filters.append(f'["{key}"="{value}"]')
            else:
                tag_filters.append(f'["{key}"]')
        
        tag_filter_str = ''.join(tag_filters)
        
        # Overpass query
        query = f"""
        [out:json];
        (
          node{tag_filter_str}(around:{search_radius_km},{latitude},{longitude});
          way{tag_filter_str}(around:{search_radius_km},{latitude},{longitude});
          relation{tag_filter_str}(around:{search_radius_km},{latitude},{longitude});
        );
        out center;
        """
        
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.post(self.overpass_url, data={"data": query}, headers=headers)
            data = response.json()
            
            results = []
            for element in data.get('elements', []):
                # Get coordinates
                if element['type'] == 'node':
                    lat = element['lat']
                    lon = element['lon']
                else:  # way or relation
                    if 'center' not in element:
                        continue
                    lat = element['center']['lat']
                    lon = element['center']['lon']
                
                # Get name
                name = element.get('tags', {}).get('name', 'Unnamed')
                
                results.append({
                    'id': element['id'],
                    'type': element['type'],
                    'name': name,
                    'latitude': lat,
                    'longitude': lon,
                    'tags': element.get('tags', {})
                })
            
            return results
        except Exception as e:
            logger.error(f"Error searching nearby places with OSM: {str(e)}")
            return []
    
    def _map_place_type_to_osm_tags(self, place_type: str) -> List[tuple]:
        """
        Map Google Places API place types to OSM tags
        
        Args:
            place_type: Google Places API place type
            
        Returns:
            List of (key, value) tuples for OSM tags
        """
        mapping = {
            'casino': [('amenity', 'casino')],
            'lodging': [('tourism', 'hotel')],
            'hotel': [('tourism', 'hotel')],
            'beach': [('natural', 'beach')],
            'marina': [('leisure', 'marina')],
            'restaurant': [('amenity', 'restaurant')],
            'hospital': [('amenity', 'hospital')],
            'school': [('amenity', 'school')],
            'golf_course': [('leisure', 'golf_course')],
            'amusement_park': [('leisure', 'water_park'), ('leisure', 'amusement_park')],
            'water_park': [('leisure', 'water_park')]
        }
        
        return mapping.get(place_type, [])
