import React from 'react';
import TestRepositoryCard from './TestRepositoryCard';

const TestRepositoryList = ({ testRepositories, onDelete, onAnalyze, onViewResults, onRefresh }) => {
  if (testRepositories.length === 0) {
    return (
      <div style={{
        padding: '60px 20px',
        textAlign: 'center',
        backgroundColor: '#fafafa',
        borderRadius: '8px',
        border: '1px dashed #ddd'
      }}>
        <p style={{ fontSize: '16px', color: '#666', marginBottom: '8px' }}>
          No test repositories uploaded yet
        </p>
        <p style={{ fontSize: '14px', color: '#999' }}>
          Upload a ZIP file to get started
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <p style={{ color: '#666', fontSize: '14px' }}>
          {testRepositories.length} test repository{testRepositories.length !== 1 ? 'ies' : ''}
        </p>
        <button
          onClick={onRefresh}
          style={{
            padding: '8px 16px',
            backgroundColor: '#f5f5f5',
            border: '1px solid #ddd',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '20px' }}>
        {testRepositories.map((repo) => (
          <TestRepositoryCard
            key={repo.id}
            testRepository={repo}
            onDelete={onDelete}
            onAnalyze={onAnalyze}
            onViewResults={onViewResults}
          />
        ))}
      </div>
    </div>
  );
};

export default TestRepositoryList;
