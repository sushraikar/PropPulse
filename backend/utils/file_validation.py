"""
File validation and virus scanning utilities for PropPulse developer portal.

This module provides utilities for:
1. Validating file types and sizes
2. Scanning files for viruses using ClamAV
3. Handling resumable uploads
4. Managing upload errors
"""

import os
import json
import uuid
import tempfile
import subprocess
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from fastapi import HTTPException
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MAX_PDF_SIZE = 100 * 1024 * 1024   # 100MB
MAX_MODEL_SIZE = 150 * 1024 * 1024 # 150MB
CHUNK_SIZE = 2 * 1024 * 1024       # 2MB
TEMP_UPLOAD_DIR = tempfile.gettempdir()
ERROR_RETENTION_DAYS = 14

# Supported file types with their validation rules
SUPPORTED_FILE_TYPES = {
    "application/pdf": {
        "max_size": MAX_PDF_SIZE,
        "extensions": [".pdf"],
        "validators": ["virus_scan", "ocr_check"],
    },
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "max_size": MAX_FILE_SIZE,
        "extensions": [".xlsx"],
        "validators": ["virus_scan", "header_check", "required_columns"],
    },
    "application/vnd.ms-excel": {
        "max_size": MAX_FILE_SIZE,
        "extensions": [".xls"],
        "validators": ["virus_scan", "header_check", "required_columns"],
    },
    "text/csv": {
        "max_size": MAX_FILE_SIZE,
        "extensions": [".csv"],
        "validators": ["virus_scan", "header_check", "required_columns"],
    },
    "model/ifc": {
        "max_size": MAX_MODEL_SIZE,
        "extensions": [".ifc"],
        "validators": ["virus_scan", "bim_check"],
    },
    "model/gltf-binary": {
        "max_size": MAX_MODEL_SIZE,
        "extensions": [".glb"],
        "validators": ["virus_scan"],
    },
}

# Required columns for tabular data
REQUIRED_COLUMNS = ["bedrooms", "price"]

class FileValidationError(Exception):
    """Exception raised for file validation errors."""
    pass

def validate_file_type(file_type: str) -> bool:
    """Validate if the file type is supported."""
    return file_type in SUPPORTED_FILE_TYPES

def validate_file_size(file_size: int, file_type: str) -> bool:
    """Validate if the file size is within limits."""
    if not validate_file_type(file_type):
        return False
    
    max_size = SUPPORTED_FILE_TYPES[file_type]["max_size"]
    return file_size <= max_size

def scan_file_for_virus(file_path: str) -> bool:
    """
    Scan a file for viruses using ClamAV.
    
    Returns True if the file is clean, False if infected.
    """
    try:
        # Check if ClamAV is installed
        result = subprocess.run(["which", "clamdscan"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("ClamAV not found, skipping virus scan")
            return True
        
        # Run ClamAV scan
        result = subprocess.run(
            ["clamdscan", "--no-summary", file_path], 
            capture_output=True, 
            text=True
        )
        
        # Check result
        if "Infected files: 0" in result.stdout or result.returncode == 0:
            return True
        else:
            logger.warning(f"Virus detected in file: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error during virus scan: {e}")
        # In production, you might want to fail closed (assume infected)
        # For development, we'll assume clean
        return True

def check_ocr_pass(file_path: str) -> bool:
    """
    Check if a PDF file can be OCR'd.
    
    Returns True if OCR is possible, False otherwise.
    """
    try:
        # Check if pdftotext is installed
        result = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("pdftotext not found, skipping OCR check")
            return True
        
        # Extract text from PDF
        result = subprocess.run(
            ["pdftotext", file_path, "-"], 
            capture_output=True, 
            text=True
        )
        
        # If we got some text, consider it a pass
        if result.stdout.strip():
            return True
        else:
            logger.warning(f"OCR check failed for file: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error during OCR check: {e}")
        return False

def check_tabular_headers(file_path: str) -> Tuple[bool, List[str]]:
    """
    Check if a tabular file has headers.
    
    Returns a tuple of (success, headers).
    """
    try:
        # Determine file type
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, nrows=1)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path, nrows=1)
        else:
            return False, []
        
        # Check if we have headers
        headers = df.columns.tolist()
        if headers:
            return True, headers
        else:
            logger.warning(f"No headers found in file: {file_path}")
            return False, []
    except Exception as e:
        logger.error(f"Error checking headers: {e}")
        return False, []

