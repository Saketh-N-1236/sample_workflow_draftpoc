import React, { useState, useEffect } from 'react';
import api from '../services/api';

const TestRepositoryBinding = ({ repositoryId, onUpdate }) => {
  const [testRepositories, setTestRepositories] = useState([]);
  const [boundRepos, setBoundRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, [repositoryId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [allReposResponse, boundReposResponse] = await Promise.all([
        api.listTestRepositories(),
        api.getBoundTestRepositories(repositoryId)
      ]);
      
      setTestRepositories(allReposResponse.data || []);
      setBoundRepos(boundReposResponse.data || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load test repositories:', err);
      setError('Failed to load test repositories');
    } finally {
      setLoading(false);
    }
  };

  const handleBind = async (testRepoId, isPrimary = false) => {
    try {
      await api.bindTestRepository(repositoryId, testRepoId, isPrimary);
      await loadData();
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Failed to bind test repository:', err);
      alert(`Failed to bind test repository: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleUnbind = async (testRepoId) => {
    if (!window.confirm('Are you sure you want to unbind this test repository?')) {
      return;
    }

    try {
      await api.unbindTestRepository(repositoryId, testRepoId);
      await loadData();
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Failed to unbind test repository:', err);
      alert(`Failed to unbind test repository: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleSetPrimary = async (testRepoId) => {
    try {
      await api.setPrimaryTestRepository(repositoryId, testRepoId);
      await loadData();
      if (onUpdate) onUpdate();
    } catch (err) {
      console.error('Failed to set primary test repository:', err);
      alert(`Failed to set primary: ${err.response?.data?.detail || err.message}`);
    }
  };

  const boundRepoIds = new Set(boundRepos.map(r => r.id));
  const availableRepos = testRepositories.filter(r => !boundRepoIds.has(r.id));
  const primaryRepo = boundRepos.find(r => r.is_primary);

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>;
  }

  return (
    <div style={{ marginTop: '24px' }}>
      <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px' }}>
        Test Repository Bindings
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

      {/* Bound Repositories */}
      {boundRepos.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: '#666' }}>
            Bound Test Repositories ({boundRepos.length})
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {boundRepos.map((repo) => (
              <div
                key={repo.id}
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: repo.is_primary ? '#f0f7ff' : 'white',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: '600' }}>{repo.name}</span>
                    {repo.is_primary && (
                      <span style={{
                        padding: '2px 6px',
                        backgroundColor: '#1976d2',
                        color: 'white',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: '600'
                      }}>
                        PRIMARY
                      </span>
                    )}
                    <span style={{
                      padding: '2px 6px',
                      backgroundColor: repo.status === 'ready' ? '#2e7d32' : '#f57c00',
                      color: 'white',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: '600'
                    }}>
                      {repo.status?.toUpperCase() || 'PENDING'}
                    </span>
                  </div>
                  {repo.schema_name && (
                    <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                      Schema: {repo.schema_name}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {!repo.is_primary && (
                    <button
                      onClick={() => handleSetPrimary(repo.id)}
                      style={{
                        padding: '6px 12px',
                        backgroundColor: '#1976d2',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Set Primary
                    </button>
                  )}
                  <button
                    onClick={() => handleUnbind(repo.id)}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: '#c62828',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Unbind
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available Repositories */}
      {availableRepos.length > 0 && (
        <div>
          <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: '#666' }}>
            Available Test Repositories ({availableRepos.length})
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {availableRepos.map((repo) => (
              <div
                key={repo.id}
                style={{
                  padding: '12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: '600' }}>{repo.name}</span>
                  <span style={{
                    marginLeft: '8px',
                    padding: '2px 6px',
                    backgroundColor: repo.status === 'ready' ? '#2e7d32' : '#f57c00',
                    color: 'white',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: '600'
                  }}>
                    {repo.status?.toUpperCase() || 'PENDING'}
                  </span>
                </div>
                <button
                  onClick={() => handleBind(repo.id, boundRepos.length === 0)}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: '#1976d2',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  {boundRepos.length === 0 ? 'Bind as Primary' : 'Bind'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {availableRepos.length === 0 && boundRepos.length === 0 && (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#fafafa',
          borderRadius: '8px',
          border: '1px dashed #ddd'
        }}>
          <p style={{ color: '#666', marginBottom: '8px' }}>
            No test repositories available
          </p>
          <p style={{ fontSize: '12px', color: '#999' }}>
            Upload a test repository first to bind it to this repository
          </p>
        </div>
      )}
    </div>
  );
};

export default TestRepositoryBinding;
