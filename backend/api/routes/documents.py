"""
Document management endpoints for PropPulse API
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime

router = APIRouter()


class DocumentMetadata(BaseModel):
    """Document metadata model"""
    document_id: str
    filename: str
    file_type: str
    project_code: Optional[str] = None
    developer: Optional[str] = None
    upload_timestamp: str
    status: str
    vector_ids: Optional[List[str]] = None


class DocumentResponse(BaseModel):
    """Document upload response model"""
    document_id: str
    status: str
    message: str


@router.post("/add", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def add_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_code: Optional[str] = Form(None),
    developer: Optional[str] = Form(None)
):
    """
    Upload and process a new document
    
    Args:
        background_tasks: FastAPI background tasks
        file: The document file to upload (PDF, XLS, XLSX, JPEG, PNG)
        project_code: Optional project code for the document
        developer: Optional developer name
        
    Returns:
        DocumentResponse: Document upload status
    """
    # Validate file type
    allowed_extensions = ['.pdf', '.xls', '.xlsx', '.jpeg', '.jpg', '.png']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Generate document ID
    document_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # In a real implementation, we would:
    # 1. Save the file to storage
    # 2. Queue the document for processing by DataIngestor agent
    # 3. Store metadata in database
    
    # For now, we'll just simulate accepting the document
    # background_tasks.add_task(process_document, document_id, file, project_code, developer)
    
    return {
        "document_id": document_id,
        "status": "processing",
        "message": f"Document '{file.filename}' accepted and queued for processing"
    }


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str):
    """
    Get document metadata by ID
    
    Args:
        document_id: The document ID
        
    Returns:
        DocumentMetadata: Document metadata
    """
    # In a real implementation, we would fetch this from the database
    # For now, return a mock response
    if not document_id.startswith("doc_"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    return {
        "document_id": document_id,
        "filename": "sample_brochure.pdf",
        "file_type": "pdf",
        "project_code": "DOWNTOWN01",
        "developer": "Emaar Properties",
        "upload_timestamp": datetime.utcnow().isoformat(),
        "status": "processed",
        "vector_ids": [f"{document_id}_chunk_{i}" for i in range(1, 6)]
    }
