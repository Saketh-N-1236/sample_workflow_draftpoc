import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import '../styles/App.css';

const DiffViewer = ({ diffContent, changedFiles = [] }) => {
  if (!diffContent && changedFiles.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#999', fontStyle: 'italic' }}>
        No diff content available. Select a branch and refresh to see changes.
      </div>
    );
  }

  // Show a preview of the diff (first 50 lines or so)
  const diffLines = diffContent ? diffContent.split('\n') : [];
  const previewLines = diffLines.slice(0, 50);
  const previewContent = previewLines.join('\n');
  const hasMoreLines = diffLines.length > 50;

  return (
    <div style={{ marginTop: '20px' }}>
      {diffContent && (
        <div className="diff-viewer" style={{ maxHeight: '600px', overflowY: 'auto' }}>
          <SyntaxHighlighter
            language="diff"
            style={vscDarkPlus}
            customStyle={{ margin: 0, padding: '16px', background: '#1e1e1e' }}
          >
            {previewContent}
          </SyntaxHighlighter>
          {hasMoreLines && (
            <div style={{ 
              padding: '12px', 
              background: '#2d2d2d', 
              color: '#999', 
              fontSize: '13px',
              textAlign: 'center',
              borderTop: '1px solid #3d3d3d'
            }}>
              Showing first 50 lines. Click "View Full Git Diff" above to see complete diff.
            </div>
          )}
        </div>
      )}
      {!diffContent && changedFiles.length > 0 && (
        <div style={{ padding: '20px', background: '#f9f9f9', borderRadius: '6px' }}>
          <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '12px' }}>
            Changed Files ({changedFiles.length}):
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {changedFiles.map((file, idx) => (
              <li key={idx} style={{ 
                padding: '8px 0', 
                borderBottom: '1px solid #e0e0e0',
                fontFamily: 'monospace',
                fontSize: '13px'
              }}>
                {file}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default DiffViewer;
