import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RepositoryConnector from '../components/RepositoryConnector';
import '../styles/App.css';
import api from '../services/api';

const AddRepository = () => {
  const navigate = useNavigate();
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async (connectData) => {
    setIsConnecting(true);
    try {
      const requestData = typeof connectData === 'string' 
        ? { url: connectData }
        : connectData;
      
      const response = await api.connectRepository(requestData);
      const repo = response.data;
      
      // Navigate to repository detail page
      navigate(`/repositories/${repo.id}`);
    } catch (error) {
      console.error('Failed to connect repository:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to connect repository. Please check the URL and try again.';
      alert(errorMsg);
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="add-repository-page">
      <div className="page-header">
        <h1 className="page-title">Add Repository</h1>
        <button
          className="button button-secondary"
          onClick={() => navigate('/repositories')}
        >
          View All Repositories
        </button>
      </div>

      <div className="page-content">
        <div className="card">
          <div className="card-header">
            <h2>Connect a Git Repository</h2>
            <p className="card-description">
              Connect a GitHub or GitLab repository to analyze code changes and select relevant tests.
            </p>
          </div>
          <div className="card-body">
            <RepositoryConnector onConnect={handleConnect} />
            {isConnecting && (
              <div style={{ marginTop: '20px', textAlign: 'center', color: '#666' }}>
                Connecting repository...
              </div>
            )}
          </div>
        </div>

        <div className="info-section" style={{ marginTop: '40px' }}>
          <h3>How it works:</h3>
          <ul className="info-list">
            <li>Enter your repository URL (GitHub or GitLab)</li>
            <li>System will validate access and fetch repository information</li>
            <li>Select a branch to analyze</li>
            <li>View git diff and run test analysis/selection</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default AddRepository;
