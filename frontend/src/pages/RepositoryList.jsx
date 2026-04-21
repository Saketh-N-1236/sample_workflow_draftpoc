import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/App.css';
import api from '../services/api';

const RepositoryList = () => {
  const navigate = useNavigate();
  const [repositories, setRepositories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadRepositories();
  }, []);

  const loadRepositories = async () => {
    setIsLoading(true);
    try {
      const response = await api.listRepositories();
      setRepositories(response.data || []);
    } catch (error) {
      console.error('Failed to load repositories:', error);
      alert('Failed to load repositories. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async (repoId, event) => {
    event.stopPropagation();
    try {
      await api.refreshRepository(repoId);
      await loadRepositories();
      alert('Repository refreshed successfully!');
    } catch (error) {
      console.error('Failed to refresh repository:', error);
      alert('Failed to refresh repository. Please try again.');
    }
  };

  const handleDelete = async (repoId, event) => {
    event.stopPropagation();
    if (!window.confirm('Delete this repository? This cannot be undone.')) return;
    try {
      await api.deleteRepository(repoId);
      setRepositories(prev => prev.filter(r => r.id !== repoId));
    } catch (error) {
      console.error('Failed to delete repository:', error);
      alert(error.response?.data?.detail || 'Failed to delete repository.');
    }
  };

  const filteredRepositories = repositories.filter(repo => {
    const query = searchQuery.toLowerCase();
    return (
      repo.url.toLowerCase().includes(query) ||
      (repo.provider && repo.provider.toLowerCase().includes(query))
    );
  });

  return (
    <div className="repository-list-page">
      <div className="page-header">
        <h1 className="page-title">Repositories</h1>
        <button
          className="button button-primary"
          onClick={() => navigate('/')}
        >
          Add Repository
        </button>
      </div>

      <div className="search-bar" style={{ marginBottom: '20px' }}>
        <input
          type="text"
          className="search-input"
          placeholder="Search repositories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#999' }}>
          Loading repositories...
        </div>
      ) : filteredRepositories.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <p style={{ color: '#999', marginBottom: '20px' }}>
            {searchQuery ? 'No repositories found matching your search.' : 'No repositories connected yet.'}
          </p>
          <button
            className="button button-primary"
            onClick={() => navigate('/')}
          >
            Add Your First Repository
          </button>
        </div>
      ) : (
        <div className="repositories-grid">
          {filteredRepositories.map(repo => (
            <div
              key={repo.id}
              className="repository-card"
              onClick={() => navigate(`/repositories/${repo.id}`)}
            >
              <div className="repository-card-header">
                <div className="repository-card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="repository-name">{repo.url.split('/').pop()}</span>
                  {repo.has_token ? (
                    <span style={{ fontSize: '11px', background: '#c6f6d5', color: '#276749', borderRadius: '4px', padding: '2px 7px', fontWeight: 600 }}>
                      Token ✓
                    </span>
                  ) : (
                    <span style={{ fontSize: '11px', background: '#fff3cd', color: '#856404', borderRadius: '4px', padding: '2px 7px', fontWeight: 600 }}>
                      Env token
                    </span>
                  )}
                </div>
              </div>
              <div className="repository-card-body">
                <div className="repository-info">
                  <div className="info-item">
                    <span className="info-label">Provider:</span>
                    <span className="info-value">{repo.provider || 'Unknown'}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Branch:</span>
                    <span className="info-value">{repo.selected_branch || repo.default_branch || 'N/A'}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">URL:</span>
                    <span className="info-value" style={{ fontSize: '12px', color: '#666' }}>
                      {repo.url}
                    </span>
                  </div>
                  {repo.createdAt && (
                    <div className="info-item">
                      <span className="info-label">Connected:</span>
                      <span className="info-value">
                        {new Date(repo.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
              <div className="repository-card-footer" style={{ display: 'flex', gap: '8px', justifyContent: 'space-between' }}>
                <button
                  className="button button-secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/repositories/${repo.id}`);
                  }}
                >
                  View Details →
                </button>
                <button
                  className="button"
                  onClick={(e) => handleDelete(repo.id, e)}
                  style={{
                    background: 'transparent',
                    border: '1px solid #e53e3e',
                    color: '#e53e3e',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '13px',
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default RepositoryList;
