import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/App.css';

const RiskAnalysisPanel = ({ repoId, onSave, onCancel }) => {
  const [threshold, setThreshold] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // Load current threshold only once when component mounts or repoId changes
    if (repoId) {
      loadThreshold();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId]); // Only depend on repoId, not on threshold changes

  const loadThreshold = async () => {
    try {
      const response = await api.getRiskThreshold(repoId);
      const currentThreshold = response.data.risk_threshold ?? null; // null means disabled
      setThreshold(currentThreshold);
    } catch (error) {
      console.error('Failed to load risk threshold:', error);
      // Use null if load fails (disabled by default)
      setThreshold(null);
    }
  };

  const handleThresholdChange = (e) => {
    const value = e.target.value;
    // Allow empty string - don't set any default value
    if (value === '' || value.trim() === '') {
      setThreshold(null); // Clear threshold (disable risk analysis)
      return;
    }
    
    // Try to parse as integer
    const numValue = parseInt(value);
    if (!isNaN(numValue) && numValue >= 1) {
      setThreshold(numValue);
    } else {
      // Invalid input - keep as null (don't force default)
      setThreshold(null);
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      // Validate threshold - allow null (disables risk analysis) or positive integer
      if (threshold !== null && threshold < 1) {
        setError('Risk threshold must be at least 1, or leave empty to disable risk analysis');
        setLoading(false);
        return;
      }

      await api.updateRiskThreshold(repoId, threshold);

      setSuccess(true);
      // Don't reload threshold immediately - wait for parent to reload repository
      setTimeout(() => {
        if (onSave) {
          onSave(threshold);
        }
      }, 1000);
    } catch (err) {
      console.error('Failed to save risk threshold:', err);
      setError(err.response?.data?.detail || 'Failed to save risk threshold');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      padding: '20px',
      backgroundColor: '#f9f9f9',
      marginTop: '16px'
    }}>
      <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '16px', fontWeight: '600' }}>
        Risk Analysis Configuration
      </h3>

      {error && (
        <div style={{
          padding: '12px',
          marginBottom: '16px',
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
          marginBottom: '16px',
          backgroundColor: '#efe',
          border: '1px solid #cfc',
          borderRadius: '4px',
          color: '#3c3'
        }}>
          Risk threshold updated successfully!
        </div>
      )}

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontSize: '14px', 
          fontWeight: '500' 
        }}>
          Risk Threshold (Number of Changed Files)
          <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
            (If changed files exceed this value, all tests will be executed)
          </span>
        </label>
        <input
          type="text"
          inputMode="numeric"
          value={threshold === null ? '' : threshold}
          onChange={handleThresholdChange}
          placeholder="Leave empty to disable risk analysis"
          onKeyDown={(e) => {
            // Allow: backspace, delete, tab, escape, enter, and numbers
            if ([8, 9, 27, 13, 46].indexOf(e.keyCode) !== -1 ||
                // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
                (e.keyCode === 65 && e.ctrlKey === true) ||
                (e.keyCode === 67 && e.ctrlKey === true) ||
                (e.keyCode === 86 && e.ctrlKey === true) ||
                (e.keyCode === 88 && e.ctrlKey === true) ||
                // Allow: home, end, left, right
                (e.keyCode >= 35 && e.keyCode <= 39)) {
              return;
            }
            // Ensure that it is a number and stop the keypress
            if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
              e.preventDefault();
            }
          }}
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
          {threshold === null ? (
            <>Risk analysis is <strong>disabled</strong>. Test selection will always run normally, regardless of the number of changed files.</>
          ) : (
            <>Current threshold: {threshold} files. When {threshold + 1} or more files are changed, test selection will be disabled and all tests will run.</>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={loading}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              color: '#666',
              border: '1px solid #ccc',
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
          {loading ? 'Saving...' : 'Save Threshold'}
        </button>
      </div>
    </div>
  );
};

export default RiskAnalysisPanel;
