"""
DataIngestor agent for PropPulse
Responsible for ingesting, processing, and chunking documents
"""
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
import asyncio
from datetime import datetime
import tempfile
import json

# PDF processing
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import io

# For chunking
import re
from math import ceil

# Import base agent
from agents.base_agent import BaseAgent


class DataIngestor(BaseAgent):
    """
    DataIngestor agent processes real estate brochures and developer price sheets.
    
    Responsibilities:
    - Extract text and metadata from various file formats (PDF, XLS, XLSX, JPEG, PNG)
    - Chunk text into segments of approximately 1000 tokens
    - Store metadata with each chunk (page_no, project_code, etc.)
    - Prepare data for vector embedding and storage
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the DataIngestor agent"""
        super().__init__(config)
        self.supported_extensions = ['.pdf', '.xls', '.xlsx', '.jpeg', '.jpg', '.png']
        self.chunk_size = self.get_config_value('chunk_size', 1000)
        self.storage_path = self.get_config_value('storage_path', '/tmp/proppulse/documents')
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a document and extract content and metadata.
        
        Args:
            input_data: Dictionary containing:
                - file_path: Path to the document file
                - document_id: Unique identifier for the document
                - metadata: Optional metadata dictionary
                
        Returns:
            Dict containing:
                - document_id: The document ID
                - chunks: List of text chunks with metadata
                - status: Processing status
                - error: Error message if any
        """
        # Validate input
        required_keys = ['file_path', 'document_id']
        if not self.validate_input(input_data, required_keys):
            return {
                'document_id': input_data.get('document_id', 'unknown'),
                'status': 'error',
                'error': 'Missing required input: file_path or document_id'
            }
        
        file_path = input_data['file_path']
        document_id = input_data['document_id']
        metadata = input_data.get('metadata', {})
        
        # Validate file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_extensions:
            return {
                'document_id': document_id,
                'status': 'error',
                'error': f'Unsupported file type: {file_ext}. Supported types: {", ".join(self.supported_extensions)}'
            }
        
        try:
            # Extract content based on file type
            if file_ext in ['.pdf']:
                content, doc_metadata = await self._process_pdf(file_path)
            elif file_ext in ['.xls', '.xlsx']:
                content, doc_metadata = await self._process_excel(file_path)
            elif file_ext in ['.jpeg', '.jpg', '.png']:
                content, doc_metadata = await self._process_image(file_path)
            else:
                # This should never happen due to the validation above
                return {
                    'document_id': document_id,
                    'status': 'error',
                    'error': f'Unsupported file type: {file_ext}'
                }
            
            # Merge extracted metadata with provided metadata
            combined_metadata = {**doc_metadata, **metadata}
            
            # Chunk the content
            chunks = self._chunk_content(content, combined_metadata)
            
            # Save chunks to storage
            await self._save_chunks(document_id, chunks)
            
            return {
                'document_id': document_id,
                'chunks': chunks,
                'status': 'success',
                'metadata': combined_metadata
            }
            
        except Exception as e:
            return {
                'document_id': document_id,
                'status': 'error',
                'error': f'Error processing document: {str(e)}'
            }
    
    async def _process_pdf(self, file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a PDF file and extract text and metadata.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple containing:
                - List of page content dictionaries
                - Document metadata dictionary
        """
        content = []
        metadata = {}
        
        try:
            # Open the PDF
            doc = fitz.open(file_path)
            
            # Extract document metadata
            metadata = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'keywords': doc.metadata.get('keywords', ''),
                'page_count': len(doc),
                'file_size': os.path.getsize(file_path),
                'creation_date': doc.metadata.get('creationDate', ''),
                'modification_date': doc.metadata.get('modDate', '')
            }
            
            # Process each page
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                
                # Extract images if needed (simplified)
                # images = page.get_images(full=True)
                
                content.append({
                    'page_no': page_num + 1,
                    'text': page_text,
                    'type': 'pdf_page'
                })
            
            return content, metadata
            
        except Exception as e:
            raise Exception(f"Error processing PDF: {str(e)}")
    
    async def _process_excel(self, file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process an Excel file and extract data and metadata.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            Tuple containing:
                - List of sheet content dictionaries
                - Document metadata dictionary
        """
        content = []
        metadata = {}
        
        try:
            # Read Excel file
            xl = pd.ExcelFile(file_path)
            
            # Extract document metadata
            metadata = {
                'file_size': os.path.getsize(file_path),
                'sheet_count': len(xl.sheet_names),
                'sheet_names': xl.sheet_names
            }
            
            # Process each sheet
            for sheet_name in xl.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Convert DataFrame to string representation
                sheet_text = f"Sheet: {sheet_name}\n\n"
                sheet_text += df.to_string(index=False)
                
                content.append({
                    'sheet_name': sheet_name,
                    'text': sheet_text,
                    'type': 'excel_sheet'
                })
            
            return content, metadata
            
        except Exception as e:
            raise Exception(f"Error processing Excel file: {str(e)}")
    
    async def _process_image(self, file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process an image file and extract metadata.
        For images, we primarily store metadata as text extraction would require OCR.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Tuple containing:
                - List with a single image content dictionary
                - Document metadata dictionary
        """
        content = []
        metadata = {}
        
        try:
            # Open the image
            with Image.open(file_path) as img:
                # Extract image metadata
                metadata = {
                    'file_size': os.path.getsize(file_path),
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode
                }
                
                # For images, we store a description rather than extracted text
                # In a real implementation, OCR could be used here
                image_description = f"Image: {os.path.basename(file_path)}\n"
                image_description += f"Dimensions: {img.width}x{img.height}\n"
                image_description += f"Format: {img.format}\n"
                
                content.append({
                    'text': image_description,
                    'type': 'image'
                })
            
            return content, metadata
            
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")
    
    def _chunk_content(self, content: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk content into segments of approximately 1000 tokens.
        
        Args:
            content: List of content dictionaries
            metadata: Document metadata
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        chunks = []
        
        for item in content:
            text = item['text']
            item_metadata = {
                'type': item.get('type', 'text'),
                'page_no': item.get('page_no'),
                'sheet_name': item.get('sheet_name')
            }
            
            # Filter out None values
            item_metadata = {k: v for k, v in item_metadata.items() if v is not None}
            
            # Combine with document metadata
            combined_metadata = {**metadata, **item_metadata}
            
            # Simple chunking by paragraphs and approximate token count
            # In a real implementation, a more sophisticated tokenizer would be used
            paragraphs = text.split('\n\n')
            current_chunk = ""
            current_token_count = 0
            
            for paragraph in paragraphs:
                # Rough estimate: 1 token ≈ 4 characters
                paragraph_token_count = ceil(len(paragraph) / 4)
                
                if current_token_count + paragraph_token_count > self.chunk_size:
                    # Current chunk is full, create a new one
                    if current_chunk:
                        chunk_id = f"{uuid.uuid4().hex}"
                        chunks.append({
                            'chunk_id': chunk_id,
                            'text': current_chunk,
                            'token_count': current_token_count,
                            'metadata': combined_metadata
                        })
                    
                    current_chunk = paragraph
                    current_token_count = paragraph_token_count
                else:
                    # Add paragraph to current chunk
                    if current_chunk:
                        current_chunk += f"\n\n{paragraph}"
                    else:
                        current_chunk = paragraph
                    current_token_count += paragraph_token_count
            
            # Add the last chunk if it's not empty
            if current_chunk:
                chunk_id = f"{uuid.uuid4().hex}"
                chunks.append({
                    'chunk_id': chunk_id,
                    'text': current_chunk,
                    'token_count': current_token_count,
                    'metadata': combined_metadata
                })
        
        return chunks
    
    async def _save_chunks(self, document_id: str, chunks: List[Dict[str, Any]]) -> None:
        """
        Save chunks to storage.
        
        Args:
            document_id: Document ID
            chunks: List of chunk dictionaries
        """
        # Create document directory
        document_dir = os.path.join(self.storage_path, document_id)
        os.makedirs(document_dir, exist_ok=True)
        
        # Save each chunk to a separate file
        for chunk in chunks:
            chunk_file = os.path.join(document_dir, f"{chunk['chunk_id']}.json")
            with open(chunk_file, 'w') as f:
                json.dump(chunk, f, indent=2)
        
        # Save chunk index
        index_file = os.path.join(document_dir, "index.json")
        with open(index_file, 'w') as f:
            json.dump({
                'document_id': document_id,
                'chunk_count': len(chunks),
                'chunk_ids': [chunk['chunk_id'] for chunk in chunks],
                'created_at': datetime.utcnow().isoformat()
            }, f, indent=2)
