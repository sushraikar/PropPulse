"""
Pinecone vector store integration for PropPulse
"""
from typing import Dict, Any, List, Optional, Union
import os
import json
import asyncio
import pinecone
from datetime import datetime

class PineconeVectorStore:
    """
    Pinecone vector store integration for PropPulse.
    
    Handles vector storage and retrieval for the RAG pipeline.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Pinecone vector store integration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Pinecone configuration
        self.api_key = self.config.get('api_key', os.getenv('PINECONE_API_KEY'))
        self.environment = self.config.get('environment', os.getenv('PINECONE_ENVIRONMENT'))
        self.index_name = self.config.get('index_name', os.getenv('PINECONE_INDEX_NAME', 'proppulse-index'))
        self.namespace = self.config.get('namespace', os.getenv('PINECONE_NAMESPACE', 'properties'))
        self.dimension = self.config.get('dimension', 1536)  # Default for text-embedding-3-small
        
        # Initialize Pinecone
        self._initialize_pinecone()
    
    def _initialize_pinecone(self) -> None:
        """Initialize Pinecone client and ensure index exists."""
        # Initialize Pinecone
        pinecone.init(api_key=self.api_key, environment=self.environment)
        
        # Check if index exists, create if not
        if self.index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine"
            )
        
        # Connect to index
        self.index = pinecone.Index(self.index_name)
    
    async def upsert_vectors(
        self, 
        vectors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Upsert vectors to Pinecone.
        
        Args:
            vectors: List of vector dictionaries with id, values, and metadata
            
        Returns:
            Upsert response
        """
        # Format vectors for Pinecone
        pinecone_vectors = []
        for vector in vectors:
            pinecone_vectors.append({
                'id': vector['id'],
                'values': vector['values'],
                'metadata': vector.get('metadata', {})
            })
        
        # Upsert vectors
        response = self.index.upsert(
            vectors=pinecone_vectors,
            namespace=self.namespace
        )
        
        return response
    
    async def query_vectors(
        self, 
        query_vector: List[float],
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Query vectors from Pinecone.
        
        Args:
            query_vector: Query vector values
            filter: Optional metadata filter
            top_k: Number of results to return
            include_metadata: Whether to include metadata in results
            
        Returns:
            Query response
        """
        # Query vectors
        response = self.index.query(
            vector=query_vector,
            filter=filter,
            top_k=top_k,
            include_metadata=include_metadata,
            namespace=self.namespace
        )
        
        return response
    
    async def delete_vectors(
        self, 
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        delete_all: bool = False
    ) -> Dict[str, Any]:
        """
        Delete vectors from Pinecone.
        
        Args:
            ids: Optional list of vector IDs to delete
            filter: Optional metadata filter for vectors to delete
            delete_all: Whether to delete all vectors in the namespace
            
        Returns:
            Delete response
        """
        if delete_all:
            # Delete all vectors in namespace
            response = self.index.delete(
                delete_all=True,
                namespace=self.namespace
            )
        elif ids:
            # Delete specific vector IDs
            response = self.index.delete(
                ids=ids,
                namespace=self.namespace
            )
        elif filter:
            # Delete vectors matching filter
            response = self.index.delete(
                filter=filter,
                namespace=self.namespace
            )
        else:
            raise ValueError("Must provide ids, filter, or delete_all=True")
        
        return response
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics.
        
        Returns:
            Index statistics
        """
        return self.index.describe_index_stats()
    
    async def create_document_vectors(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Create vectors for document chunks.
        
        Args:
            document_id: Document ID
            chunks: List of document chunks
            embeddings: List of embeddings for chunks
            
        Returns:
            Upsert response
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        # Create vectors
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = chunk.get('chunk_id', f"{document_id}_chunk_{i}")
            
            vectors.append({
                'id': chunk_id,
                'values': embedding,
                'metadata': {
                    'document_id': document_id,
                    'chunk_id': chunk_id,
                    'text': chunk.get('text', ''),
                    'token_count': chunk.get('token_count', 0),
                    **chunk.get('metadata', {})
                }
            })
        
        # Upsert vectors
        return await self.upsert_vectors(vectors)
    
    async def search_similar(
        self,
        query_vector: List[float],
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_vector: Query vector
            filter: Optional metadata filter
            top_k: Number of results to return
            
        Returns:
            List of similar documents with scores
        """
        # Query vectors
        response = await self.query_vectors(
            query_vector=query_vector,
            filter=filter,
            top_k=top_k,
            include_metadata=True
        )
        
        # Format results
        results = []
        for match in response.get('matches', []):
            results.append({
                'id': match['id'],
                'score': match['score'],
                'metadata': match.get('metadata', {}),
                'text': match.get('metadata', {}).get('text', '')
            })
        
        return results
