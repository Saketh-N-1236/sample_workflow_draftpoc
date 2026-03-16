import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import BranchSelector from '../components/BranchSelector';
import DiffViewer from '../components/DiffViewer';
import DiffStats from '../components/DiffStats';
import DiffModal from '../components/DiffModal';
import ActionButtons from '../components/ActionButtons';
import ResultsDisplay from '../components/ResultsDisplay';
import EmbeddingStatus from '../components/EmbeddingStatus';
import TestSummaryModal from '../components/TestSummaryModal';
import RiskAnalysisPanel from '../components/RiskAnalysisPanel';
import TestRepositoryBinding from '../components/TestRepositoryBinding';
import '../styles/App.css';
import api from '../services/api';

const RepositoryDetail = () => {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const [repository, setRepository] = useState(null);
  const [diffContent, setDiffContent] = useState('');
  const [changedFiles, setChangedFiles] = useState([]);
  const [isSelectionRunning, setIsSelectionRunning] = useState(false);
  const [selectionResults, setSelectionResults] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('diff'); // 'diff', 'selection'
  const [diffStats, setDiffStats] = useState(null);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);
  const [showTestSummary, setShowTestSummary] = useState(false);
  const [showRiskAnalysis, setShowRiskAnalysis] = useState(false);
  const [totalTestsInDb, setTotalTestsInDb] = useState(0);
  const [selectionDisabled, setSelectionDisabled] = useState(false);
  const [primaryTestRepoId, setPrimaryTestRepoId] = useState(null);

  useEffect(() => {
    if (repoId) {
      loadRepository();
      loadBoundTestRepositories();
    }
    // Load total tests count
    loadTotalTestsCount();
  }, [repoId]);

  const loadTotalTestsCount = async () => {
    try {
      const response = await api.getTotalTestsCount();
      setTotalTestsInDb(response.data.total_tests || 0);
    } catch (error) {
      console.error('Failed to load total tests count:', error);
    }
  };

  const loadBoundTestRepositories = async () => {
    try {
      const response = await api.getBoundTestRepositories(repoId);
      const boundRepos = response.data || [];
      
      // Find primary test repository, or use first one if no primary
      const primaryRepo = boundRepos.find(repo => repo.is_primary) || boundRepos[0];
      if (primaryRepo) {
        setPrimaryTestRepoId(primaryRepo.id);
      } else {
        setPrimaryTestRepoId(null);
      }
    } catch (error) {
      console.error('Failed to load bound test repositories:', error);
      setPrimaryTestRepoId(null);
    }
  };

  const loadRepository = async () => {
    setIsLoading(true);
    try {
      const response = await api.getRepository(repoId);
      setRepository(response.data);
      await fetchDiff(repoId);
    } catch (error) {
      console.error('Failed to load repository:', error);
      alert('Repository not found. Redirecting to repositories list...');
      navigate('/repositories');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDiff = async (repoId) => {
    try {
      const response = await api.getDiff(repoId);
      setDiffContent(response.data.diff || '');
      setChangedFiles(response.data.changedFiles || []);
      setDiffStats(response.data.stats || null);
    } catch (error) {
      console.error('Failed to fetch diff:', error);
      setDiffContent('');
      setChangedFiles([]);
      setDiffStats(null);
    }
  };

  const handleRefresh = async () => {
    try {
      await api.refreshRepository(repoId);
      await loadRepository();
      alert('Repository refreshed successfully!');
    } catch (error) {
      console.error('Failed to refresh repository:', error);
      alert('Failed to refresh repository. Please try again.');
    }
  };

  const handleBranchChange = async (newBranch) => {
    if (!repository) return;
    
    try {
      const updatedRepo = { ...repository, selected_branch: newBranch };
      setRepository(updatedRepo);
      await fetchDiff(repoId);
    } catch (error) {
      console.error('Failed to handle branch change:', error);
    }
  };

  const handleTestSelection = async () => {
    if (!repository) {
      alert('Repository not loaded.');
      return;
    }

    setIsSelectionRunning(true);
    setSelectionResults(null);
    setActiveTab('selection');

    try {
      const response = await api.selectTests(repository.id);
      setSelectionResults(response.data);
      // Check if selection is disabled due to threshold
      if (response.data.selectionDisabled) {
        setSelectionDisabled(true);
      } else {
        setSelectionDisabled(false);
      }
    } catch (error) {
      console.error('Test selection failed:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Test selection failed. Please check the console for details.';
      alert(errorMsg);
    } finally {
      setIsSelectionRunning(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <p>Loading repository...</p>
      </div>
    );
  }

  if (!repository) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <p>Repository not found.</p>
        <button className="button button-primary" onClick={() => navigate('/repositories')}>
          Back to Repositories
        </button>
      </div>
    );
  }

  return (
    <div className="repository-detail-page">
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <button
            className="button button-secondary"
            onClick={() => navigate('/repositories')}
            style={{ marginRight: '12px' }}
          >
            ← Back
          </button>
          <h1 className="page-title">{repository.url.split('/').pop()}</h1>
        </div>
        <button
          className="button button-primary"
          onClick={handleRefresh}
        >
          ↻ Refresh
        </button>
      </div>

      <div className="repository-info-section" style={{ flexShrink: 0 }}>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Provider:</span>
            <span className="info-value">{repository.provider || 'Unknown'}</span>
          </div>
          <div className="info-item">
            <span className="info-label">URL:</span>
            <span className="info-value" style={{ fontSize: '14px' }}>{repository.url}</span>
          </div>
          {repository.createdAt && (
            <div className="info-item">
              <span className="info-label">Connected:</span>
              <span className="info-value">
                {new Date(repository.createdAt).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="branch-selector-section" style={{ flexShrink: 0 }}>
        <BranchSelector
          repoId={repository.id}
          selectedBranch={repository.selected_branch}
          defaultBranch={repository.default_branch}
          onBranchChange={handleBranchChange}
        />
      </div>

      {/* Embedding Status - Show before test selection */}
      <div style={{ marginBottom: '20px', flexShrink: 0 }}>
        <EmbeddingStatus testRepoId={primaryTestRepoId} />
      </div>

      <div className="actions-section" style={{ marginBottom: '20px', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
          <ActionButtons
            onTestSelection={handleTestSelection}
            isSelectionRunning={isSelectionRunning}
            disabled={selectionDisabled}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            {selectionResults && selectionResults.totalTests > 0 && (
              <button
                onClick={() => setShowTestSummary(true)}
                style={{
                  padding: '8px 16px',
                  background: '#4caf50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Test Summary
              </button>
            )}
            <button
              onClick={() => setShowRiskAnalysis(!showRiskAnalysis)}
              style={{
                padding: '8px 16px',
                background: showRiskAnalysis ? '#ff9800' : 'transparent',
                color: showRiskAnalysis ? 'white' : '#ff9800',
                border: '1px solid #ff9800',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              {showRiskAnalysis ? 'Hide' : 'Configure'} Risk Analysis
            </button>
          </div>
        </div>
        {showRiskAnalysis && (
          <div style={{ marginTop: '16px' }}>
            <RiskAnalysisPanel 
              repoId={repository.id}
              onSave={async (threshold) => {
                // Reload repository to get updated threshold
                await loadRepository();
                // Clear selection results if threshold is disabled (to hide stale warning)
                if (threshold === null) {
                  setSelectionResults(null);
                  setSelectionDisabled(false);
                }
                setShowRiskAnalysis(false);
              }}
              onCancel={() => setShowRiskAnalysis(false)}
            />
          </div>
        )}
      </div>

      {/* Risk Analysis Warning Banner - Only show if threshold is enabled (not null) */}
      {selectionResults && 
       selectionResults.selectionDisabled && 
       selectionResults.riskAnalysis && 
       repository && 
       repository.risk_threshold !== null && 
       repository.risk_threshold !== undefined && (
        <div style={{
          padding: '16px',
          marginBottom: '20px',
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '4px',
          color: '#856404'
        }}>
          <strong>Risk Threshold Exceeded</strong>
          <p style={{ margin: '8px 0 0 0' }}>
            {selectionResults.riskAnalysis.message || 
              `Changed files (${selectionResults.riskAnalysis.changed_files}) exceed threshold (${selectionResults.riskAnalysis.threshold}). All tests will be executed.`}
          </p>
        </div>
      )}

      {/* Test Repository Bindings */}
      <div style={{ marginBottom: '20px', padding: '20px', backgroundColor: '#fafafa', borderRadius: '8px', border: '1px solid #ddd' }}>
        <TestRepositoryBinding 
          repositoryId={repository.id}
          onUpdate={() => {
            // Reload repository data and bound test repositories
            loadRepository();
            loadBoundTestRepositories();
          }}
        />
      </div>

      <div className="tabs" style={{ flexShrink: 0 }}>
        <button
          className={`tab ${activeTab === 'diff' ? 'active' : ''}`}
          onClick={() => setActiveTab('diff')}
        >
          Git Diff
        </button>
        <button
          className={`tab ${activeTab === 'selection' ? 'active' : ''}`}
          onClick={() => setActiveTab('selection')}
        >
          Test Selection
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'diff' && (
          <div>
            <DiffStats 
              stats={diffStats}
              changedFiles={changedFiles}
              onViewFullDiff={() => setIsDiffModalOpen(true)}
            />
            <DiffViewer 
              diffContent={diffContent} 
              changedFiles={changedFiles} 
            />
            <DiffModal
              isOpen={isDiffModalOpen}
              onClose={() => setIsDiffModalOpen(false)}
              diffContent={diffContent}
              changedFiles={changedFiles}
              stats={diffStats}
            />
          </div>
        )}
        {activeTab === 'selection' && (
          <ResultsDisplay selectionResults={selectionResults} />
        )}
      </div>

      {/* Test Summary Modal */}
      <TestSummaryModal
        isOpen={showTestSummary}
        onClose={() => setShowTestSummary(false)}
        selectionResults={selectionResults}
        totalTestsInDb={totalTestsInDb}
      />
    </div>
  );
};

export default RepositoryDetail;
