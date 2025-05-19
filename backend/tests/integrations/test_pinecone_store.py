"""
Tests for the Pinecone vector store integration
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from integrations.pinecone.pinecone_store import PineconeVectorStore

class TestPineconeVectorStore:
    """Test suite for Pinecone vector store integration"""
    
    @pytest.fixture
    def pinecone_store(self, mock_env_vars, mock_pinecone):
        """Create a PineconeVectorStore instance for testing"""
        config = {
            'index_name': 'test-index',
            'namespace': 'properties',
            'dimension': 1536
        }
        return PineconeVectorStore(config)
    
    def test_initialization(self, pinecone_store, mock_pinecone):
        """Test initialization of Pinecone vector store"""
        assert pinecone_store.index_name == 'test-index'
        assert pinecone_store.namespace == 'properties'
        assert pinecone_store.dimension == 1536
        assert pinecone_store.index is not None
    
    @pytest.mark.asyncio
    async def test_upsert_vectors(self, pinecone_store, mock_pinecone):
        """Test upserting vectors to Pinecone"""
        # Create test vectors
        vectors = [
            {
                'id': 'vec1',
                'values': [0.1] * 1536,
                'metadata': {'document_id': 'doc1', 'page_no': 1}
            },
            {
                'id': 'vec2',
                'values': [0.2] * 1536,
                'metadata': {'document_id': 'doc1', 'page_no': 2}
            }
        ]
        
        # Upsert vectors
        response = await pinecone_store.upsert_vectors(vectors)
        
        # Verify response
        assert response == {'upserted_count': 5}
        
        # Verify Pinecone API call
        mock_pinecone.upsert.assert_called_once()
        args, kwargs = mock_pinecone.upsert.call_args
        assert kwargs['namespace'] == 'properties'
        assert len(kwargs['vectors']) == 2
        assert kwargs['vectors'][0]['id'] == 'vec1'
        assert kwargs['vectors'][1]['id'] == 'vec2'
    
    @pytest.mark.asyncio
    async def test_query_vectors(self, pinecone_store, mock_pinecone):
        """Test querying vectors from Pinecone"""
        # Create test query vector
        query_vector = [0.1] * 1536
        filter = {'document_id': 'doc1'}
        
        # Query vectors
        response = await pinecone_store.query_vectors(query_vector, filter, top_k=5)
        
        # Verify response
        assert 'matches' in response
        assert len(response['matches']) == 1
        assert response['matches'][0]['id'] == 'test-chunk-1'
        assert response['matches'][0]['score'] == 0.95
        
        # Verify Pinecone API call
        mock_pinecone.query.assert_called_once()
        args, kwargs = mock_pinecone.query.call_args
        assert kwargs['vector'] == query_vector
        assert kwargs['filter'] == filter
        assert kwargs['top_k'] == 5
        assert kwargs['namespace'] == 'properties'
        assert kwargs['include_metadata'] == True
    
    @pytest.mark.asyncio
    async def test_delete_vectors(self, pinecone_store, mock_pinecone):
        """Test deleting vectors from Pinecone"""
        # Delete by IDs
        ids = ['vec1', 'vec2']
        response = await pinecone_store.delete_vectors(ids=ids)
        
        # Verify response
        assert response == {'deleted_count': 1}
        
        # Verify Pinecone API call
        mock_pinecone.delete.assert_called_once()
        args, kwargs = mock_pinecone.delete.call_args
        assert kwargs['ids'] == ids
        assert kwargs['namespace'] == 'properties'
        
        # Reset mock
        mock_pinecone.delete.reset_mock()
        
        # Delete by filter
        filter = {'document_id': 'doc1'}
        response = await pinecone_store.delete_vectors(filter=filter)
        
        # Verify response
        assert response == {'deleted_count': 1}
        
        # Verify Pinecone API call
        mock_pinecone.delete.assert_called_once()
        args, kwargs = mock_pinecone.delete.call_args
        assert kwargs['filter'] == filter
        assert kwargs['namespace'] == 'properties'
        
        # Reset mock
        mock_pinecone.delete.reset_mock()
        
        # Delete all
        response = await pinecone_store.delete_vectors(delete_all=True)
        
        # Verify response
        assert response == {'deleted_count': 1}
        
        # Verify Pinecone API call
        mock_pinecone.delete.assert_called_once()
        args, kwargs = mock_pinecone.delete.call_args
        assert kwargs['delete_all'] == True
        assert kwargs['namespace'] == 'properties'
    
    @pytest.mark.asyncio
    async def test_delete_vectors_invalid(self, pinecone_store):
        """Test deleting vectors with invalid parameters"""
        # Attempt to delete without specifying how
        with pytest.raises(ValueError):
            await pinecone_store.delete_vectors()
    
    @pytest.mark.asyncio
    async def test_get_stats(self, pinecone_store, mock_pinecone):
        """Test getting index statistics"""
        # Get stats
        response = await pinecone_store.get_stats()
        
        # Verify response
        assert 'namespaces' in response
        assert 'properties' in response['namespaces']
        assert response['namespaces']['properties']['vector_count'] == 100
        
        # Verify Pinecone API call
        mock_pinecone.describe_index_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_document_vectors(self, pinecone_store, mock_pinecone):
        """Test creating vectors for document chunks"""
        # Create test chunks and embeddings
        document_id = 'test-doc-1'
        chunks = [
            {
                'chunk_id': 'chunk1',
                'text': 'This is chunk 1',
                'token_count': 4,
                'metadata': {'page_no': 1}
            },
            {
                'chunk_id': 'chunk2',
                'text': 'This is chunk 2',
                'token_count': 4,
                'metadata': {'page_no': 2}
            }
        ]
        embeddings = [
            [0.1] * 1536,
            [0.2] * 1536
        ]
        
        # Create document vectors
        response = await pinecone_store.create_document_vectors(document_id, chunks, embeddings)
        
        # Verify response
        assert response == {'upserted_count': 5}
        
        # Verify Pinecone API call
        mock_pinecone.upsert.assert_called_once()
        args, kwargs = mock_pinecone.upsert.call_args
        assert len(kwargs['vectors']) == 2
        assert kwargs['vectors'][0]['id'] == 'chunk1'
        assert kwargs['vectors'][0]['metadata']['document_id'] == 'test-doc-1'
        assert kwargs['vectors'][0]['metadata']['text'] == 'This is chunk 1'
        assert kwargs['vectors'][0]['metadata']['page_no'] == 1
    
    @pytest.mark.asyncio
    async def test_create_document_vectors_mismatch(self, pinecone_store):
        """Test creating vectors with mismatched chunks and embeddings"""
        # Create mismatched chunks and embeddings
        document_id = 'test-doc-1'
        chunks = [{'chunk_id': 'chunk1', 'text': 'This is chunk 1'}]
        embeddings = [[0.1] * 1536, [0.2] * 1536]  # Two embeddings for one chunk
        
        # Attempt to create document vectors
        with pytest.raises(ValueError):
            await pinecone_store.create_document_vectors(document_id, chunks, embeddings)
    
    @pytest.mark.asyncio
    async def test_search_similar(self, pinecone_store, mock_pinecone):
        """Test searching for similar documents"""
        # Create test query vector
        query_vector = [0.1] * 1536
        filter = {'document_id': 'test-doc-1'}
        
        # Search for similar documents
        results = await pinecone_store.search_similar(query_vector, filter, top_k=5)
        
        # Verify results
        assert len(results) == 1
        assert results[0]['id'] == 'test-chunk-1'
        assert results[0]['score'] == 0.95
        assert results[0]['text'] == 'This is a test chunk'
        assert results[0]['metadata']['document_id'] == 'test-doc-1'
        assert results[0]['metadata']['page_no'] == 1
        
        # Verify Pinecone API call
        mock_pinecone.query.assert_called_once()
        args, kwargs = mock_pinecone.query.call_args
        assert kwargs['vector'] == query_vector
        assert kwargs['filter'] == filter
        assert kwargs['top_k'] == 5
