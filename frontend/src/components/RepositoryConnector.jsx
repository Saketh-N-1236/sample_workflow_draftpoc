import React, { useState, useEffect } from 'react';
import '../styles/App.css';

const RepositoryConnector = ({ onConnect }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [provider, setProvider] = useState('auto'); // 'auto', 'github', 'gitlab'
  const [isConnecting, setIsConnecting] = useState(false);

  // Auto-detect provider from URL
  useEffect(() => {
    if (repoUrl.trim()) {
      if (repoUrl.includes('github.com')) {
        setProvider('github');
      } else if (repoUrl.includes('gitlab.com') || repoUrl.includes('gitlab.')) {
        setProvider('gitlab');
      } else {
        setProvider('auto');
      }
    }
  }, [repoUrl]);

  const handleConnect = async () => {
    if (!repoUrl.trim()) return;
    
    setIsConnecting(true);
    try {
      // Send provider only if not auto-detected
      const connectData = {
        url: repoUrl,
        provider: provider === 'auto' ? null : provider
      };
      await onConnect(connectData);
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="details-section">
      <div className="section-title">Connect Repository</div>
      <div className="section-content">
        <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Provider Selection */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: '#1a1a1a' }}>
              Repository Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #e0e0e0',
                borderRadius: '6px',
                fontSize: '14px',
                background: 'white',
                cursor: 'pointer'
              }}
            >
              <option value="auto">Auto-detect</option>
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </select>
          </div>

          {/* Repository URL */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: '#1a1a1a' }}>
              Repository URL
            </label>
            <div style={{ display: 'flex', gap: '12px' }}>
              <input
                type="text"
                className="text-input"
                placeholder={
                  provider === 'github' 
                    ? "https://github.com/owner/repo.git"
                    : provider === 'gitlab'
                    ? "https://gitlab.com/group/project.git"
                    : "Enter Git repository URL"
                }
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                style={{ minHeight: 'auto', padding: '10px 12px', flex: 1 }}
                onKeyPress={(e) => e.key === 'Enter' && handleConnect()}
              />
              <button
                className="button button-primary"
                onClick={handleConnect}
                disabled={!repoUrl.trim() || isConnecting}
              >
                {isConnecting ? 'Connecting...' : 'Connect'}
              </button>
            </div>
          </div>

          {/* Help text */}
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            {provider === 'github' && (
              <span>GitHub: Set GITHUB_API_TOKEN in .env file for private repositories</span>
            )}
            {provider === 'gitlab' && (
              <span>GitLab: Set GITLAB_API_TOKEN in .env file for private repositories</span>
            )}
            {provider === 'auto' && (
              <span>Provider will be auto-detected from the URL</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RepositoryConnector;
