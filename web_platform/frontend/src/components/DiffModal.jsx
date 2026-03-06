import React from 'react';
import '../styles/App.css';

const DiffModal = ({ isOpen, onClose, diffContent, changedFiles, stats }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Full Git Diff</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          {stats && (
            <div className="modal-stats">
              <div className="modal-stat-item">
                <span className="modal-stat-label">Files Changed:</span>
                <span className="modal-stat-value">{changedFiles?.length || stats.files_changed || 0}</span>
              </div>
              <div className="modal-stat-item">
                <span className="modal-stat-label">Additions:</span>
                <span className="modal-stat-value stat-positive">+{stats.additions || 0}</span>
              </div>
              <div className="modal-stat-item">
                <span className="modal-stat-label">Deletions:</span>
                <span className="modal-stat-value stat-negative">-{stats.deletions || 0}</span>
              </div>
            </div>
          )}
          {changedFiles && changedFiles.length > 0 && (
            <div className="modal-changed-files">
              <h3>Changed Files:</h3>
              <ul className="changed-files-list">
                {changedFiles.map((file, index) => (
                  <li key={index}>{file}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="modal-diff-content">
            <pre className="diff-content-pre">{diffContent || 'No diff content available.'}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiffModal;
