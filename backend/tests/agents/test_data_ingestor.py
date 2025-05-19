"""
Tests for the DataIngestor agent
"""
import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
import asyncio

from agents.data_ingestor.data_ingestor import DataIngestor

class TestDataIngestor:
    """Test suite for DataIngestor agent"""
    
    @pytest.fixture
    def data_ingestor(self):
        """Create a DataIngestor instance for testing"""
        config = {
            'chunk_size': 1000,
            'storage_path': '/tmp/test-proppulse/documents'
        }
        return DataIngestor(config)
    
    @pytest.mark.asyncio
    async def test_process_missing_input(self, data_ingestor):
        """Test process with missing required input"""
        # Test with empty input
        result = await data_ingestor.process({})
        assert result['status'] == 'error'
        assert 'Missing required input' in result['error']
        
        # Test with partial input
        result = await data_ingestor.process({'file_path': 'test.pdf'})
        assert result['status'] == 'error'
        assert 'Missing required input' in result['error']
    
    @pytest.mark.asyncio
    async def test_process_unsupported_file_type(self, data_ingestor):
        """Test process with unsupported file type"""
        result = await data_ingestor.process({
            'file_path': 'test.doc',
            'document_id': 'test-doc-1'
        })
        assert result['status'] == 'error'
        assert 'Unsupported file type' in result['error']
    
    @pytest.mark.asyncio
    @patch('agents.data_ingestor.data_ingestor.fitz.open')
    @patch('os.path.getsize', return_value=1024)
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    async def test_process_pdf(self, mock_file, mock_makedirs, mock_getsize, mock_fitz_open, data_ingestor):
        """Test processing a PDF file"""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author',
            'subject': 'Test Subject',
            'keywords': 'test, document',
            'creationDate': '2025-05-19',
            'modDate': '2025-05-19'
        }
        mock_doc.__len__.return_value = 2
        
        # Mock PDF pages
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = 'This is page 1 content.'
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = 'This is page 2 content.'
        mock_doc.__iter__.return_value = [mock_page1, mock_page2]
        
        mock_fitz_open.return_value = mock_doc
        
        # Process PDF
        result = await data_ingestor.process({
            'file_path': 'test.pdf',
            'document_id': 'test-doc-1',
            'metadata': {
                'project_code': 'TEST01',
                'developer': 'Test Developer'
            }
        })
        
        # Verify result
        assert result['status'] == 'success'
        assert result['document_id'] == 'test-doc-1'
        assert len(result['chunks']) == 2
        assert 'This is page 1 content.' in result['chunks'][0]['text']
        assert 'This is page 2 content.' in result['chunks'][1]['text']
        assert result['metadata']['project_code'] == 'TEST01'
        assert result['metadata']['developer'] == 'Test Developer'
        
        # Verify file operations
        mock_makedirs.assert_called()
        mock_file.assert_called()
    
    @pytest.mark.asyncio
    @patch('agents.data_ingestor.data_ingestor.pd.ExcelFile')
    @patch('agents.data_ingestor.data_ingestor.pd.read_excel')
    @patch('os.path.getsize', return_value=1024)
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    async def test_process_excel(self, mock_file, mock_makedirs, mock_getsize, mock_read_excel, mock_excel_file, data_ingestor):
        """Test processing an Excel file"""
        # Mock Excel file
        mock_xl = MagicMock()
        mock_xl.sheet_names = ['Sheet1', 'Sheet2']
        mock_excel_file.return_value = mock_xl
        
        # Mock DataFrame
        mock_df = MagicMock()
        mock_df.to_string.return_value = 'Column1,Column2\nValue1,Value2\nValue3,Value4'
        mock_read_excel.return_value = mock_df
        
        # Process Excel
        result = await data_ingestor.process({
            'file_path': 'test.xlsx',
            'document_id': 'test-doc-2',
            'metadata': {
                'project_code': 'TEST02',
                'developer': 'Test Developer'
            }
        })
        
        # Verify result
        assert result['status'] == 'success'
        assert result['document_id'] == 'test-doc-2'
        assert len(result['chunks']) == 2
        assert 'Sheet: Sheet1' in result['chunks'][0]['text']
        assert 'Sheet: Sheet2' in result['chunks'][1]['text']
        assert result['metadata']['project_code'] == 'TEST02'
        assert result['metadata']['developer'] == 'Test Developer'
        
        # Verify file operations
        mock_makedirs.assert_called()
        mock_file.assert_called()
    
    @pytest.mark.asyncio
    @patch('agents.data_ingestor.data_ingestor.Image.open')
    @patch('os.path.getsize', return_value=1024)
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    async def test_process_image(self, mock_file, mock_makedirs, mock_getsize, mock_image_open, data_ingestor):
        """Test processing an image file"""
        # Mock image
        mock_img = MagicMock()
        mock_img.width = 1920
        mock_img.height = 1080
        mock_img.format = 'JPEG'
        mock_img.mode = 'RGB'
        mock_img.__enter__.return_value = mock_img
        mock_image_open.return_value = mock_img
        
        # Process image
        result = await data_ingestor.process({
            'file_path': 'test.jpg',
            'document_id': 'test-doc-3',
            'metadata': {
                'project_code': 'TEST03',
                'developer': 'Test Developer'
            }
        })
        
        # Verify result
        assert result['status'] == 'success'
        assert result['document_id'] == 'test-doc-3'
        assert len(result['chunks']) == 1
        assert 'Image: test.jpg' in result['chunks'][0]['text']
        assert 'Dimensions: 1920x1080' in result['chunks'][0]['text']
        assert result['metadata']['project_code'] == 'TEST03'
        assert result['metadata']['developer'] == 'Test Developer'
        
        # Verify file operations
        mock_makedirs.assert_called()
        mock_file.assert_called()
    
    def test_chunk_content(self, data_ingestor):
        """Test content chunking logic"""
        # Create test content
        content = [
            {
                'text': 'This is a test paragraph.\n\nThis is another paragraph.\n\nAnd a third paragraph.',
                'type': 'text',
                'page_no': 1
            }
        ]
        metadata = {'project_code': 'TEST', 'developer': 'Test Developer'}
        
        # Chunk content
        chunks = data_ingestor._chunk_content(content, metadata)
        
        # Verify chunks
        assert len(chunks) == 1
        assert chunks[0]['text'] == 'This is a test paragraph.\n\nThis is another paragraph.\n\nAnd a third paragraph.'
        assert chunks[0]['metadata']['project_code'] == 'TEST'
        assert chunks[0]['metadata']['developer'] == 'Test Developer'
        assert chunks[0]['metadata']['page_no'] == 1
        assert chunks[0]['metadata']['type'] == 'text'
        
        # Test with longer content that should be split
        long_text = '\n\n'.join(['Paragraph ' + str(i) * 200 for i in range(10)])
        content = [
            {
                'text': long_text,
                'type': 'text',
                'page_no': 1
            }
        ]
        
        # Chunk content
        chunks = data_ingestor._chunk_content(content, metadata)
        
        # Verify chunks are split
        assert len(chunks) > 1
