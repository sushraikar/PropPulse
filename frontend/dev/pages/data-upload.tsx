import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import { withAuth } from '../../contexts/AuthContext';

// File type icons
import { 
  DocumentTextIcon, 
  TableCellsIcon, 
  DocumentIcon,
  PhotoIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

// Maximum file size (200MB in bytes)
const MAX_FILE_SIZE = 200 * 1024 * 1024;

// Chunk size for uploads (2MB)
const CHUNK_SIZE = 2 * 1024 * 1024;

// Supported file types
const SUPPORTED_FILE_TYPES = {
  'application/pdf': {
    icon: DocumentTextIcon,
    label: 'PDF',
    maxSize: 100 * 1024 * 1024, // 100MB
  },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    icon: TableCellsIcon,
    label: 'Excel',
    maxSize: MAX_FILE_SIZE,
  },
  'application/vnd.ms-excel': {
    icon: TableCellsIcon,
    label: 'Excel',
    maxSize: MAX_FILE_SIZE,
  },
  'text/csv': {
    icon: TableCellsIcon,
    label: 'CSV',
    maxSize: MAX_FILE_SIZE,
  },
  'model/ifc': {
    icon: DocumentIcon,
    label: 'IFC',
    maxSize: 150 * 1024 * 1024, // 150MB
  },
  'model/gltf-binary': {
    icon: DocumentIcon,
    label: 'GLB',
    maxSize: 150 * 1024 * 1024, // 150MB
  },
};

// Upload status enum
const UploadStatus = {
  PENDING: 'pending',
  UPLOADING: 'uploading',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  PAUSED: 'paused',
};

