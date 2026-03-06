import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/App.css';

const SemanticConfigPanel = ({ repoId, onSave, onCancel }) => {
  const [config, setConfig] = useState({
    similarity_threshold: null,
    max_results: 10000,  // High limit to effectively remove upper bound
    use_adaptive_thresholds: true,
    use_multi_query: false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleThresholdChange = (e) => {
    const value = e.target.value;
    setConfig({
      ...config,
      similarity_threshold: value === '' ? null : parseFloat(value)
    });
  };

  const handleMaxResultsChange = (e) => {
    setConfig({
      ...config,
      max_results: parseInt(e.target.value) || 20
    });
  };

  const handleToggle = (field) => {
    setConfig({
      ...config,
      [field]: !config[field]
    });
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      // Validate
      if (config.similarity_threshold !== null) {
        if (config.similarity_threshold < 0 || config.similarity_threshold > 1) {
          setError('Similarity threshold must be between 0.0 and 1.0');
          setLoading(false);
          return;
        }
      }

      if (config.max_results < 1) {
        setError('Max results must be at least 1');
        setLoading(false);
        return;
      }

      if (repoId) {
        await api.configureSemanticSearch(repoId, config);
      }

      setSuccess(true);
      setTimeout(() => {
        if (onSave) {
          onSave(config);
        }
      }, 1000);
    } catch (err) {
      console.error('Failed to save semantic config:', err);
      setError(err.response?.data?.detail || 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setConfig({
      similarity_threshold: null,
      max_results: 20,
      use_adaptive_thresholds: true,
      use_multi_query: false
    });
    setError(null);
    setSuccess(false);
  };

  return (
    <div style={{ 
      padding: '20px', 
      background: 'white', 
      borderRadius: '8px', 
      border: '1px solid #e0e0e0'
    }}>
      <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', fontWeight: '600' }}>
        Semantic Search Configuration
      </h3>

      {error && (
        <div style={{ 
          padding: '12px', 
          background: '#ffebee', 
          borderRadius: '4px',
          marginBottom: '16px',
          color: '#f44336',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{ 
          padding: '12px', 
          background: '#e8f5e9', 
          borderRadius: '4px',
          marginBottom: '16px',
          color: '#2e7d32',
          fontSize: '14px'
        }}>
          Configuration saved successfully!
        </div>
      )}

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontSize: '14px', 
          fontWeight: '500' 
        }}>
          Similarity Threshold
          <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
            (0.3 - 0.7, leave empty for adaptive)
          </span>
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.1"
          value={config.similarity_threshold === null ? '' : config.similarity_threshold}
          onChange={handleThresholdChange}
          placeholder="Auto (adaptive thresholds)"
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
          {config.similarity_threshold === null 
            ? 'Using adaptive thresholds (strict → moderate → lenient)'
            : `Fixed threshold: ${config.similarity_threshold}`
          }
        </div>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontSize: '14px', 
          fontWeight: '500' 
        }}>
          Max Results
        </label>
        <input
          type="number"
          min="1"
          value={config.max_results}
          onChange={handleMaxResultsChange}
          placeholder="10000 (no limit)"
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
          Set to 10000 or higher to effectively remove limits
        </div>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'flex', 
          alignItems: 'center', 
          cursor: 'pointer',
          fontSize: '14px'
        }}>
          <input
            type="checkbox"
            checked={config.use_adaptive_thresholds}
            onChange={() => handleToggle('use_adaptive_thresholds')}
            style={{ marginRight: '8px' }}
          />
          Use Adaptive Thresholds
          <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
            (Try multiple thresholds for better coverage)
          </span>
        </label>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'flex', 
          alignItems: 'center', 
          cursor: 'pointer',
          fontSize: '14px'
        }}>
          <input
            type="checkbox"
            checked={config.use_multi_query}
            onChange={() => handleToggle('use_multi_query')}
            style={{ marginRight: '8px' }}
          />
          Use Multi-Query Search
          <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
            (Generate multiple query variations)
          </span>
        </label>
      </div>

      <div style={{ 
        display: 'flex', 
        gap: '12px', 
        justifyContent: 'flex-end',
        paddingTop: '16px',
        borderTop: '1px solid #e0e0e0'
      }}>
        <button
          onClick={handleReset}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: 'transparent',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px'
          }}
        >
          Reset
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={loading}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px'
            }}
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleSave}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: loading ? '#ccc' : '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500'
          }}
        >
          {loading ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
};

export default SemanticConfigPanel;
