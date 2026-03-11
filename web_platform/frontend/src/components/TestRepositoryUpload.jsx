import React, { useState, useRef } from 'react';
import api from '../services/api';

const TestRepositoryUpload = ({ onSuccess }) => {
  const [file, setFile] = useState(null);
  const [name, setName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.zip')) {
        setFile(droppedFile);
        if (!name) {
          setName(droppedFile.name.replace('.zip', ''));
        }
      } else {
        setError('Please upload a ZIP file');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.name.endsWith('.zip')) {
        setFile(selectedFile);
        if (!name) {
          setName(selectedFile.name.replace('.zip', ''));
        }
        setError(null);
      } else {
        setError('Please select a ZIP file');
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!file) {
      setError('Please select a ZIP file');
      return;
    }

    if (!name.trim()) {
      setError('Please enter a name for the test repository');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setSuccess(null);

      const response = await api.uploadTestRepository(file, name.trim());
      
      setSuccess(`Test repository "${response.data.name}" uploaded successfully!`);
      setFile(null);
      setName('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Call success callback after a short delay
      setTimeout(() => {
        if (onSuccess) {
          onSuccess();
        }
      }, 1500);
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to upload test repository');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px' }}>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>
            Test Repository Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter a name for this test repository"
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
            disabled={uploading}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>
            ZIP File
          </label>
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${dragActive ? '#1976d2' : '#ddd'}`,
              borderRadius: '8px',
              padding: '40px',
              textAlign: 'center',
              backgroundColor: dragActive ? '#f0f7ff' : '#fafafa',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              disabled={uploading}
            />
            {file ? (
              <div>
                <p style={{ margin: '0 0 8px 0', fontWeight: '600', color: '#1976d2' }}>
                  {file.name}
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: '#666' }}>
                  Click to select a different file
                </p>
              </div>
            ) : (
              <div>
                <p style={{ margin: '0 0 8px 0', fontSize: '16px' }}>
                  Drag and drop a ZIP file here
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: '#666' }}>
                  or click to browse
                </p>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div style={{
            padding: '12px',
            marginBottom: '20px',
            backgroundColor: '#fee',
            border: '1px solid #fcc',
            borderRadius: '4px',
            color: '#c33'
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            padding: '12px',
            marginBottom: '20px',
            backgroundColor: '#efe',
            border: '1px solid #cfc',
            borderRadius: '4px',
            color: '#3c3'
          }}>
            {success}
          </div>
        )}

        <button
          type="submit"
          disabled={uploading || !file || !name.trim()}
          style={{
            padding: '12px 24px',
            backgroundColor: uploading || !file || !name.trim() ? '#ccc' : '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: uploading || !file || !name.trim() ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '600'
          }}
        >
          {uploading ? 'Uploading...' : 'Upload Test Repository'}
        </button>
      </form>
    </div>
  );
};

export default TestRepositoryUpload;