const DataUploadService = () => {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadStatus, setUploadStatus] = useState({});
  const [parseResults, setParseResults] = useState({});
  const [activeFile, setActiveFile] = useState(null);
  const [columnMappings, setColumnMappings] = useState({});
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle file drop
  const onDrop = useCallback((acceptedFiles) => {
    // Filter out unsupported file types and files exceeding size limit
    const validFiles = acceptedFiles.filter(file => {
      const fileType = SUPPORTED_FILE_TYPES[file.type];
      
      if (!fileType) {
        toast.error(`Unsupported file type: ${file.type}`);
        return false;
      }
      
      if (file.size > fileType.maxSize) {
        toast.error(`File too large: ${file.name}. Maximum size for ${fileType.label} is ${fileType.maxSize / (1024 * 1024)}MB`);
        return false;
      }
      
      return true;
    });
    
    // Add valid files to state
    setFiles(prevFiles => [...prevFiles, ...validFiles]);
    
    // Initialize upload progress and status for new files
    const newProgress = { ...uploadProgress };
    const newStatus = { ...uploadStatus };
    
    validFiles.forEach(file => {
      newProgress[file.name] = 0;
      newStatus[file.name] = UploadStatus.PENDING;
    });
    
    setUploadProgress(newProgress);
    setUploadStatus(newStatus);
  }, [uploadProgress, uploadStatus]);

  // Configure dropzone
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: Object.keys(SUPPORTED_FILE_TYPES).reduce((acc, type) => {
      acc[type] = [];
      return acc;
    }, {}),
    maxSize: MAX_FILE_SIZE,
  });

  // Upload a file in chunks
  const uploadFile = async (file) => {
    try {
      // Update status to uploading
      setUploadStatus(prev => ({ ...prev, [file.name]: UploadStatus.UPLOADING }));
      
      // Get upload ID for chunked upload
      const initResponse = await axios.post('/api/dev/upload/init', {
        fileName: file.name,
        fileType: file.type,
        fileSize: file.size,
      });
      
      const { uploadId } = initResponse.data;
      
      // Calculate total chunks
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      let uploadedChunks = 0;
      
      // Upload each chunk
      for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
        const start = chunkIndex * CHUNK_SIZE;
        const end = Math.min(file.size, start + CHUNK_SIZE);
        const chunk = file.slice(start, end);
        
        const formData = new FormData();
        formData.append('uploadId', uploadId);
        formData.append('chunkIndex', chunkIndex);
        formData.append('totalChunks', totalChunks);
        formData.append('chunk', chunk);
        
        await axios.post('/api/dev/upload/chunk', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            // Calculate overall progress for this file
            const chunkProgress = progressEvent.loaded / progressEvent.total;
            const overallProgress = ((chunkIndex + chunkProgress) / totalChunks) * 100;
            
            setUploadProgress(prev => ({
              ...prev,
              [file.name]: Math.round(overallProgress),
            }));
          },
        });
        
        uploadedChunks++;
      }
      
      // Complete upload
      if (uploadedChunks === totalChunks) {
        setUploadStatus(prev => ({ ...prev, [file.name]: UploadStatus.PROCESSING }));
        
        const completeResponse = await axios.post('/api/dev/upload/complete', {
          uploadId,
          fileName: file.name,
          fileType: file.type,
        });
        
        // Process file with DataIngestor
        const processResponse = await axios.post('/api/dev/process', {
          fileId: completeResponse.data.fileId,
        });
        
        // Update parse results
        setParseResults(prev => ({
          ...prev,
          [file.name]: processResponse.data,
        }));
        
        // Update status to completed
        setUploadStatus(prev => ({ ...prev, [file.name]: UploadStatus.COMPLETED }));
        
        // Set as active file for column mapping
        setActiveFile(file.name);
        
        // Initialize column mappings with smart guesses
        setColumnMappings(prev => ({
          ...prev,
          [file.name]: processResponse.data.columnMappings || {},
        }));
        
        toast.success(`File ${file.name} uploaded and processed successfully`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      
      // Update status to failed
      setUploadStatus(prev => ({ ...prev, [file.name]: UploadStatus.FAILED }));
      
      // Store error details
      setParseResults(prev => ({
        ...prev,
        [file.name]: {
          error: error.response?.data?.message || 'Upload failed',
        },
      }));
      
      toast.error(`Failed to upload ${file.name}: ${error.response?.data?.message || 'Unknown error'}`);
    }
  };

  // Retry failed upload
  const retryUpload = (fileName) => {
    const file = files.find(f => f.name === fileName);
    if (file) {
      setUploadProgress(prev => ({ ...prev, [fileName]: 0 }));
      setUploadStatus(prev => ({ ...prev, [fileName]: UploadStatus.PENDING }));
      uploadFile(file);
    }
  };

  // Remove file from list
  const removeFile = (fileName) => {
    setFiles(prev => prev.filter(f => f.name !== fileName));
    
    // Clean up state
    setUploadProgress(prev => {
      const newProgress = { ...prev };
      delete newProgress[fileName];
      return newProgress;
    });
    
    setUploadStatus(prev => {
      const newStatus = { ...prev };
      delete newStatus[fileName];
      return newStatus;
    });
    
    setParseResults(prev => {
      const newResults = { ...prev };
      delete newResults[fileName];
      return newResults;
    });
    
    setColumnMappings(prev => {
      const newMappings = { ...prev };
      delete newMappings[fileName];
      return newMappings;
    });
    
    // If active file is removed, set another file as active
    if (activeFile === fileName) {
      const remainingFiles = files.filter(f => f.name !== fileName);
      if (remainingFiles.length > 0) {
        setActiveFile(remainingFiles[0].name);
      } else {
        setActiveFile(null);
      }
    }
  };

  // Update column mapping
  const updateColumnMapping = (fileName, columnName, propertyField) => {
    setColumnMappings(prev => ({
      ...prev,
      [fileName]: {
        ...prev[fileName],
        [columnName]: propertyField,
      },
    }));
  };

  // Save column mappings and finalize processing
  const saveColumnMappings = async (fileName) => {
    try {
      setIsProcessing(true);
      
      const response = await axios.post('/api/dev/column-mapping', {
        fileId: parseResults[fileName].fileId,
        columnMappings: columnMappings[fileName],
      });
      
      // Update parse results with final processing results
      setParseResults(prev => ({
        ...prev,
        [fileName]: {
          ...prev[fileName],
          finalResults: response.data,
        },
      }));
      
      toast.success(`Column mappings saved for ${fileName}`);
    } catch (error) {
      console.error('Error saving column mappings:', error);
      toast.error(`Failed to save column mappings: ${error.response?.data?.message || 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Start uploads for pending files
  useEffect(() => {
    files.forEach(file => {
      if (uploadStatus[file.name] === UploadStatus.PENDING) {
        uploadFile(file);
      }
    });
  }, [files, uploadStatus]);

  // Render file icon based on type
  const renderFileIcon = (file) => {
    const fileType = SUPPORTED_FILE_TYPES[file.type];
    if (fileType) {
      const Icon = fileType.icon;
      return <Icon className="h-8 w-8 text-gray-500" />;
    }
    return <DocumentIcon className="h-8 w-8 text-gray-500" />;
  };

  // Render status icon
  const renderStatusIcon = (status) => {
    switch (status) {
      case UploadStatus.COMPLETED:
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case UploadStatus.FAILED:
        return <ExclamationCircleIcon className="h-5 w-5 text-red-500" />;
      case UploadStatus.UPLOADING:
      case UploadStatus.PROCESSING:
        return <ArrowPathIcon className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return null;
    }
  };

  // Render parse results for active file
  const renderParseResults = () => {
    if (!activeFile || !parseResults[activeFile]) return null;
    
    const result = parseResults[activeFile];
    
    if (result.error) {
      return (
        <div className="mt-6 bg-red-50 p-4 rounded-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <ExclamationCircleIcon className="h-5 w-5 text-red-400" aria-hidden="true" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error processing file</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{result.error}</p>
              </div>
            </div>
          </div>
        </div>
      );
    }
    
    if (uploadStatus[activeFile] === UploadStatus.PROCESSING) {
      return (
        <div className="mt-6 bg-blue-50 p-4 rounded-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <ArrowPathIcon className="h-5 w-5 text-blue-400 animate-spin" aria-hidden="true" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Processing file</h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>Please wait while we analyze your file...</p>
              </div>
            </div>
          </div>
        </div>
      );
    }
    
    if (result.columns && result.columns.length > 0) {
      return (
        <div className="mt-6">
          <h3 className="text-lg font-medium text-gray-900">Column Mapping</h3>
          <p className="mt-1 text-sm text-gray-500">
            Map columns from your file to property fields. We've made some smart guesses for you.
          </p>
          
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    File Column
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Property Field
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sample Data
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {result.columns.map((column, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {column.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <select
                        className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
                        value={columnMappings[activeFile]?.[column.name] || ''}
                        onChange={(e) => updateColumnMapping(activeFile, column.name, e.target.value)}
                      >
                        <option value="">-- Select Field --</option>
                        <option value="unit_no">Unit Number</option>
                        <option value="tower">Tower/Phase</option>
                        <option value="floor">Floor</option>
                        <option value="unit_type">Unit Type</option>
                        <option value="bedrooms">Bedrooms</option>
                        <option value="bathrooms">Bathrooms</option>
                        <option value="size_ft2">Size (ft²)</option>
                        <option value="price">Price (AED)</option>
                        <option value="view">View</option>
                        <option value="status">Status</option>
                        <option value="completion_date">Completion Date</option>
                        <option value="payment_plan">Payment Plan</option>
                        <option value="description">Description</option>
                        <option value="features">Features</option>
                        <option value="latitude">Latitude</option>
                        <option value="longitude">Longitude</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {column.sampleData}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => saveColumnMappings(activeFile)}
              disabled={isProcessing}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              {isProcessing ? (
                <>
                  <ArrowPathIcon className="animate-spin -ml-1 mr-2 h-4 w-4" />
                  Processing...
                </>
              ) : (
                'Save Mappings'
              )}
            </button>
          </div>
          
          {parseResults[activeFile]?.finalResults && (
            <div className="mt-6 bg-green-50 p-4 rounded-md">
              <div className="flex">
                <div className="flex-shrink-0">
                  <CheckCircleIcon className="h-5 w-5 text-green-400" aria-hidden="true" />
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-green-800">Processing complete</h3>
                  <div className="mt-2 text-sm text-green-700">
                    <p>Successfully processed {parseResults[activeFile].finalResults.processedCount} properties.</p>
                    {parseResults[activeFile].finalResults.errorCount > 0 && (
                      <p className="mt-1">
                        {parseResults[activeFile].finalResults.errorCount} errors encountered.{' '}
                        <a href={parseResults[activeFile].finalResults.errorReportUrl} className="font-medium underline">
                          Download error report
                        </a>
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }
    
    return null;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="md:flex md:items-center md:justify-between">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:truncate">
            Data Upload
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Upload property data files to be processed and added to your inventory.
          </p>
        </div>
      </div>
      
      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900">Upload Files</h3>
            <p className="mt-1 text-sm text-gray-500">
              Drag and drop files or click to browse. Supported formats: PDF, Excel, CSV, IFC, GLB.
            </p>
            
            <div
              {...getRootProps()}
              className={`mt-4 border-2 border-dashed rounded-md px-6 pt-5 pb-6 flex justify-center ${
                isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'
              }`}
            >
              <div className="space-y-1 text-center">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                  aria-hidden="true"
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <div className="flex text-sm text-gray-600">
                  <label
                    htmlFor="file-upload"
                    className="relative cursor-pointer bg-white rounded-md font-medium text-primary-600 hover:text-primary-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-primary-500"
                  >
                    <span>Upload files</span>
                    <input {...getInputProps()} id="file-upload" className="sr-only" />
                  </label>
                  <p className="pl-1">or drag and drop</p>
                </div>
                <p className="text-xs text-gray-500">
                  PDF (max 100MB), Excel/CSV, IFC/GLB (max 150MB)
                </p>
              </div>
            </div>
            
            {files.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-900">Files</h4>
                <ul className="mt-3 divide-y divide-gray-200">
                  {files.map((file) => (
                    <li key={file.name} className="py-3 flex items-center justify-between">
                      <div className="flex items-center">
                        {renderFileIcon(file)}
                        <div className="ml-3">
                          <p className="text-sm font-medium text-gray-900">{file.name}</p>
                          <p className="text-xs text-gray-500">
                            {(file.size / (1024 * 1024)).toFixed(2)} MB
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center">
                        {renderStatusIcon(uploadStatus[file.name])}
                        
                        <div className="ml-4 flex-shrink-0 flex">
                          {uploadStatus[file.name] === UploadStatus.FAILED && (
                            <button
                              type="button"
                              onClick={() => retryUpload(file.name)}
                              className="mr-2 bg-white rounded-md font-medium text-primary-600 hover:text-primary-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                            >
                              Retry
                            </button>
                          )}
                          
                          <button
                            type="button"
                            onClick={() => removeFile(file.name)}
                            className="bg-white rounded-md font-medium text-red-600 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          
          {files.length > 0 && (
            <div className="mt-6 bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900">Upload Progress</h3>
              <div className="mt-4 space-y-4">
                {files.map((file) => (
                  <div key={`progress-${file.name}`}>
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-gray-900">{file.name}</div>
                      <div className="text-sm font-medium text-gray-900">{uploadProgress[file.name]}%</div>
                    </div>
                    <div className="mt-1 relative pt-1">
                      <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
                        <div
                          style={{ width: `${uploadProgress[file.name]}%` }}
                          className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center ${
                            uploadStatus[file.name] === UploadStatus.FAILED
                              ? 'bg-red-500'
                              : uploadStatus[file.name] === UploadStatus.COMPLETED
                              ? 'bg-green-500'
                              : 'bg-primary-500'
                          }`}
                        ></div>
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      {uploadStatus[file.name] === UploadStatus.UPLOADING && 'Uploading...'}
                      {uploadStatus[file.name] === UploadStatus.PROCESSING && 'Processing...'}
                      {uploadStatus[file.name] === UploadStatus.COMPLETED && 'Completed'}
                      {uploadStatus[file.name] === UploadStatus.FAILED && 'Failed'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className="lg:col-span-2">
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900">File Processing</h3>
            
            {files.length > 0 ? (
              <div>
                <div className="mt-4">
                  <label htmlFor="active-file" className="block text-sm font-medium text-gray-700">
                    Select File to Process
                  </label>
                  <select
                    id="active-file"
                    name="active-file"
                    className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm rounded-md"
                    value={activeFile || ''}
                    onChange={(e) => setActiveFile(e.target.value)}
                  >
                    <option value="">-- Select File --</option>
                    {files.map((file) => (
                      <option key={file.name} value={file.name} disabled={uploadStatus[file.name] !== UploadStatus.COMPLETED}>
                        {file.name} {uploadStatus[file.name] !== UploadStatus.COMPLETED ? '(Processing...)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
                
                {renderParseResults()}
              </div>
            ) : (
              <div className="mt-4 text-center py-12">
                <PhotoIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">No files uploaded</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Upload files to start processing your property data.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default withAuth(DataUploadService, 'developer_admin');
