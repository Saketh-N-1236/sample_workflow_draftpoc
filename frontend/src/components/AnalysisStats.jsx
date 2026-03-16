import React from 'react';
import '../styles/App.css';

const AnalysisStats = ({ analysisResults }) => {
  if (!analysisResults) {
    return null;
  }

  const stats = [
    {
      label: 'Total Tests',
      value: analysisResults.totalTests || 0,
      color: '#1976d2'
    },
    {
      label: 'Test Files',
      value: analysisResults.testFiles || analysisResults.filesAnalyzed || 0,
      color: '#2e7d32'
    },
    {
      label: 'Test Classes',
      value: analysisResults.totalTestClasses || 0,
      color: '#ed6c02'
    },
    {
      label: 'Test Methods',
      value: analysisResults.totalTestMethods || analysisResults.totalTests || 0,
      color: '#9c27b0'
    },
    {
      label: 'Functions',
      value: analysisResults.functionsExtracted || 0,
      color: '#0288d1'
    },
    {
      label: 'Modules',
      value: analysisResults.modulesIdentified || 0,
      color: '#c2185b'
    },
    {
      label: 'Dependencies',
      value: analysisResults.totalDependencies || 0,
      color: '#00796b'
    },
    {
      label: 'Production Classes',
      value: analysisResults.totalProductionClasses || 0,
      color: '#5d4037'
    }
  ];

  return (
    <div className="analysis-stats-container">
      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-box">
            <div className="stat-content">
              <div className="stat-label">{stat.label}</div>
              <div className="stat-value" style={{ color: stat.color }}>
                {stat.value.toLocaleString()}
              </div>
            </div>
          </div>
        ))}
      </div>
      {analysisResults.framework && (
        <div className="framework-info">
          <span className="framework-label">Framework:</span>
          <span className="framework-value">{analysisResults.framework}</span>
        </div>
      )}
      {analysisResults.testsWithDescriptions !== undefined && analysisResults.testsWithDescriptions > 0 && (
        <div className="metadata-info">
          <span className="metadata-label">Tests with Descriptions:</span>
          <span className="metadata-value">{analysisResults.testsWithDescriptions}</span>
        </div>
      )}
    </div>
  );
};

export default AnalysisStats;
