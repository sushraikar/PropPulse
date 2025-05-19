"""
RetrievalAgent for PropPulse
Responsible for retrieving relevant information from vector store
"""
from typing import Dict, Any, List, Optional
import os
import json
import asyncio

# Import base agent
from agents.base_agent import BaseAgent


class RetrievalAgent(BaseAgent):
    """
    RetrievalAgent performs similarity search and retrieves relevant information.
    
    Responsibilities:
    - Execute similarity search with k=8 results
    - Apply metadata filters to search results
    - Rank and organize retrieved information
    - Return structured data for proposal generation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RetrievalAgent"""
        super().__init__(config)
        self.default_k = self.get_config_value('default_k', 8)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process retrieval requests and return relevant information.
        
        Args:
            input_data: Dictionary containing:
                - queries: List of query strings or query objects
                - filters: Optional metadata filters
                - k: Optional number of results to return (default: 8)
                
        Returns:
            Dict containing:
                - results: List of retrieval results
                - status: Processing status
        """
        # Validate input
        required_keys = ['queries']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: queries'
            }
        
        queries = input_data['queries']
        filters = input_data.get('filters', {})
        k = input_data.get('k', self.default_k)
        
        try:
            # Process each query
            results = []
            for query in queries:
                # Handle both string queries and query objects
                query_text = query if isinstance(query, str) else query.get('query', '')
                query_type = None if isinstance(query, str) else query.get('type')
                
                # Perform vector search
                # In a real implementation, this would call Pinecone
                query_results = await self._perform_vector_search(query_text, filters, k, query_type)
                results.append({
                    'query': query_text,
                    'type': query_type,
                    'results': query_results
                })
            
            # Combine and rank results
            combined_results = self._combine_results(results)
            
            return {
                'status': 'success',
                'results': combined_results,
                'individual_query_results': results
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error retrieving information: {str(e)}'
            }
    
    async def _perform_vector_search(
        self, 
        query: str, 
        filters: Dict[str, Any], 
        k: int, 
        query_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search using Pinecone.
        
        Args:
            query: Query string
            filters: Metadata filters
            k: Number of results to return
            query_type: Optional query type for specialized retrieval
            
        Returns:
            List of search results
        """
        # In a real implementation, this would:
        # 1. Convert query to embedding using OpenAI
        # 2. Perform similarity search in Pinecone
        # 3. Apply metadata filters
        # 4. Return results
        
        # For now, return mock results
        mock_results = []
        
        # Generate different mock results based on query type
        if query_type == 'property_details':
            mock_results = [
                {
                    'id': 'chunk_001',
                    'text': 'Luxury 2-bedroom apartment in Downtown Dubai. 1,200 sq ft with premium finishes. Floor-to-ceiling windows with stunning Burj Khalifa views. Marble flooring throughout.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 2,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.92
                },
                {
                    'id': 'chunk_002',
                    'text': 'Master bedroom with en-suite bathroom and walk-in closet. Second bedroom with built-in wardrobes. Fully equipped kitchen with premium appliances. Large balcony overlooking the Dubai Fountain.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 3,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.89
                }
            ]
        elif query_type == 'pricing':
            mock_results = [
                {
                    'id': 'chunk_003',
                    'text': 'Price: AED 1,250,000. Payment plan: 20% down payment, 30% during construction, 50% on completion. Service charge: AED 15 per sq ft per year.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 5,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.94
                }
            ]
        elif query_type == 'investment_metrics':
            mock_results = [
                {
                    'id': 'chunk_004',
                    'text': 'Expected rental yield: 6.8% per annum. Average occupancy rate in the area: 85%. Projected capital appreciation: 7% per annum over the next 10 years.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 7,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.91
                }
            ]
        elif query_type == 'developer_info':
            mock_results = [
                {
                    'id': 'chunk_005',
                    'text': 'Developed by Emaar Properties, the leading developer in Dubai with a proven track record of delivering high-quality projects on time.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 1,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.88
                }
            ]
        elif query_type == 'location_advantages':
            mock_results = [
                {
                    'id': 'chunk_006',
                    'text': 'Located in the heart of Downtown Dubai, within walking distance to Dubai Mall, Burj Khalifa, and Dubai Opera. Easy access to Sheikh Zayed Road and Dubai Metro.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 4,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.90
                }
            ]
        else:
            # General query
            mock_results = [
                {
                    'id': 'chunk_001',
                    'text': 'Luxury 2-bedroom apartment in Downtown Dubai. 1,200 sq ft with premium finishes.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 2,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.92
                },
                {
                    'id': 'chunk_003',
                    'text': 'Price: AED 1,250,000. Payment plan: 20% down payment, 30% during construction, 50% on completion.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 5,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.94
                },
                {
                    'id': 'chunk_004',
                    'text': 'Expected rental yield: 6.8% per annum. Average occupancy rate in the area: 85%.',
                    'metadata': {
                        'property_id': 'PROP_001',
                        'page_no': 7,
                        'project_code': 'DOWNTOWN01'
                    },
                    'score': 0.91
                }
            ]
        
        # Simulate async operation
        await asyncio.sleep(0.1)
        
        return mock_results[:k]
    
    def _combine_results(self, query_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine and organize results from multiple queries.
        
        Args:
            query_results: List of query result dictionaries
            
        Returns:
            Combined and organized results
        """
        # Organize results by property
        properties = {}
        
        for query_result in query_results:
            for result in query_result['results']:
                property_id = result['metadata'].get('property_id')
                
                if property_id not in properties:
                    properties[property_id] = {
                        'property_id': property_id,
                        'details': [],
                        'pricing': [],
                        'investment_metrics': [],
                        'developer_info': [],
                        'location': [],
                        'other': []
                    }
                
                # Categorize result based on query type
                query_type = query_result.get('type')
                if query_type == 'property_details':
                    properties[property_id]['details'].append(result)
                elif query_type == 'pricing':
                    properties[property_id]['pricing'].append(result)
                elif query_type == 'investment_metrics':
                    properties[property_id]['investment_metrics'].append(result)
                elif query_type == 'developer_info':
                    properties[property_id]['developer_info'].append(result)
                elif query_type == 'location_advantages':
                    properties[property_id]['location'].append(result)
                else:
                    properties[property_id]['other'].append(result)
        
        return {
            'properties': list(properties.values())
        }
