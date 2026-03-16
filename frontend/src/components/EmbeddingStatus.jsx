import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/App.css';

const EmbeddingStatus = ({ testRepoId = null, onRegenerate }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStatus();
  }, [testRepoId]);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const response = await api.getEmbeddingStatus(testRepoId);
      setStatus(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch embedding status:', err);
      setError('Failed to load embedding status');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (health) => {
    switch (health) {
      case 'healthy':
        return '#4caf50';
      case 'unhealthy':
        return '#f44336';
      case 'empty':
        return '#ff9800';
      default:
        return '#9e9e9e';
    }
  };

  const getHealthLabel = (health) => {
    switch (health) {
      case 'healthy':
        return 'Healthy';
      case 'unhealthy':
        return 'Unhealthy';
      case 'empty':
        return 'Empty';
      default:
        return 'Unknown';
    }
  };

  if (loading) {
    return (
      <div style={{ 
        padding: '16px', 
        background: 'white', 
        borderRadius: '8px', 
        border: '1px solid #e0e0e0',
        marginBottom: '20px'
      }}>
        <p>Loading embedding status...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ 
        padding: '16px', 
        background: '#ffebee', 
        borderRadius: '8px', 
        border: '1px solid #f44336',
        marginBottom: '20px'
      }}>
        <p style={{ color: '#f44336', margin: 0 }}>{error}</p>
        <button 
          onClick={fetchStatus}
          style={{
            marginTop: '8px',
            padding: '6px 12px',
            background: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!status) {
    return null;
  }

  return (
    <div style={{ 
      padding: '16px', 
      background: 'white', 
      borderRadius: '8px', 
      border: '1px solid #e0e0e0',
      marginBottom: '20px'
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '12px'
      }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>
          Embedding Status
        </h3>
        <button
          onClick={fetchStatus}
          style={{
            padding: '4px 8px',
            background: 'transparent',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px'
          }}
        >
          Refresh
        </button>
      </div>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '12px',
        marginBottom: '12px'
      }}>
        <div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            {status.test_repo_id ? 'Embeddings (This Repository)' : 'Total Embeddings'}
          </div>
          <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1976d2' }}>
            {status.total_embeddings || 0}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            Index Health
          </div>
          <div style={{ 
            fontSize: '14px', 
            fontWeight: '600',
            color: getHealthColor(status.index_health)
          }}>
            {getHealthLabel(status.index_health)}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            Backend
          </div>
          <div style={{ fontSize: '14px', fontWeight: '500' }}>
            {status.backend || 'unknown'}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
            Dimensions
          </div>
          <div style={{ fontSize: '14px', fontWeight: '500' }}>
            {status.embedding_dimensions || 768}
          </div>
        </div>
      </div>

      {status.last_generated && (
        <div style={{ 
          fontSize: '12px', 
          color: '#666', 
          marginBottom: '12px',
          paddingTop: '12px',
          borderTop: '1px solid #e0e0e0'
        }}>
          Last Generated: {new Date(status.last_generated).toLocaleString()}
        </div>
      )}

      {onRegenerate && (
        <button
          onClick={onRegenerate}
          style={{
            width: '100%',
            padding: '8px 16px',
            background: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500'
          }}
        >
          Regenerate Embeddings
        </button>
      )}

      {status.error && (
        <div style={{ 
          marginTop: '12px',
          padding: '8px',
          background: '#ffebee',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#f44336'
        }}>
          Error: {status.error}
        </div>
      )}
    </div>
  );
};

export default EmbeddingStatus;