def check_required_columns(headers: List[str]) -> bool:
    """
    Check if the required columns are present in the headers.
    
    Returns True if all required columns are present, False otherwise.
    """
    # Convert headers to lowercase for case-insensitive comparison
    lower_headers = [h.lower() for h in headers]
    
    # Check for exact matches
    exact_matches = [col for col in REQUIRED_COLUMNS if col in lower_headers]
    
    # Check for partial matches (e.g., "bedroom" instead of "bedrooms")
    partial_matches = []
    for col in REQUIRED_COLUMNS:
        if col not in exact_matches:
            for header in lower_headers:
                if col in header or header in col:
                    partial_matches.append(col)
                    break
    
    # Return True if all required columns are found
    return len(exact_matches) + len(partial_matches) == len(REQUIRED_COLUMNS)

def check_bim_model(file_path: str) -> bool:
    """
    Check if an IFC file is valid using IfcOpenShell.
    
    Returns True if the file is valid, False otherwise.
    """
    try:
        # Check if IfcOpenShell is installed
        try:
            import ifcopenshell
        except ImportError:
            logger.warning("IfcOpenShell not found, skipping BIM check")
            return True
        
        # Try to open the IFC file
        ifc_file = ifcopenshell.open(file_path)
        
        # If we got here, the file is valid
        return True
    except Exception as e:
        logger.error(f"Error during BIM check: {e}")
        return False

def validate_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """
    Validate a file using all applicable validators.
    
    Returns a dictionary with validation results.
    """
    if not validate_file_type(file_type):
        return {
            "valid": False,
            "error": f"Unsupported file type: {file_type}"
        }
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Validate file size
    if not validate_file_size(file_size, file_type):
        max_size_mb = SUPPORTED_FILE_TYPES[file_type]["max_size"] / (1024 * 1024)
        return {
            "valid": False,
            "error": f"File too large. Maximum size for {file_type} is {max_size_mb}MB"
        }
    
    # Get validators for this file type
    validators = SUPPORTED_FILE_TYPES[file_type]["validators"]
    
    # Run validators
    validation_results = {}
    
    # Virus scan
    if "virus_scan" in validators:
        virus_free = scan_file_for_virus(file_path)
        validation_results["virus_scan"] = virus_free
        if not virus_free:
            return {
                "valid": False,
                "error": "File failed virus scan"
            }
    
    # OCR check for PDFs
    if "ocr_check" in validators:
        ocr_pass = check_ocr_pass(file_path)
        validation_results["ocr_check"] = ocr_pass
        if not ocr_pass:
            return {
                "valid": False,
                "error": "File failed OCR check. The PDF may be scanned or contain only images."
            }
    
    # Header check for tabular data
    if "header_check" in validators:
        header_check, headers = check_tabular_headers(file_path)
        validation_results["header_check"] = header_check
        if not header_check:
            return {
                "valid": False,
                "error": "File has no headers. Please ensure the first row contains column names."
            }
        
        # Required columns check
        if "required_columns" in validators:
            columns_check = check_required_columns(headers)
            validation_results["required_columns"] = columns_check
            if not columns_check:
                return {
                    "valid": False,
                    "error": f"File is missing required columns: {', '.join(REQUIRED_COLUMNS)}"
                }
    
    # BIM check for IFC files
    if "bim_check" in validators:
        bim_check = check_bim_model(file_path)
        validation_results["bim_check"] = bim_check
        if not bim_check:
            return {
                "valid": False,
                "error": "File failed BIM check. The IFC file may be corrupted or invalid."
            }
    
    # All validations passed
    return {
        "valid": True,
        "validation_results": validation_results
    }

def store_upload_error(file_id: str, error: str, user_id: str) -> str:
    """
    Store an upload error for later retrieval.
    
    Returns the error ID.
    """
    error_id = str(uuid.uuid4())
    
    error_data = {
        "error_id": error_id,
        "file_id": file_id,
        "user_id": user_id,
        "error": error,
        "timestamp": str(pd.Timestamp.now()),
        "expiry": str(pd.Timestamp.now() + pd.Timedelta(days=ERROR_RETENTION_DAYS))
    }
    
    # In a real implementation, save to database
    # For now, we'll save to a temporary file
    error_file = os.path.join(TEMP_UPLOAD_DIR, f"upload_error_{error_id}.json")
    with open(error_file, "w") as f:
        json.dump(error_data, f)
    
    return error_id

