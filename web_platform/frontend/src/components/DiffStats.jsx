import React from 'react';
import '../styles/App.css';

const DiffStats = ({ stats, changedFiles, onViewFullDiff }) => {
  if (!stats && (!changedFiles || changedFiles.length === 0)) {
    return null;
  }

  const filesChanged = changedFiles?.length || stats?.files_changed || 0;
  const additions = stats?.additions || 0;
  const deletions = stats?.deletions || 0;
  const totalLines = additions + deletions;

  return (
    <div className="diff-stats-box">
      <div className="stats-grid">
        <div className="stat-item">
          <div className="stat-label">Files Changed</div>
          <div className="stat-value">{filesChanged}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Lines Added</div>
          <div className="stat-value stat-positive">+{additions}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Lines Removed</div>
          <div className="stat-value stat-negative">-{deletions}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Total Changes</div>
          <div className="stat-value">{totalLines}</div>
        </div>
      </div>
      {onViewFullDiff && (
        <div className="stats-footer">
          <button 
            className="link-button"
            onClick={onViewFullDiff}
          >
            View Full Git Diff →
          </button>
        </div>
      )}
    </div>
  );
};

export default DiffStats;
