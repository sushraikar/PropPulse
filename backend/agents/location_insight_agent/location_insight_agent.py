"""
LocationInsightAgent for PropPulse
Responsible for gathering location-based insights for properties
"""
from typing import Dict, Any, List, Optional, Union
import os
import json
import asyncio
import requests
import math
from datetime import datetime, date
import logging
from enum import Enum

# Import base agent
from agents.base_agent import BaseAgent
from integrations.zoho.zoho_crm import ZohoCRM
from db.models.property import ViewOrientation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class POICategory(str, Enum):
    """POI Categories in order of priority"""
    CASINO = "casino"
    HOTEL = "lodging"
    BEACH = "beach"
    MARINA = "marina"
    RESTAURANT = "restaurant"
    HOSPITAL = "hospital"
    SCHOOL = "school"
    GOLF = "golf_course"
    WATER_PARK = "amusement_park"

class LocationInsightAgent(BaseAgent):
    """
    LocationInsightAgent gathers location-based insights for properties.
    
    Responsibilities:
    - Fetch lat/lng from Zoho CRM
    - Call Google Places API (with OSM fallback)
    - Compute distances to POIs
    - Calculate sunset/sunrise visibility
    - Generate location insights summary
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the LocationInsightAgent"""
        super().__init__(config)
        
        # Initialize Zoho CRM client
        self.zoho_crm = ZohoCRM(config.get('zoho_config'))
        
        # Google Places API configuration
        self.google_api_key = self._get_google_api_key()
        self.google_places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        
        # OpenStreetMap API configuration (fallback)
        self.osm_url = "https://nominatim.openstreetmap.org/search"
        
        # Wynn Casino site coordinates (Al Marjan Island, RAK)
        self.wynn_casino_lat = 25.7406
        self.wynn_casino_lng = 55.8350
        
        # Sunset/Sunrise azimuth range
        self.sunset_azimuth_range = (290, 305)  # degrees
        
        # POI search radius (in meters)
        self.poi_radius = 3000
        
        # POI categories in priority order
        self.poi_categories = [
            POICategory.CASINO,
            POICategory.HOTEL,
            POICategory.BEACH,
            POICategory.MARINA,
            POICategory.RESTAURANT,
            POICategory.HOSPITAL,
            POICategory.SCHOOL,
            POICategory.GOLF,
            POICategory.WATER_PARK
        ]
    
    def _get_google_api_key(self) -> str:
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
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
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
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process property to gather location insights
        
        Args:
            input_data: Dictionary containing:
                - property_id: Zoho CRM Property ID
                
        Returns:
            Dict containing:
                - property_id: Property ID
                - latitude: Property latitude
                - longitude: Property longitude
                - poi_data: Points of interest data
                - wynn_casino_distance: Distance to Wynn Casino site (km)
                - sunset_view_score: Sunset view score (0-100)
                - summary: Location insights summary (300 words)
                - translations: Summaries in Arabic, French, Hindi
                - status: Processing status
        """
        # Validate input
        if 'property_id' not in input_data:
            return {
                'status': 'error',
                'error': 'Missing required input: property_id'
            }
        
        property_id = input_data['property_id']
        
        try:
            # Fetch property data from Zoho CRM
            property_data = await self._fetch_property_from_zoho(property_id)
            
            # Extract or geocode coordinates
            latitude, longitude = await self._get_property_coordinates(property_data)
            
            if not latitude or not longitude:
                return {
                    'status': 'error',
                    'error': f"Could not determine coordinates for property {property_id}"
                }
            
            # Get nearby POIs
            poi_data = await self._get_nearby_pois(latitude, longitude)
            
            # Calculate distance to Wynn Casino site
            wynn_casino_distance = self._calculate_distance(
                latitude, longitude, self.wynn_casino_lat, self.wynn_casino_lng
            )
            
            # Determine view orientation
            view_orientation = self._determine_view_orientation(property_data)
            
            # Calculate sunset view score
            floor = self._extract_floor_number(property_data)
            sunset_view_score = self._calculate_sunset_view_score(view_orientation, floor)
            
            # Generate summary
            summary = self._generate_location_summary(
                property_data, latitude, longitude, poi_data, 
                wynn_casino_distance, sunset_view_score
            )
            
            # Generate translations
            translations = await self._generate_translations(summary)
            
            return {
                'status': 'success',
                'property_id': property_id,
                'latitude': latitude,
                'longitude': longitude,
                'poi_data': poi_data,
                'view_orientation': view_orientation.value if view_orientation else None,
                'floor': floor,
                'wynn_casino_distance': wynn_casino_distance,
                'sunset_view_score': sunset_view_score,
                'summary': summary,
                'translations': translations
            }
            
        except Exception as e:
            logger.error(f"Error processing location insights: {str(e)}")
            return {
                'status': 'error',
                'error': f"Error processing location insights: {str(e)}"
            }
    
    async def _fetch_property_from_zoho(self, property_id: str) -> Dict[str, Any]:
        """
        Fetch property data from Zoho CRM
        
        Args:
            property_id: Zoho CRM Property ID
            
        Returns:
            Property data dictionary
        """
        try:
            property_data = await self.zoho_crm.get_property(property_id)
            return property_data
        except Exception as e:
            logger.error(f"Error fetching property from Zoho CRM: {str(e)}")
            raise ValueError(f"Could not fetch property {property_id} from Zoho CRM")
    
    async def _get_property_coordinates(self, property_data: Dict[str, Any]) -> tuple:
        """
        Get property coordinates from data or geocode if needed
        
        Args:
            property_data: Property data from Zoho CRM
            
        Returns:
            Tuple of (latitude, longitude)
        """
        # Check if coordinates are already in the data
        if 'latitude' in property_data and 'longitude' in property_data:
            lat = property_data.get('latitude')
            lng = property_data.get('longitude')
            
            if lat and lng:
                return float(lat), float(lng)
        
        # If not, try to geocode based on address
        address_components = []
        if property_data.get('Project_Name'):
            address_components.append(property_data.get('Project_Name'))
        
        if property_data.get('Tower_Phase'):
            address_components.append(property_data.get('Tower_Phase'))
            
        # For Uno Luxe, we know it's on Al Marjan Island, RAK
        address_components.extend(["Al Marjan Island", "Ras Al Khaimah", "UAE"])
        
        address = ", ".join(address_components)
        
        # Try Google Geocoding first
        try:
            coordinates = await self._google_geocode(address)
            if coordinates:
                return coordinates
        except Exception as e:
            logger.warning(f"Google geocoding failed: {str(e)}, trying OSM fallback")
        
        # Fallback to OpenStreetMap
        try:
            coordinates = await self._osm_geocode(address)
            if coordinates:
                return coordinates
        except Exception as e:
            logger.error(f"OSM geocoding failed: {str(e)}")
        
        # If all geocoding fails, return None
        return None, None
    
    async def _google_geocode(self, address: str) -> tuple:
        """
        Geocode address using Google Geocoding API
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude)
        """
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": self.google_api_key
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] == 'OK' and data['results']:
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        
        return None, None
    
    async def _osm_geocode(self, address: str) -> tuple:
        """
        Geocode address using OpenStreetMap Nominatim API
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude)
        """
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        headers = {
            "User-Agent": "PropPulse/1.0"  # OSM requires a user agent
        }
        
        response = requests.get(self.osm_url, params=params, headers=headers)
        data = response.json()
        
        if data and len(data) > 0:
            return float(data[0]['lat']), float(data[0]['lon'])
        
        return None, None
    
    async def _get_nearby_pois(self, latitude: float, longitude: float) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get nearby points of interest using Google Places API
        
        Args:
            latitude: Property latitude
            longitude: Property longitude
            
        Returns:
            Dictionary of POI categories with lists of POIs
        """
        poi_results = {}
        
        for category in self.poi_categories:
            try:
                # Try Google Places API first
                pois = await self._google_places_search(latitude, longitude, category)
                
                # If Google Places fails or returns no results, try OSM
                if not pois:
                    pois = await self._osm_places_search(latitude, longitude, category)
                
                if pois:
                    poi_results[category] = pois
            except Exception as e:
                logger.warning(f"Error fetching {category} POIs: {str(e)}")
        
        return poi_results
    
    async def _google_places_search(self, latitude: float, longitude: float, category: str) -> List[Dict[str, Any]]:
        """
        Search for places using Google Places API
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            category: Place category/type
            
        Returns:
            List of places
        """
        params = {
            "location": f"{latitude},{longitude}",
            "radius": self.poi_radius,
            "type": category,
            "key": self.google_api_key
        }
        
        # For restaurants, add price level filter (≥4)
        if category == POICategory.RESTAURANT:
            params["minprice"] = 4
        
        response = requests.get(self.google_places_url, params=params)
        data = response.json()
        
        if data['status'] != 'OK':
            if data['status'] == 'ZERO_RESULTS':
                return []
            
            if data['status'] in ['OVER_QUERY_LIMIT', 'REQUEST_DENIED']:
                logger.warning(f"Google Places API error: {data['status']}")
                return []
            
            raise ValueError(f"Google Places API error: {data['status']}")
        
        results = []
        for place in data.get('results', [])[:10]:  # Limit to top 10
            place_lat = place['geometry']['location']['lat']
            place_lng = place['geometry']['location']['lng']
            
            distance = self._calculate_distance(latitude, longitude, place_lat, place_lng)
            
            results.append({
                'name': place['name'],
                'place_id': place.get('place_id'),
                'latitude': place_lat,
                'longitude': place_lng,
                'distance': distance,
                'rating': place.get('rating'),
                'user_ratings_total': place.get('user_ratings_total'),
                'vicinity': place.get('vicinity')
            })
        
        # Sort by distance
        results.sort(key=lambda x: x['distance'])
        
        return results
    
    async def _osm_places_search(self, latitude: float, longitude: float, category: str) -> List[Dict[str, Any]]:
        """
        Search for places using OpenStreetMap Nominatim API (fallback)
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            category: Place category/type
            
        Returns:
            List of places
        """
        # Map Google Places categories to OSM amenities/tags
        category_mapping = {
            POICategory.CASINO: "amenity=casino",
            POICategory.HOTEL: "tourism=hotel",
            POICategory.BEACH: "natural=beach",
            POICategory.MARINA: "leisure=marina",
            POICategory.RESTAURANT: "amenity=restaurant",
            POICategory.HOSPITAL: "amenity=hospital",
            POICategory.SCHOOL: "amenity=school",
            POICategory.GOLF: "leisure=golf_course",
            POICategory.WATER_PARK: "leisure=water_park"
        }
        
        osm_category = category_mapping.get(category, "")
        if not osm_category:
            return []
        
        params = {
            "format": "json",
            "limit": 10,
            "radius": self.poi_radius,
            "lat": latitude,
            "lon": longitude
        }
        
        # Add the OSM category/tag
        tag_key, tag_value = osm_category.split('=')
        params[tag_key] = tag_value
        
        headers = {
            "User-Agent": "PropPulse/1.0"  # OSM requires a user agent
        }
        
        response = requests.get(self.osm_url, params=params, headers=headers)
        data = response.json()
        
        results = []
        for place in data:
            place_lat = float(place['lat'])
            place_lng = float(place['lon'])
            
            distance = self._calculate_distance(latitude, longitude, place_lat, place_lng)
            
            results.append({
                'name': place.get('display_name', '').split(',')[0],
                'place_id': place.get('place_id'),
                'latitude': place_lat,
                'longitude': place_lng,
                'distance': distance,
                'osm_type': place.get('osm_type'),
                'osm_id': place.get('osm_id')
            })
        
        # Sort by distance
        results.sort(key=lambda x: x['distance'])
        
        return results
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        
        Args:
            lat1: First point latitude
            lon1: First point longitude
            lat2: Second point latitude
            lon2: Second point longitude
            
        Returns:
            Distance in kilometers
        """
        # Earth radius in kilometers
        R = 6371.0
        
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        
        return round(distance, 2)
    
    def _determine_view_orientation(self, property_data: Dict[str, Any]) -> Optional[ViewOrientation]:
        """
        Determine property view orientation
        
        Args:
            property_data: Property data from Zoho CRM
            
        Returns:
            ViewOrientation enum value
        """
        # Check if view orientation is already specified
        if 'view_orientation' in property_data:
            view_str = property_data['view_orientation']
            try:
                return ViewOrientation(view_str.lower())
            except (ValueError, AttributeError):
                pass
        
        # Try to determine from view description
        view_desc = property_data.get('view', '').lower()
        
        orientation_keywords = {
            ViewOrientation.NORTH: ['north', 'northern'],
            ViewOrientation.NORTHEAST: ['northeast', 'north east', 'north-east'],
            ViewOrientation.EAST: ['east', 'eastern'],
            ViewOrientation.SOUTHEAST: ['southeast', 'south east', 'south-east'],
            ViewOrientation.SOUTH: ['south', 'southern'],
            ViewOrientation.SOUTHWEST: ['southwest', 'south west', 'south-west'],
            ViewOrientation.WEST: ['west', 'western', 'sunset'],
            ViewOrientation.NORTHWEST: ['northwest', 'north west', 'north-west']
        }
        
        for orientation, keywords in orientation_keywords.items():
            if any(keyword in view_desc for keyword in keywords):
                return orientation
        
        # Default to west for Uno Luxe (most units face the sea/sunset)
        if 'uno' in property_data.get('Project_Name', '').lower():
            return ViewOrientation.WEST
        
        return None
    
    def _extract_floor_number(self, property_data: Dict[str, Any]) -> Optional[int]:
        """
        Extract floor number from property data
        
        Args:
            property_data: Property data from Zoho CRM
            
        Returns:
            Floor number as integer
        """
        # Check if floor is already specified
        if 'floor' in property_data:
            try:
                return int(property_data['floor'])
            except (ValueError, TypeError):
                pass
        
        # Try to extract from unit number
        unit_no = property_data.get('Unit_No', '')
        if not unit_no:
            return None
        
        # Common format: Tower-Floor-Unit (e.g., "A-12-05" is Tower A, Floor 12, Unit 05)
        parts = unit_no.split('-')
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except (ValueError, IndexError):
                pass
        
        # Another common format: Floor+Unit (e.g., "1204" is Floor 12, Unit 04)
        if len(unit_no) >= 3 and unit_no.isdigit():
            try:
                return int(unit_no[:-2])
            except (ValueError, IndexError):
                pass
        
        return None
    
    def _calculate_sunset_view_score(self, view_orientation: Optional[ViewOrientation], floor: Optional[int]) -> int:
        """
        Calculate sunset view score (0-100)
        
        Args:
            view_orientation: Property view orientation
            floor: Floor number
            
        Returns:
            Sunset view score (0-100)
        """
        base_score = 0
        
        # Score based on orientation
        orientation_scores = {
            ViewOrientation.WEST: 70,      # Direct sunset view
            ViewOrientation.SOUTHWEST: 60, # Good sunset view
            ViewOrientation.NORTHWEST: 60, # Good sunset view
            ViewOrientation.SOUTH: 40,     # Partial sunset view
            ViewOrientation.NORTH: 40,     # Partial sunset view
            ViewOrientation.EAST: 10,      # No sunset view
            ViewOrientation.NORTHEAST: 20, # Poor sunset view
            ViewOrientation.SOUTHEAST: 20  # Poor sunset view
        }
        
        if view_orientation:
            base_score = orientation_scores.get(view_orientation, 0)
        
        # Add bonus for higher floors
        floor_bonus = 0
        if floor:
            if floor > 10:
                floor_bonus = 20
            elif floor > 5:
                floor_bonus = 10
        
        # Calculate final score (cap at 100)
        final_score = min(base_score + floor_bonus, 100)
        
        return final_score
    
    def _generate_location_summary(
        self, 
        property_data: Dict[str, Any],
        latitude: float,
        longitude: float,
        poi_data: Dict[str, List[Dict[str, Any]]],
        wynn_casino_distance: float,
        sunset_view_score: int
    ) -> str:
        """
        Generate location insights summary
        
        Args:
            property_data: Property data from Zoho CRM
            latitude: Property latitude
            longitude: Property longitude
            poi_data: Points of interest data
            wynn_casino_distance: Distance to Wynn Casino site
            sunset_view_score: Sunset view score
            
        Returns:
            Location insights summary (300 words)
        """
        project_name = property_data.get('Project_Name', 'the property')
        unit_no = property_data.get('Unit_No', '')
        
        # Start with property introduction
        summary = f"Location Analysis for {project_name}"
        if unit_no:
            summary += f" Unit {unit_no}"
        summary += f" (Coordinates: {latitude:.6f}, {longitude:.6f})\n\n"
        
        # Add Wynn Casino proximity
        casino_desc = "future Wynn Casino & Resort"
        summary += f"This property is located {wynn_casino_distance:.2f} km from the {casino_desc} site, "
        
        if wynn_casino_distance < 1:
            summary += "offering exceptional proximity to this landmark development. "
        elif wynn_casino_distance < 2:
            summary += "providing convenient access to this major attraction. "
        else:
            summary += "within reasonable distance of this upcoming entertainment destination. "
        
        # Add sunset view assessment
        summary += f"The property has a sunset view score of {sunset_view_score}/100, "
        
        if sunset_view_score >= 67:
            summary += "offering spectacular sunset views over the Arabian Gulf. "
        elif sunset_view_score >= 34:
            summary += "providing partial sunset views depending on the season. "
        else:
            summary += "with limited direct sunset visibility. "
        
        # Add POI information
        summary += "\n\nNearby Points of Interest:\n"
        
        for category in self.poi_categories:
            pois = poi_data.get(category, [])
            if not pois:
                continue
            
            # Get category display name
            category_display = category.replace('_', ' ').title()
            
            # Add category header
            summary += f"\n{category_display}s:\n"
            
            # Add top 3 POIs in this category
            for i, poi in enumerate(pois[:3]):
                name = poi['name']
                distance = poi['distance']
                rating = poi.get('rating', 'N/A')
                
                summary += f"- {name} ({distance:.2f} km"
                if rating != 'N/A':
                    summary += f", Rating: {rating}/5"
                summary += ")\n"
        
        # Add location advantage summary
        summary += "\nLocation Advantages:\n"
        
        advantages = []
        
        # Check for beach proximity
        beach_pois = poi_data.get(POICategory.BEACH, [])
        if beach_pois and beach_pois[0]['distance'] < 1:
            advantages.append(f"Beach access within {beach_pois[0]['distance']:.2f} km")
        
        # Check for marina proximity
        marina_pois = poi_data.get(POICategory.MARINA, [])
        if marina_pois and marina_pois[0]['distance'] < 2:
            advantages.append(f"Marina facilities at {marina_pois[0]['distance']:.2f} km")
        
        # Check for dining options
        restaurant_pois = poi_data.get(POICategory.RESTAURANT, [])
        if restaurant_pois and len(restaurant_pois) >= 3:
            advantages.append(f"Multiple fine dining options within {restaurant_pois[2]['distance']:.2f} km")
        
        # Check for hospitality
        hotel_pois = poi_data.get(POICategory.HOTEL, [])
        if hotel_pois and len(hotel_pois) >= 2:
            advantages.append(f"Surrounded by {len(hotel_pois[:5])} luxury hotels and resorts")
        
        # Check for healthcare
        hospital_pois = poi_data.get(POICategory.HOSPITAL, [])
        if hospital_pois:
            advantages.append(f"Healthcare facilities within {hospital_pois[0]['distance']:.2f} km")
        
        # Check for education
        school_pois = poi_data.get(POICategory.SCHOOL, [])
        if school_pois:
            advantages.append(f"Educational institutions at {school_pois[0]['distance']:.2f} km")
        
        # Add Wynn proximity as advantage
        if wynn_casino_distance < 2:
            advantages.append(f"Prime position near future Wynn Casino & Resort ({wynn_casino_distance:.2f} km)")
        
        # Add sunset view as advantage if good
        if sunset_view_score >= 67:
            advantages.append("Excellent sunset views")
        
        # Add advantages to summary
        for advantage in advantages:
            summary += f"- {advantage}\n"
        
        # Add investment potential conclusion
        summary += "\nInvestment Potential:\n"
        summary += f"Based on location analysis, {project_name} "
        
        if wynn_casino_distance < 1.5 and sunset_view_score >= 60:
            summary += "offers exceptional investment potential with prime positioning and desirable views. "
        elif wynn_casino_distance < 3 and sunset_view_score >= 40:
            summary += "presents strong investment opportunity with good location advantages. "
        else:
            summary += "provides reasonable investment value with several location benefits. "
        
        summary += "The property's proximity to key attractions and amenities enhances both rental yield potential and long-term capital appreciation prospects."
        
        return summary
    
    async def _generate_translations(self, summary: str) -> Dict[str, str]:
        """
        Generate translations of the summary
        
        Args:
            summary: English summary text
            
        Returns:
            Dictionary with translations in Arabic, French, and Hindi
        """
        # In a real implementation, this would use a translation service
        # For now, we'll use placeholder translations
        
        # Simulate translation delay
        await asyncio.sleep(0.5)
        
        return {
            "ar": f"[Arabic Translation of: {summary[:100]}...]",
            "fr": f"[French Translation of: {summary[:100]}...]",
            "hi": f"[Hindi Translation of: {summary[:100]}...]"
        }