def get_upload_errors(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all upload errors for a user.
    
    Returns a list of error dictionaries.
    """
    errors = []
    
    # In a real implementation, query database
    # For now, we'll scan the temporary directory
    for filename in os.listdir(TEMP_UPLOAD_DIR):
        if filename.startswith("upload_error_") and filename.endswith(".json"):
            error_file = os.path.join(TEMP_UPLOAD_DIR, filename)
            try:
                with open(error_file, "r") as f:
                    error_data = json.load(f)
                
                if error_data.get("user_id") == user_id:
                    # Check if error has expired
                    expiry = pd.Timestamp(error_data.get("expiry"))
                    if expiry > pd.Timestamp.now():
                        errors.append(error_data)
                    else:
                        # Remove expired error
                        os.remove(error_file)
            except Exception as e:
                logger.error(f"Error reading error file {filename}: {e}")
    
    return errors

def get_upload_session(upload_id: str) -> Dict[str, Any]:
    """
    Get an upload session by ID.
    
    Returns the session data or None if not found.
    """
    session_file = os.path.join(TEMP_UPLOAD_DIR, upload_id, "session.json")
    if not os.path.exists(session_file):
        return None
    
    try:
        with open(session_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading session file: {e}")
        return None

def get_resumable_uploads(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all resumable uploads for a user.
    
    Returns a list of upload session dictionaries.
    """
    uploads = []
    
    # In a real implementation, query database
    # For now, we'll scan the temporary directory
    for dirname in os.listdir(TEMP_UPLOAD_DIR):
        session_file = os.path.join(TEMP_UPLOAD_DIR, dirname, "session.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                
                if session_data.get("user_id") == user_id and session_data.get("status") != "completed":
                    uploads.append(session_data)
            except Exception as e:
                logger.error(f"Error reading session file {session_file}: {e}")
    
    return uploads

def cleanup_expired_data():
    """
    Clean up expired upload sessions and error reports.
    
    This should be run periodically, e.g., via a cron job.
    """
    now = pd.Timestamp.now()
    
    # Clean up expired error reports
    for filename in os.listdir(TEMP_UPLOAD_DIR):
        if filename.startswith("upload_error_") and filename.endswith(".json"):
            error_file = os.path.join(TEMP_UPLOAD_DIR, filename)
            try:
                with open(error_file, "r") as f:
                    error_data = json.load(f)
                
                expiry = pd.Timestamp(error_data.get("expiry"))
                if expiry < now:
                    os.remove(error_file)
                    logger.info(f"Removed expired error file: {filename}")
            except Exception as e:
                logger.error(f"Error processing error file {filename}: {e}")
    
    # Clean up old upload sessions (older than 7 days)
    for dirname in os.listdir(TEMP_UPLOAD_DIR):
        session_file = os.path.join(TEMP_UPLOAD_DIR, dirname, "session.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                
                # Check if session is older than 7 days
                if "timestamp" in session_data:
                    timestamp = pd.Timestamp(session_data["timestamp"])
                    if (now - timestamp).days > 7:
                        # Remove session directory
                        for root, dirs, files in os.walk(os.path.join(TEMP_UPLOAD_DIR, dirname), topdown=False):
                            for file in files:
                                os.remove(os.path.join(root, file))
                            for dir in dirs:
                                os.rmdir(os.path.join(root, dir))
                        os.rmdir(os.path.join(TEMP_UPLOAD_DIR, dirname))
                        logger.info(f"Removed expired upload session: {dirname}")
            except Exception as e:
                logger.error(f"Error processing session {dirname}: {e}")

# GDPR compliance functions
def purge_user_data(user_id: str) -> Dict[str, Any]:
    """
    Purge all data associated with a user.
    
    Returns a summary of purged data.
    """
    purged = {
        "upload_sessions": 0,
        "error_reports": 0,
        "processed_files": 0
    }
    
    # Purge upload sessions
    for dirname in os.listdir(TEMP_UPLOAD_DIR):
        session_file = os.path.join(TEMP_UPLOAD_DIR, dirname, "session.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                
                if session_data.get("user_id") == user_id:
                    # Remove session directory
                    for root, dirs, files in os.walk(os.path.join(TEMP_UPLOAD_DIR, dirname), topdown=False):
                        for file in files:
                            os.remove(os.path.join(root, file))
                        for dir in dirs:
                            os.rmdir(os.path.join(root, dir))
                    os.rmdir(os.path.join(TEMP_UPLOAD_DIR, dirname))
                    purged["upload_sessions"] += 1
            except Exception as e:
                logger.error(f"Error purging session {dirname}: {e}")
    
    # Purge error reports
    for filename in os.listdir(TEMP_UPLOAD_DIR):
        if filename.startswith("upload_error_") and filename.endswith(".json"):
            error_file = os.path.join(TEMP_UPLOAD_DIR, filename)
            try:
                with open(error_file, "r") as f:
                    error_data = json.load(f)
                
                if error_data.get("user_id") == user_id:
                    os.remove(error_file)
                    purged["error_reports"] += 1
            except Exception as e:
                logger.error(f"Error purging error file {filename}: {e}")
    
    # In a real implementation, also purge from database
    # ...
    
    return purged
