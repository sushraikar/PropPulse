"""
OpenAI embeddings integration for PropPulse
"""
from typing import Dict, Any, List, Optional, Union
import os
import json
import asyncio
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

class OpenAIEmbeddings:
    """
    OpenAI embeddings integration for PropPulse.
    
    Handles text embedding generation for the RAG pipeline.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize OpenAI embeddings integration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # OpenAI configuration
        self.api_key = self.config.get('api_key', os.getenv('OPENAI_API_KEY'))
        self.model = self.config.get('model', os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'))
        self.batch_size = self.config.get('batch_size', 100)  # Maximum batch size for API calls
        
        # Initialize OpenAI client
        openai.api_key = self.api_key
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # Create embedding
        response = openai.Embedding.create(
            model=self.model,
            input=text
        )
        
        # Extract embedding
        embedding = response['data'][0]['embedding']
        
        return embedding
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a batch of texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Create embeddings
        response = openai.Embedding.create(
            model=self.model,
            input=texts
        )
        
        # Extract embeddings
        embeddings = [item['embedding'] for item in response['data']]
        
        return embeddings
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a list of texts, handling batching.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Process in batches to avoid API limits
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self.create_embeddings_batch(batch)
            all_embeddings.extend(batch_embeddings)
            
            # Add a small delay between batches to avoid rate limits
            if i + self.batch_size < len(texts):
                await asyncio.sleep(0.5)
        
        return all_embeddings
    
    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[List[float]]:
        """
        Create embeddings for document chunks.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of embedding vectors
        """
        # Extract text from chunks
        texts = []
        for chunk in chunks:
            if isinstance(chunk, dict) and 'text' in chunk:
                texts.append(chunk['text'])
            elif isinstance(chunk, str):
                texts.append(chunk)
            else:
                raise ValueError(f"Invalid chunk format: {chunk}")
        
        # Create embeddings
        return await self.create_embeddings(texts)
    
    async def embed_query(self, query: str) -> List[float]:
        """
        Create embedding for a query.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector
        """
        return await self.create_embedding(query)
