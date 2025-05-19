"""
DataIngestor integration with GPT-4o for column mapping.

This module provides backend API endpoints for:
1. Initializing chunked uploads
2. Processing chunks
3. Completing uploads
4. Processing files with DataIngestor
5. Smart column mapping with GPT-4o
"""

import os
import json
import uuid
import tempfile
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from openai import OpenAI

from ...db.models.upload import UploadSession, UploadChunk, ProcessedFile, UploadError
from ...agents.data_ingestor.data_ingestor import DataIngestor
from ...utils.auth import get_current_user

# Initialize router
router = APIRouter(prefix="/api/dev", tags=["developer"])

# Get OpenAI API key from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
openai_api_key = secret_client.get_secret("OPENAI-API-KEY").value

# Initialize OpenAI client
openai_client = OpenAI(api_key=openai_api_key)

# Temporary storage for chunks (in production, use blob storage)
TEMP_UPLOAD_DIR = tempfile.gettempdir()

# Models
class UploadInitRequest(BaseModel):
    fileName: str
    fileType: str
    fileSize: int

class UploadInitResponse(BaseModel):
    uploadId: str

class ChunkUploadResponse(BaseModel):
    success: bool
    message: str

class UploadCompleteRequest(BaseModel):
    uploadId: str
    fileName: str
    fileType: str

class UploadCompleteResponse(BaseModel):
    fileId: str
    success: bool

class ProcessFileRequest(BaseModel):
    fileId: str

class ColumnMapping(BaseModel):
    fileId: str
    columnMappings: Dict[str, str]

# Helper functions
def create_upload_session(file_name: str, file_type: str, file_size: int, user_id: str) -> str:
    """Create a new upload session and return the upload ID."""
    upload_id = str(uuid.uuid4())
    
    # In a real implementation, save to database
    # For now, we'll save to a temporary file
    session_info = {
        "upload_id": upload_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_size": file_size,
        "user_id": user_id,
        "chunks_received": 0,
        "total_chunks": 0,
        "status": "initialized"
    }
    
    os.makedirs(os.path.join(TEMP_UPLOAD_DIR, upload_id), exist_ok=True)
    with open(os.path.join(TEMP_UPLOAD_DIR, upload_id, "session.json"), "w") as f:
        json.dump(session_info, f)
    
    return upload_id

def save_chunk(upload_id: str, chunk_index: int, total_chunks: int, chunk_data: bytes) -> bool:
    """Save a chunk of the uploaded file."""
    try:
        # Update session info
        session_file = os.path.join(TEMP_UPLOAD_DIR, upload_id, "session.json")
        with open(session_file, "r") as f:
            session_info = json.load(f)
        
        session_info["chunks_received"] += 1
        session_info["total_chunks"] = total_chunks
        
        with open(session_file, "w") as f:
            json.dump(session_info, f)
        
        # Save chunk
        chunk_file = os.path.join(TEMP_UPLOAD_DIR, upload_id, f"chunk_{chunk_index}")
        with open(chunk_file, "wb") as f:
            f.write(chunk_data)
        
        return True
    except Exception as e:
        print(f"Error saving chunk: {e}")
        return False

def complete_upload(upload_id: str) -> str:
    """Combine chunks into a complete file and return the file ID."""
    try:
        # Get session info
        session_file = os.path.join(TEMP_UPLOAD_DIR, upload_id, "session.json")
        with open(session_file, "r") as f:
            session_info = json.load(f)
        
        # Check if all chunks are received
        if session_info["chunks_received"] != session_info["total_chunks"]:
            raise ValueError("Not all chunks have been received")
        
        # Combine chunks
        file_id = str(uuid.uuid4())
        output_file = os.path.join(TEMP_UPLOAD_DIR, file_id)
        
        with open(output_file, "wb") as outfile:
            for i in range(session_info["total_chunks"]):
                chunk_file = os.path.join(TEMP_UPLOAD_DIR, upload_id, f"chunk_{i}")
                with open(chunk_file, "rb") as infile:
                    outfile.write(infile.read())
        
        # Update session status
        session_info["status"] = "completed"
        session_info["file_id"] = file_id
        
        with open(session_file, "w") as f:
            json.dump(session_info, f)
        
        return file_id
    except Exception as e:
        print(f"Error completing upload: {e}")
        raise

