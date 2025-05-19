"""
Tests for the OpenAI embeddings integration
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from integrations.openai.openai_embeddings import OpenAIEmbeddings

class TestOpenAIEmbeddings:
    """Test suite for OpenAI embeddings integration"""
    
    @pytest.fixture
    def openai_embeddings(self, mock_env_vars):
        """Create an OpenAIEmbeddings instance for testing"""
        config = {
            'model': 'text-embedding-3-small',
            'batch_size': 5
        }
        return OpenAIEmbeddings(config)
    
    @pytest.mark.asyncio
    async def test_create_embedding(self, openai_embeddings, mock_openai):
        """Test creating a single embedding"""
        # Create embedding
        embedding = await openai_embeddings.create_embedding("This is a test text")
        
        # Verify embedding
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert embedding[0] == 0.1
        
        # Verify API call
        mock_openai.assert_called_once()
        args, kwargs = mock_openai.call_args
        assert kwargs['model'] == 'text-embedding-3-small'
        assert kwargs['input'] == "This is a test text"
    
    @pytest.mark.asyncio
    async def test_create_embeddings_batch(self, openai_embeddings, mock_openai):
        """Test creating embeddings for a batch of texts"""
        # Create batch embeddings
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = await openai_embeddings.create_embeddings_batch(texts)
        
        # Verify embeddings
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)
        
        # Verify API call
        mock_openai.assert_called_once()
        args, kwargs = mock_openai.call_args
        assert kwargs['model'] == 'text-embedding-3-small'
        assert kwargs['input'] == texts
    
    @pytest.mark.asyncio
    async def test_create_embeddings_with_batching(self, openai_embeddings, mock_openai):
        """Test creating embeddings with automatic batching"""
        # Create a list of texts larger than batch size
        texts = [f"Text {i}" for i in range(12)]
        
        # Create embeddings
        embeddings = await openai_embeddings.create_embeddings(texts)
        
        # Verify embeddings
        assert isinstance(embeddings, list)
        assert len(embeddings) == 12
        assert all(len(emb) == 1536 for emb in embeddings)
        
        # Verify API calls (should be 3 calls with batch size 5)
        assert mock_openai.call_count == 3
    
    @pytest.mark.asyncio
    async def test_embed_chunks(self, openai_embeddings, mock_openai):
        """Test embedding document chunks"""
        # Create test chunks
        chunks = [
            {'chunk_id': 'chunk1', 'text': 'Chunk 1 text', 'metadata': {'page_no': 1}},
            {'chunk_id': 'chunk2', 'text': 'Chunk 2 text', 'metadata': {'page_no': 2}},
            {'chunk_id': 'chunk3', 'text': 'Chunk 3 text', 'metadata': {'page_no': 3}}
        ]
        
        # Embed chunks
        embeddings = await openai_embeddings.embed_chunks(chunks)
        
        # Verify embeddings
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)
        
        # Verify API call
        mock_openai.assert_called_once()
        args, kwargs = mock_openai.call_args
        assert kwargs['model'] == 'text-embedding-3-small'
        assert kwargs['input'] == ['Chunk 1 text', 'Chunk 2 text', 'Chunk 3 text']
    
    @pytest.mark.asyncio
    async def test_embed_query(self, openai_embeddings, mock_openai):
        """Test embedding a query"""
        # Embed query
        embedding = await openai_embeddings.embed_query("What is the price of the property?")
        
        # Verify embedding
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        
        # Verify API call
        mock_openai.assert_called_once()
        args, kwargs = mock_openai.call_args
        assert kwargs['model'] == 'text-embedding-3-small'
        assert kwargs['input'] == "What is the price of the property?"
    
    @pytest.mark.asyncio
    async def test_invalid_chunk_format(self, openai_embeddings):
        """Test embedding chunks with invalid format"""
        # Create invalid chunks
        invalid_chunks = [
            {'invalid_key': 'No text field'},
            42,  # Not a dict
            {'chunk_id': 'chunk3', 'text': 'Valid chunk'}
        ]
        
        # Attempt to embed invalid chunks
        with pytest.raises(ValueError):
            await openai_embeddings.embed_chunks(invalid_chunks)
