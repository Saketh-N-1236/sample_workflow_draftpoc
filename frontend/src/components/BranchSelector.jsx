import React, { useState, useEffect } from 'react';
import '../styles/App.css';
import api from '../services/api';

const BranchSelector = ({ repoId, selectedBranch, defaultBranch, onBranchChange }) => {
  const [branches, setBranches] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (repoId) {
      loadBranches();
    }
  }, [repoId]);

  const loadBranches = async () => {
    if (!repoId) return;
    
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.listBranches(repoId);
      const branchList = response.data.branches || [];
      setBranches(branchList);
    } catch (err) {
      console.error('Failed to load branches:', err);
      setError('Failed to load branches');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBranchChange = async (e) => {
    const newBranch = e.target.value;
    if (newBranch && newBranch !== selectedBranch) {
      try {
        await api.updateRepository(repoId, { selected_branch: newBranch });
        onBranchChange(newBranch);
      } catch (err) {
        console.error('Failed to update branch:', err);
        alert('Failed to update branch selection. Please try again.');
      }
    }
  };

  const currentBranch = selectedBranch || defaultBranch || '';

  return (
    <div className="branch-selector" style={{ marginBottom: '16px' }}>
      <label htmlFor="branch-select" className="input-label" style={{ 
        display: 'block', 
        marginBottom: '8px',
        fontSize: '14px',
        fontWeight: 500,
        color: '#1a1a1a'
      }}>
        Branch:
      </label>
      <div className="branch-selector-row">
        <select
          id="branch-select"
          className="branch-selector-select"
          value={currentBranch}
          onChange={handleBranchChange}
          disabled={isLoading || branches.length === 0}
          style={{
            cursor: isLoading ? 'not-allowed' : 'pointer',
          }}
        >
          {isLoading ? (
            <option>Loading branches...</option>
          ) : branches.length === 0 ? (
            <option>No branches available</option>
          ) : (
            branches.map(branch => (
              <option key={branch.name} value={branch.name}>
                {branch.name} {branch.default ? '(default)' : ''}
              </option>
            ))
          )}
        </select>
        <button
          type="button"
          className={`branch-selector-refresh${isLoading ? ' branch-selector-refresh--loading' : ''}`}
          onClick={loadBranches}
          disabled={isLoading}
          style={{
            cursor: isLoading ? 'not-allowed' : 'pointer',
          }}
          title="Refresh branches"
        >
          {isLoading
            ? <span className="branch-refresh-spinner" />
            : <span className="branch-refresh-icon">↻</span>
          }
        </button>
      </div>
      {error && (
        <div style={{ marginTop: '8px', fontSize: '12px', color: '#d32f2f' }}>
          {error}
        </div>
      )}
      {currentBranch && (
        <div style={{ marginTop: '4px', fontSize: '12px', color: '#666' }}>
          Using branch: <strong>{currentBranch}</strong>
        </div>
      )}
    </div>
  );
};

export default BranchSelector;