def process_file_with_data_ingestor(file_id: str, file_type: str) -> Dict[str, Any]:
    """Process the uploaded file with DataIngestor and return initial analysis."""
    try:
        file_path = os.path.join(TEMP_UPLOAD_DIR, file_id)
        
        # Initialize DataIngestor
        ingestor = DataIngestor()
        
        # Process file based on type
        if file_type == "application/pdf":
            # PDF processing
            result = ingestor.process_pdf(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel", "text/csv"]:
            # Excel/CSV processing
            result = ingestor.process_tabular(file_path)
        elif file_type in ["model/ifc", "model/gltf-binary"]:
            # IFC/GLB processing
            result = ingestor.process_model(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Extract columns and sample data for mapping
        columns = []
        
        if hasattr(result, 'data') and isinstance(result.data, pd.DataFrame):
            df = result.data
            
            for col in df.columns:
                sample_data = df[col].dropna().head(3).tolist()
                sample_data = [str(s) for s in sample_data]
                
                columns.append({
                    "name": col,
                    "sampleData": ", ".join(sample_data)
                })
            
            # Generate smart column mappings with GPT-4o
            column_mappings = generate_smart_column_mappings(df)
        else:
            # For non-tabular data
            columns = result.get("extracted_fields", [])
            column_mappings = {}
        
        return {
            "fileId": file_id,
            "columns": columns,
            "rowCount": len(df) if 'df' in locals() else 0,
            "columnMappings": column_mappings,
            "status": "processed"
        }
    except Exception as e:
        print(f"Error processing file: {e}")
        # Store error for later retrieval
        error_id = str(uuid.uuid4())
        error_file = os.path.join(TEMP_UPLOAD_DIR, f"error_{error_id}.json")
        with open(error_file, "w") as f:
            json.dump({
                "file_id": file_id,
                "error": str(e),
                "timestamp": str(pd.Timestamp.now())
            }, f)
        
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

def generate_smart_column_mappings(df: pd.DataFrame) -> Dict[str, str]:
    """Use GPT-4o to generate smart column mappings based on column names and sample data."""
    try:
        # Prepare data for GPT-4o
        columns_info = []
        for col in df.columns:
            sample_data = df[col].dropna().head(5).tolist()
            sample_data = [str(s) for s in sample_data]
            
            columns_info.append({
                "name": col,
                "samples": sample_data
            })
        
        # Define property fields
        property_fields = [
            "unit_no", "tower", "floor", "unit_type", "bedrooms", "bathrooms", 
            "size_ft2", "price", "view", "status", "completion_date", 
            "payment_plan", "description", "features", "latitude", "longitude"
        ]
        
        # Create prompt for GPT-4o
        prompt = f"""
        You are an AI assistant helping to map columns from a real estate data file to standardized property fields.
        
        Here are the columns from the uploaded file with sample data:
        {json.dumps(columns_info, indent=2)}
        
        Please map each column to one of the following property fields:
        {", ".join(property_fields)}
        
        If a column doesn't match any field, leave it unmapped.
        
        Return your answer as a JSON object with column names as keys and property fields as values.
        Example: {{"Unit": "unit_no", "Tower/Building": "tower", "Price (AED)": "price"}}
        """
        
        # Call GPT-4o API
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that maps real estate data columns to standardized fields. Respond only with the JSON mapping."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        # Extract and parse the mapping
        mapping_text = response.choices[0].message.content
        
        # Clean up the response to extract just the JSON part
        mapping_text = mapping_text.strip()
        if mapping_text.startswith("```json"):
            mapping_text = mapping_text[7:]
        if mapping_text.endswith("```"):
            mapping_text = mapping_text[:-3]
        mapping_text = mapping_text.strip()
        
        column_mappings = json.loads(mapping_text)
        
        return column_mappings
    except Exception as e:
        print(f"Error generating smart column mappings: {e}")
        # Return empty mappings if GPT-4o fails
        return {}

def apply_column_mappings(file_id: str, column_mappings: Dict[str, str]) -> Dict[str, Any]:
    """Apply column mappings to the processed file and ingest into the database."""
    try:
        file_path = os.path.join(TEMP_UPLOAD_DIR, file_id)
        
        # Load the file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            # For non-tabular data, we'd need a different approach
            # This is simplified for the example
            raise ValueError("Only tabular data supported for column mapping")
        
        # Rename columns based on mappings
        rename_dict = {}
        for original_col, mapped_field in column_mappings.items():
            if mapped_field and original_col in df.columns:
                rename_dict[original_col] = mapped_field
        
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        # Initialize DataIngestor
        ingestor = DataIngestor()
        
        # Ingest the mapped data
        result = ingestor.ingest_properties(df)
        
        # Generate error report if needed
        error_report_url = None
        if result.get("error_count", 0) > 0:
            error_df = pd.DataFrame(result.get("errors", []))
            error_file_id = str(uuid.uuid4())
            error_file_path = os.path.join(TEMP_UPLOAD_DIR, f"error_report_{error_file_id}.csv")
            error_df.to_csv(error_file_path, index=False)
            error_report_url = f"/api/dev/download/error-report/{error_file_id}"
        
        return {
            "processedCount": result.get("processed_count", 0),
            "errorCount": result.get("error_count", 0),
            "errorReportUrl": error_report_url,
            "status": "ingested"
        }
    except Exception as e:
        print(f"Error applying column mappings: {e}")
        raise HTTPException(status_code=500, detail=f"Error applying column mappings: {str(e)}")

# API Endpoints
@router.post("/upload/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Initialize a new chunked upload."""
    upload_id = create_upload_session(
        request.fileName,
        request.fileType,
        request.fileSize,
        current_user["id"]
    )
    
    return {"uploadId": upload_id}

@router.post("/upload/chunk", response_model=ChunkUploadResponse)
async def upload_chunk(
    uploadId: str = Form(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    chunk: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """Upload a chunk of a file."""
    chunk_data = await chunk.read()
    success = save_chunk(uploadId, chunkIndex, totalChunks, chunk_data)
    
    if success:
        return {"success": True, "message": "Chunk uploaded successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save chunk")

@router.post("/upload/complete", response_model=UploadCompleteResponse)
async def complete_upload_endpoint(
    request: UploadCompleteRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Complete a chunked upload by combining all chunks."""
    try:
        file_id = complete_upload(request.uploadId)
        return {"fileId": file_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process", response_model=Dict[str, Any])
async def process_file(
    request: ProcessFileRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Process an uploaded file with DataIngestor."""
    # Get file type from session info
    session_file = os.path.join(TEMP_UPLOAD_DIR, request.fileId, "session.json")
    if not os.path.exists(session_file):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(session_file, "r") as f:
        session_info = json.load(f)
    
    file_type = session_info.get("file_type")
    
    # Process the file
    result = process_file_with_data_ingestor(request.fileId, file_type)
    return result

@router.post("/column-mapping", response_model=Dict[str, Any])
async def apply_column_mapping(
    request: ColumnMapping,
    current_user: Dict = Depends(get_current_user)
):
    """Apply column mappings and ingest data into the database."""
    result = apply_column_mappings(request.fileId, request.columnMappings)
    return result

@router.get("/download/error-report/{error_id}")
async def download_error_report(
    error_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Download an error report CSV."""
    file_path = os.path.join(TEMP_UPLOAD_DIR, f"error_report_{error_id}.csv")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Error report not found")
    
    # In a real implementation, you'd return a FileResponse
    # For this example, we'll just return a success message
    return {"success": True, "message": "Error report download endpoint"}
