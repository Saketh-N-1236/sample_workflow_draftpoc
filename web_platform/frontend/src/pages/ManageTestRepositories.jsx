import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import TestRepositoryUpload from '../components/TestRepositoryUpload';
import TestRepositoryList from '../components/TestRepositoryList';
import '../styles/App.css';

const ManageTestRepositories = () => {
  const navigate = useNavigate();
  const [testRepositories, setTestRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('list'); // 'list' or 'upload'

  useEffect(() => {
    loadTestRepositories();
  }, []);

  const loadTestRepositories = async () => {
    try {
      setLoading(true);
      const response = await api.listTestRepositories();
      setTestRepositories(response.data || []);
      setError(null);
    } catch (err) {
      console.error('Failed to load test repositories:', err);
      setError('Failed to load test repositories. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadSuccess = () => {
    loadTestRepositories();
    setActiveTab('list');
  };

  const handleDelete = async (testRepoId) => {
    if (!window.confirm('Are you sure you want to delete this test repository? This will also delete its schema and all data.')) {
      return;
    }

    try {
      await api.deleteTestRepository(testRepoId);
      await loadTestRepositories();
    } catch (err) {
      console.error('Failed to delete test repository:', err);
      alert('Failed to delete test repository. Please try again.');
    }
  };

  const handleAnalyze = async (testRepoId) => {
    try {
      // Start analysis
      const response = await api.analyzeTestRepository(testRepoId);
      
      // Show success message and redirect to analysis page
      alert(`Analysis started: ${response.data.message || 'Analysis in progress'}`);
      
      // Navigate to analysis page after a short delay
      setTimeout(() => {
        navigate(`/test-repositories/${testRepoId}/analysis`);
      }, 1000);
      
      await loadTestRepositories();
    } catch (err) {
      console.error('Failed to analyze test repository:', err);
      alert(`Failed to analyze test repository: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleViewResults = (testRepoId) => {
    navigate(`/test-repositories/${testRepoId}/analysis`);
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <p>Loading test repositories...</p>
      </div>
    );
  }

  return (
    <div className="manage-test-repositories-page" style={{ padding: '20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '600', marginBottom: '8px' }}>
          Manage Test Repositories
        </h1>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Upload, manage, and bind test repositories to code repositories
        </p>
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

      {/* Tabs */}
      <div style={{ marginBottom: '24px', borderBottom: '1px solid #ddd' }}>
        <button
          onClick={() => setActiveTab('list')}
          style={{
            padding: '10px 20px',
            marginRight: '8px',
            border: 'none',
            borderBottom: activeTab === 'list' ? '2px solid #1976d2' : '2px solid transparent',
            background: 'none',
            cursor: 'pointer',
            color: activeTab === 'list' ? '#1976d2' : '#666',
            fontWeight: activeTab === 'list' ? '600' : '400'
          }}
        >
          Test Repositories ({testRepositories.length})
        </button>
        <button
          onClick={() => setActiveTab('upload')}
          style={{
            padding: '10px 20px',
            border: 'none',
            borderBottom: activeTab === 'upload' ? '2px solid #1976d2' : '2px solid transparent',
            background: 'none',
            cursor: 'pointer',
            color: activeTab === 'upload' ? '#1976d2' : '#666',
            fontWeight: activeTab === 'upload' ? '600' : '400'
          }}
        >
          Upload New
        </button>
      </div>

      {/* Content */}
      {activeTab === 'list' ? (
        <TestRepositoryList
          testRepositories={testRepositories}
          onDelete={handleDelete}
          onAnalyze={handleAnalyze}
          onViewResults={handleViewResults}
          onRefresh={loadTestRepositories}
        />
      ) : (
        <TestRepositoryUpload onSuccess={handleUploadSuccess} />
      )}
    </div>
  );
};

export default ManageTestRepositories;
