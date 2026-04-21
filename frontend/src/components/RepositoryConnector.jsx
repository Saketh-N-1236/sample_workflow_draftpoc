import React, { useState, useEffect } from 'react';
import '../styles/App.css';

const RepositoryConnector = ({ onConnect }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [provider, setProvider] = useState('auto'); // 'auto', 'github', 'gitlab'
  const [accessToken, setAccessToken] = useState('');
  const [showToken, setShowToken] = useState(false);
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
      const connectData = {
        url: repoUrl,
        provider: provider === 'auto' ? null : provider,
        access_token: accessToken.trim() || null,
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
              style={{ minHeight: 'auto', padding: '10px 12px' }}
              onKeyPress={(e) => e.key === 'Enter' && handleConnect()}
            />
          </div>

          {/* Personal Access Token */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: '#1a1a1a' }}>
              Personal Access Token
              <span style={{ fontWeight: 400, color: '#888', marginLeft: '6px' }}>(required for private repos)</span>
            </label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type={showToken ? 'text' : 'password'}
                className="text-input"
                placeholder={
                  provider === 'github'
                    ? "ghp_xxxxxxxxxxxx  (repo scope required)"
                    : provider === 'gitlab'
                    ? "glpat-xxxxxxxxxxxx  (read_api + read_repository)"
                    : "Paste your Personal Access Token here"
                }
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                style={{ minHeight: 'auto', padding: '10px 12px', flex: 1, fontFamily: accessToken && !showToken ? 'monospace' : 'inherit' }}
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowToken(v => !v)}
                style={{
                  padding: '8px 12px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '6px',
                  background: 'white',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: '#555',
                  whiteSpace: 'nowrap',
                }}
              >
                {showToken ? 'Hide' : 'Show'}
              </button>
            </div>
            <div style={{ fontSize: '12px', color: '#888' }}>
              {provider === 'github' && 'GitHub: Settings → Developer settings → Personal access tokens → Tokens (classic) → repo scope'}
              {provider === 'gitlab' && 'GitLab: User Settings → Access Tokens → read_api + read_repository scopes'}
              {provider === 'auto' && 'Token is stored encrypted and never exposed in API responses.'}
            </div>
          </div>

          {/* Connect button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
            <button
              className="button button-primary"
              onClick={handleConnect}
              disabled={!repoUrl.trim() || isConnecting}
              style={{ minWidth: '120px' }}
            >
              {isConnecting ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RepositoryConnector;
