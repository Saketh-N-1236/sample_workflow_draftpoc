import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import RepositoryConnector from '../components/RepositoryConnector';
import DiffViewer from '../components/DiffViewer';
import ActionButtons from '../components/ActionButtons';
import ResultsDisplay from '../components/ResultsDisplay';
import BranchSelector from '../components/BranchSelector';
import '../styles/App.css';
import api from '../services/api';

const Dashboard = () => {
  const [activeSubTab, setActiveSubTab] = useState('repository');
  const [repository, setRepository] = useState(null);
  const [diffContent, setDiffContent] = useState('');
  const [changedFiles, setChangedFiles] = useState([]);
  const [isAnalysisRunning, setIsAnalysisRunning] = useState(false);
  const [isSelectionRunning, setIsSelectionRunning] = useState(false);
  const [isAnalysisComplete, setIsAnalysisComplete] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState('');
  const [analysisResults, setAnalysisResults] = useState(null);
  const [selectionResults, setSelectionResults] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);

  const fetchDiff = async (repoId) => {
    try {
      const response = await api.getDiff(repoId);
      console.log('Diff response:', {
        hasDiff: !!response.data.diff,
        diffLength: response.data.diff?.length || 0,
        changedFiles: response.data.changedFiles?.length || 0,
        stats: response.data.stats
      });
      setDiffContent(response.data.diff || '');
      setChangedFiles(response.data.changedFiles || []);
    } catch (error) {
      console.error('Failed to fetch diff:', error);
      console.error('Error details:', error.response?.data);
    }
  };

  // Load repositories on component mount
  useEffect(() => {
    const loadRepositories = async () => {
      setIsLoadingRepos(true);
      try {
        const response = await api.listRepositories();
        const repos = response.data || [];
        setRepositories(repos);
        
        // Auto-select first repository if available
        if (repos.length > 0) {
          const firstRepo = repos[0];
          setSelectedRepo(firstRepo.id);
          setRepository(firstRepo);
          await fetchDiff(firstRepo.id);
        }
      } catch (error) {
        console.error('Failed to load repositories:', error);
        // Don't show error alert - just log it (user might not have any repos yet)
      } finally {
        setIsLoadingRepos(false);
      }
    };
    
    loadRepositories();
  }, []);

  const handleConnect = async (connectData) => {
    try {
      // connectData can be a string (backward compatibility) or object with url and provider
      const requestData = typeof connectData === 'string' 
        ? { url: connectData }
        : connectData;
      
      const response = await api.connectRepository(requestData);
      const repo = response.data;
      setRepository(repo);
      setRepositories([...repositories, repo]);
      setSelectedRepo(repo.id);
      
      // Fetch diff
      await fetchDiff(repo.id);
    } catch (error) {
      console.error('Failed to connect repository:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to connect repository. Please check the URL and try again.';
      alert(errorMsg);
    }
  };

  const handleTestAnalysis = async () => {
    if (!repository) {
      alert('Please connect a repository first.');
      return;
    }

    setIsAnalysisRunning(true);
    setAnalysisProgress('Starting analysis...');
    setAnalysisResults(null);

    try {
      const response = await api.runAnalysis(repository.id);
      setAnalysisResults(response.data);
      setIsAnalysisComplete(true);
      setAnalysisProgress('Analysis complete!');
    } catch (error) {
      console.error('Analysis failed:', error);
      alert('Analysis failed. Please check the console for details.');
    } finally {
      setIsAnalysisRunning(false);
      setAnalysisProgress('');
    }
  };

  const handleTestSelection = async () => {
    if (!repository) {
      alert('Please connect a repository first.');
      return;
    }

    if (!isAnalysisComplete) {
      alert('Please run Test Analysis first.');
      return;
    }

    setIsSelectionRunning(true);
    setSelectionResults(null);

    try {
      const response = await api.selectTests(repository.id);
      setSelectionResults(response.data);
    } catch (error) {
      console.error('Test selection failed:', error);
      alert('Test selection failed. Please check the console for details.');
    } finally {
      setIsSelectionRunning(false);
    }
  };

  const handleRepoSelect = (repoId) => {
    setSelectedRepo(repoId);
    const repo = repositories.find(r => r.id === repoId);
    if (repo) {
      setRepository(repo);
      fetchDiff(repoId);
    }
  };

  const handleRefreshRepository = async (repoId, event) => {
    event.stopPropagation(); // Prevent triggering repo selection
    
    try {
      const response = await api.refreshRepository(repoId);
      const refreshedRepo = response.data;
      
      // Update repository in list
      setRepositories(repos => 
        repos.map(r => r.id === repoId ? refreshedRepo : r)
      );
      
      // Update current repository if it's the one being refreshed
      if (repository && repository.id === repoId) {
        setRepository(refreshedRepo);
      }
      
      // Refresh diff
      await fetchDiff(repoId);
      
      alert('Repository refreshed successfully!');
    } catch (error) {
      console.error('Failed to refresh repository:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to refresh repository.';
      alert(errorMsg);
    }
  };

  const handleBranchChange = async (newBranch) => {
    if (!repository) return;
    
    try {
      // Update repository in state
      const updatedRepo = { ...repository, selected_branch: newBranch };
      setRepository(updatedRepo);
      
      // Update in repositories list
      setRepositories(repos => 
        repos.map(r => r.id === repository.id ? updatedRepo : r)
      );
      
      // Refresh diff with new branch
      await fetchDiff(repository.id);
    } catch (error) {
      console.error('Failed to handle branch change:', error);
    }
  };

  const subTabs = [
    { id: 'repository', label: 'Repository' },
    { id: 'analysis', label: 'Analysis Results' },
    { id: 'selection', label: 'Test Selection' },
  ];

  return (
    <div className="app-container">
      <Header />
      <div className="main-layout">
        <div className="content-area">
          <div className="sub-tabs">
            {subTabs.map(tab => (
              <button
                key={tab.id}
                className={`sub-tab ${activeSubTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveSubTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="content-panels">
            <div className="left-panel">
              <div className="panel-header">
                <div className="panel-title">Repositories</div>
                <div className="panel-subtitle">Connected repositories</div>
              </div>
              <div className="search-bar">
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search repositories..."
                />
              </div>
              <div className="filter-bar">
                <select className="filter-dropdown">
                  <option>All Repos ({repositories.length})</option>
                </select>
              </div>
              <div className="items-list">
                {isLoadingRepos ? (
                  <div style={{ padding: '16px', textAlign: 'center', color: '#999' }}>
                    Loading repositories...
                  </div>
                ) : repositories.length === 0 ? (
                  <div style={{ padding: '16px', textAlign: 'center', color: '#999' }}>
                    No repositories connected yet.
                  </div>
                ) : (
                  repositories.map(repo => (
                    <div
                      key={repo.id}
                      className={`list-item ${selectedRepo === repo.id ? 'active' : ''}`}
                      onClick={() => handleRepoSelect(repo.id)}
                      style={{ position: 'relative' }}
                    >
                      <div className="list-item-id">REPO-{String(repo.id).padStart(3, '0')}</div>
                      <div className="list-item-title">{repo.url.split('/').pop()}</div>
                      <button
                        onClick={(e) => handleRefreshRepository(repo.id, e)}
                        style={{
                          position: 'absolute',
                          right: '8px',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '4px 8px',
                          fontSize: '12px',
                          color: '#666',
                          borderRadius: '4px'
                        }}
                        onMouseEnter={(e) => {
                          e.target.style.background = '#f0f0f0';
                        }}
                        onMouseLeave={(e) => {
                          e.target.style.background = 'transparent';
                        }}
                        title="Refresh repository"
                      >
                        ↻
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="right-panel">
              <div className="details-header">
                <div>
                  <div className="details-title">
                    {repository ? `Repository: ${repository.url.split('/').pop()}` : 'Repository Details'}
                  </div>
                  {repository && (
                    <div className="details-timestamp">
                      Connected on {new Date(repository.createdAt || Date.now()).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
              <div className="details-content">
                {!repository ? (
                  <RepositoryConnector onConnect={handleConnect} />
                ) : (
                  <>
                    {activeSubTab === 'repository' && (
                      <>
                        <BranchSelector
                          repoId={repository.id}
                          selectedBranch={repository.selected_branch}
                          defaultBranch={repository.default_branch}
                          onBranchChange={handleBranchChange}
                        />
                        <DiffViewer diffContent={diffContent} changedFiles={changedFiles} />
                        <ActionButtons
                          onTestAnalysis={handleTestAnalysis}
                          onTestSelection={handleTestSelection}
                          isAnalysisRunning={isAnalysisRunning}
                          isSelectionRunning={isSelectionRunning}
                          isAnalysisComplete={isAnalysisComplete}
                          analysisProgress={analysisProgress}
                        />
                      </>
                    )}
                    {activeSubTab === 'analysis' && (
                      <ResultsDisplay analysisResults={analysisResults} />
                    )}
                    {activeSubTab === 'selection' && (
                      <ResultsDisplay selectionResults={selectionResults} />
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
