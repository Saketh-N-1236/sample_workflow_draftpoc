import React from 'react';
import { useNavigate } from 'react-router-dom';

const TestRepositoryCard = ({ testRepository, onDelete, onAnalyze, onViewResults }) => {
  const navigate = useNavigate();
  const getStatusColor = (status) => {
    switch (status) {
      case 'ready':
        return '#2e7d32';
      case 'analyzing':
        return '#f57c00';
      case 'error':
        return '#c62828';
      default:
        return '#666';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'ready':
        return 'Ready';
      case 'analyzing':
        return 'Analyzing';
      case 'error':
        return 'Error';
      default:
        return 'Pending';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <div style={{
      border: '1px solid #ddd',
      borderRadius: '8px',
      padding: '20px',
      backgroundColor: 'white',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
            {testRepository.name}
          </h3>
          <span style={{
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: '600',
            color: 'white',
            backgroundColor: getStatusColor(testRepository.status)
          }}>
            {getStatusLabel(testRepository.status)}
          </span>
        </div>
        {testRepository.zip_filename && (
          <p style={{ margin: 0, fontSize: '12px', color: '#666' }}>
            {testRepository.zip_filename}
          </p>
        )}
      </div>

      <div style={{ marginBottom: '16px', fontSize: '12px', color: '#666' }}>
        <div style={{ marginBottom: '4px' }}>
          <strong>Hash:</strong> {testRepository.hash?.substring(0, 8)}...
        </div>
        {testRepository.schema_name && (
          <div style={{ marginBottom: '4px' }}>
            <strong>Schema:</strong> {testRepository.schema_name}
          </div>
        )}
        <div style={{ marginBottom: '4px' }}>
          <strong>Uploaded:</strong> {formatDate(testRepository.uploaded_at)}
        </div>
        {testRepository.last_analyzed_at && (
          <div>
            <strong>Last Analyzed:</strong> {formatDate(testRepository.last_analyzed_at)}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {testRepository.status === 'ready' && (
          <button
            onClick={() => {
              if (onViewResults) {
                onViewResults(testRepository.id);
              } else {
                navigate(`/test-repositories/${testRepository.id}/analysis`);
              }
            }}
            style={{
              padding: '6px 12px',
              backgroundColor: '#2e7d32',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            View Results
          </button>
        )}
        {testRepository.status !== 'ready' && (
          <button
            onClick={() => onAnalyze(testRepository.id)}
            style={{
              padding: '6px 12px',
              backgroundColor: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            Analyze
          </button>
        )}
        <button
          onClick={() => onDelete(testRepository.id)}
          style={{
            padding: '6px 12px',
            backgroundColor: '#c62828',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: '600'
          }}
        >
          Delete
        </button>
      </div>
    </div>
  );
};

export default TestRepositoryCard;
