"""
QueryPlanner agent for PropPulse
Responsible for decomposing user queries and orchestrating the retrieval process
"""
from typing import Dict, Any, List, Optional
import json
import re

# Import base agent
from agents.base_agent import BaseAgent


class QueryPlanner(BaseAgent):
    """
    QueryPlanner agent decomposes user queries and plans the retrieval strategy.
    
    Responsibilities:
    - Parse and understand user investment requirements
    - Break down complex queries into sub-queries
    - Determine relevant metadata filters
    - Coordinate with RetrievalAgent to fetch relevant information
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the QueryPlanner agent"""
        super().__init__(config)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a user query and plan the retrieval strategy.
        
        Args:
            input_data: Dictionary containing:
                - query: User's investment query or requirements
                - user_preferences: Optional user preferences
                - property_ids: Optional list of specific property IDs
                
        Returns:
            Dict containing:
                - sub_queries: List of decomposed sub-queries
                - metadata_filters: Metadata filters for retrieval
                - retrieval_plan: Plan for information retrieval
        """
        # Validate input
        required_keys = ['query']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: query'
            }
        
        query = input_data['query']
        user_preferences = input_data.get('user_preferences', {})
        property_ids = input_data.get('property_ids', [])
        
        try:
            # Decompose the query into sub-queries
            sub_queries = self._decompose_query(query)
            
            # Determine metadata filters based on query and preferences
            metadata_filters = self._determine_metadata_filters(query, user_preferences, property_ids)
            
            # Create retrieval plan
            retrieval_plan = self._create_retrieval_plan(sub_queries, metadata_filters)
            
            return {
                'status': 'success',
                'sub_queries': sub_queries,
                'metadata_filters': metadata_filters,
                'retrieval_plan': retrieval_plan
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error planning query: {str(e)}'
            }
    
    def _decompose_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Decompose a complex query into simpler sub-queries.
        
        Args:
            query: User's investment query
            
        Returns:
            List of sub-query dictionaries
        """
        # In a real implementation, this would use NLP to break down the query
        # For now, we'll use a rule-based approach
        
        sub_queries = []
        
        # Check for property details
        if re.search(r'property|apartment|villa|penthouse', query, re.IGNORECASE):
            sub_queries.append({
                'type': 'property_details',
                'query': 'Extract property details including location, size, and amenities'
            })
        
        # Check for price information
        if re.search(r'price|cost|budget|afford', query, re.IGNORECASE):
            sub_queries.append({
                'type': 'pricing',
                'query': 'Extract property pricing information and payment plans'
            })
        
        # Check for investment metrics
        if re.search(r'invest|return|yield|ROI|rental|income', query, re.IGNORECASE):
            sub_queries.append({
                'type': 'investment_metrics',
                'query': 'Extract investment metrics including rental yield and capital appreciation'
            })
        
        # Check for developer information
        if re.search(r'developer|builder|company|reputation', query, re.IGNORECASE):
            sub_queries.append({
                'type': 'developer_info',
                'query': 'Extract information about the developer and their track record'
            })
        
        # Check for location advantages
        if re.search(r'location|area|neighborhood|facilities|nearby', query, re.IGNORECASE):
            sub_queries.append({
                'type': 'location_advantages',
                'query': 'Extract information about location advantages and nearby facilities'
            })
        
        # If no specific aspects were identified, create a general query
        if not sub_queries:
            sub_queries.append({
                'type': 'general',
                'query': 'Extract general property and investment information'
            })
        
        return sub_queries
    
    def _determine_metadata_filters(self, query: str, user_preferences: Dict[str, Any], property_ids: List[str]) -> Dict[str, Any]:
        """
        Determine metadata filters based on query and preferences.
        
        Args:
            query: User's investment query
            user_preferences: User preferences
            property_ids: List of specific property IDs
            
        Returns:
            Metadata filter dictionary
        """
        filters = {}
        
        # Add property IDs if specified
        if property_ids:
            filters['property_id'] = property_ids
        
        # Extract price range
        price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:k|m|million)?\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:k|m|million)?', query, re.IGNORECASE)
        if price_match:
            min_price = self._normalize_price(price_match.group(1), price_match.group(2))
            max_price = self._normalize_price(price_match.group(3), price_match.group(4))
            filters['price_range'] = {'min': min_price, 'max': max_price}
        
        # Extract property type
        property_types = []
        if re.search(r'apartment', query, re.IGNORECASE):
            property_types.append('apartment')
        if re.search(r'villa', query, re.IGNORECASE):
            property_types.append('villa')
        if re.search(r'penthouse', query, re.IGNORECASE):
            property_types.append('penthouse')
        if re.search(r'townhouse', query, re.IGNORECASE):
            property_types.append('townhouse')
        
        if property_types:
            filters['property_type'] = property_types
        
        # Add user preferences
        if user_preferences:
            if 'preferred_locations' in user_preferences:
                filters['location'] = user_preferences['preferred_locations']
            
            if 'min_bedrooms' in user_preferences:
                filters['bedrooms'] = {'min': user_preferences['min_bedrooms']}
            
            if 'max_budget' in user_preferences:
                if 'price_range' not in filters:
                    filters['price_range'] = {}
                filters['price_range']['max'] = user_preferences['max_budget']
        
        return filters
    
    def _normalize_price(self, price_str: str, unit: Optional[str] = None) -> float:
        """
        Normalize price string to a float value.
        
        Args:
            price_str: Price string
            unit: Optional unit (k, m, million)
            
        Returns:
            Normalized price as float
        """
        price = float(price_str)
        
        if unit:
            unit = unit.lower()
            if unit in ['k', 'thousand']:
                price *= 1000
            elif unit in ['m', 'million']:
                price *= 1000000
        
        return price
    
    def _create_retrieval_plan(self, sub_queries: List[Dict[str, Any]], metadata_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a plan for information retrieval.
        
        Args:
            sub_queries: List of sub-queries
            metadata_filters: Metadata filters
            
        Returns:
            Retrieval plan dictionary
        """
        # In a real implementation, this would create a more sophisticated plan
        # For now, we'll create a simple plan with priorities
        
        # Assign priorities to sub-queries
        prioritized_queries = []
        for i, query in enumerate(sub_queries):
            priority = 1  # Default priority
            
            # Assign higher priority to investment metrics and pricing
            if query['type'] == 'investment_metrics':
                priority = 3
            elif query['type'] == 'pricing':
                priority = 2
            
            prioritized_queries.append({
                **query,
                'priority': priority,
                'k_value': 8  # Default k value for similarity search
            })
        
        # Sort by priority (descending)
        prioritized_queries.sort(key=lambda x: x['priority'], reverse=True)
        
        return {
            'queries': prioritized_queries,
            'filters': metadata_filters,
            'strategy': 'hierarchical',  # Could be 'parallel', 'sequential', etc.
            'max_results_per_query': 8
        }
