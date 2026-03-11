import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import '../styles/App.css';
import api from '../services/api';
import AnalysisStats from '../components/AnalysisStats';
import EmbeddingStatus from '../components/EmbeddingStatus';

const TestRepositoryAnalysis = () => {
  const { testRepoId } = useParams();
  const navigate = useNavigate();
  const [analysisData, setAnalysisData] = useState(null);
  const [testRepository, setTestRepository] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeSection, setActiveSection] = useState('summary');
  const [progressMessages, setProgressMessages] = useState([]);

  useEffect(() => {
    if (testRepoId) {
      loadTestRepository();
      loadAnalysisResults();
    }
  }, [testRepoId]);

  const loadTestRepository = async () => {
    try {
      const response = await api.getTestRepository(testRepoId);
      setTestRepository(response.data);
    } catch (err) {
      console.error('Failed to load test repository:', err);
    }
  };

  const loadAnalysisResults = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.getTestRepositoryAnalysis(testRepoId);
      setAnalysisData(response.data);
      if (response.data.test_repository) {
        setTestRepository(response.data.test_repository);
      }
    } catch (err) {
      console.error('Failed to load analysis results:', err);
      setError('Failed to load analysis results. Please run analysis first.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setError(null);
    setProgressMessages([]);
    
    try {
      // Start analysis
      const response = await api.analyzeTestRepository(testRepoId);
      
      // Show progress messages
      setProgressMessages(['Analysis started...', 'Running analysis pipeline...']);
      
      // Wait a bit then reload results
      setTimeout(async () => {
        await loadAnalysisResults();
        setIsRefreshing(false);
      }, 2000);
    } catch (err) {
      console.error('Failed to refresh analysis:', err);
      setError('Failed to refresh analysis. Please try again.');
      setProgressMessages([]);
      setIsRefreshing(false);
    }
  };

  const renderTestRegistry = () => {
    if (!analysisData?.test_registry?.tests) return <p>No test registry data available.</p>;
    
    const tests = analysisData.test_registry.tests;
    
    return (
      <div>
        <h3>Test Registry ({tests.length} tests)</h3>
        <div style={{ marginTop: '16px' }}>
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f5f5f5', position: 'sticky', top: 0 }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>Test ID</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>Test Name</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>Class</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>File</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>Type</th>
                </tr>
              </thead>
              <tbody>
                {tests.map((test, idx) => (
                  <tr key={test.test_id || idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '12px', fontFamily: 'monospace', fontSize: '12px' }}>{test.test_id}</td>
                    <td style={{ padding: '12px' }}>{test.method_name}</td>
                    <td style={{ padding: '12px' }}>{test.class_name || '-'}</td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#666' }}>{test.file_path}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{ 
                        padding: '4px 8px', 
                        borderRadius: '4px', 
                        background: test.test_type === 'unit' ? '#e3f2fd' : test.test_type === 'integration' ? '#f3e5f5' : '#fff3e0',
                        color: test.test_type === 'unit' ? '#1976d2' : test.test_type === 'integration' ? '#7b1fa2' : '#e65100',
                        fontSize: '12px',
                        fontWeight: '500'
                      }}>
                        {test.test_type || 'other'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  const renderTestMetadata = () => {
    if (!analysisData?.test_metadata?.test_metadata) return <p>No test metadata available.</p>;
    
    const metadata = analysisData.test_metadata.test_metadata;
    
    return (
      <div>
        <h3>Test Metadata ({metadata.length} tests)</h3>
        <div style={{ marginTop: '16px' }}>
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {metadata.map((meta, idx) => (
              <div key={meta.test_id || idx} style={{ 
                padding: '16px', 
                marginBottom: '12px', 
                background: 'white', 
                borderRadius: '8px',
                border: '1px solid #e0e0e0'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong style={{ color: '#1976d2' }}>{meta.test_id}</strong>
                  <span style={{ fontSize: '12px', color: '#666' }}>{meta.file_path}</span>
                </div>
                {meta.description && (
                  <p style={{ margin: '8px 0', color: '#333' }}>{meta.description}</p>
                )}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '8px' }}>
                  {meta.markers && meta.markers.length > 0 && (
                    <span style={{ fontSize: '12px', color: '#666' }}>
                      Markers: {meta.markers.join(', ')}
                    </span>
                  )}
                  {meta.is_async && (
                    <span style={{ fontSize: '12px', color: '#1976d2', fontWeight: '500' }}>Async</span>
                  )}
                  {meta.is_parameterized && (
                    <span style={{ fontSize: '12px', color: '#2e7d32', fontWeight: '500' }}>Parameterized</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderStaticDependencies = () => {
    const staticDeps = analysisData?.static_dependencies;
    const deps = staticDeps?.dependencies || {};
    const totalTests = staticDeps?.total_tests || 0;
    const testsWithDeps = staticDeps?.tests_with_dependencies || 0;
    const totalReferences = staticDeps?.total_references || 0;
    const totalImports = staticDeps?.total_imports || 0;
    
    const hasData = Object.keys(deps).length > 0 || totalTests > 0;
    
    if (!hasData) {
      return (
        <div>
          <h3>Static Dependencies</h3>
          <div style={{ marginTop: '16px', padding: '16px', background: '#f5f5f5', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
            <p style={{ color: '#666', margin: 0 }}>
              No static dependencies data available. This could mean:
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li>Dependencies have not been extracted yet</li>
                <li>The analysis pipeline has not completed</li>
                <li>No production code dependencies were found in test files</li>
              </ul>
            </p>
          </div>
        </div>
      );
    }
    
    // Show statistics
    const testsWithProdDeps = Object.values(deps).filter(refs => Array.isArray(refs) && refs.length > 0).length;
    
    return (
      <div>
        <h3>Static Dependencies</h3>
        {(totalTests > 0 || totalImports > 0) && (
          <div style={{ marginTop: '8px', marginBottom: '16px', padding: '12px', background: '#f5f5f5', borderRadius: '6px', fontSize: '14px' }}>
            <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
              {totalTests > 0 && (
                <div><strong>Total Tests:</strong> {totalTests}</div>
              )}
              {totalImports > 0 && (
                <div><strong>Total Imports:</strong> {totalImports}</div>
              )}
              {totalReferences > 0 && (
                <div><strong>Production Dependencies:</strong> {totalReferences}</div>
              )}
              {testsWithProdDeps > 0 && (
                <div><strong>Tests with Production Dependencies:</strong> {testsWithProdDeps}</div>
              )}
            </div>
            {totalImports > 0 && totalReferences === 0 && (
              <div style={{ marginTop: '8px', padding: '8px', background: '#fff3cd', borderRadius: '4px', fontSize: '13px', color: '#856404' }}>
                <strong>Note:</strong> All imports are test framework imports (e.g., JUnit, pytest). No production code dependencies were found.
              </div>
            )}
          </div>
        )}
        <div style={{ marginTop: '16px' }}>
          {Object.keys(deps).length === 0 ? (
            <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
              <p style={{ color: '#666', margin: 0 }}>
                No production code dependencies found. All imports in test files are test framework imports.
              </p>
            </div>
          ) : (
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {Object.entries(deps).slice(0, 100).map(([testId, depList], idx) => (
                <div key={idx} style={{ 
                  padding: '12px', 
                  marginBottom: '8px', 
                  background: 'white', 
                  borderRadius: '6px',
                  border: '1px solid #e0e0e0'
                }}>
                  <strong style={{ color: '#1976d2', fontSize: '13px' }}>{testId}</strong>
                  <div style={{ marginTop: '4px', fontSize: '12px', color: '#666' }}>
                    {Array.isArray(depList) && depList.length > 0 ? (
                      depList.join(', ')
                    ) : (
                      <span style={{ fontStyle: 'italic', color: '#999' }}>No production dependencies</span>
                    )}
                  </div>
                </div>
              ))}
              {Object.keys(deps).length > 100 && (
                <p style={{ color: '#666', fontStyle: 'italic', marginTop: '12px' }}>
                  Showing first 100 of {Object.keys(deps).length} tests...
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderFunctionCalls = () => {
    const funcCalls = analysisData?.function_calls;
    const mappings = funcCalls?.function_mappings || [];
    const totalTests = funcCalls?.total_tests || 0;
    const testsWithCalls = funcCalls?.tests_with_function_calls || 0;
    const totalMappings = funcCalls?.total_mappings || 0;
    
    if (!funcCalls || (mappings.length === 0 && totalTests === 0)) {
      return (
        <div>
          <h3>Function Calls</h3>
          <div style={{ marginTop: '16px', padding: '16px', background: '#f5f5f5', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
            <p style={{ color: '#666', margin: 0 }}>
              No function calls data available. This could mean:
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li>Function calls have not been extracted yet</li>
                <li>The analysis pipeline has not completed</li>
                <li>No function call mappings were found in test files</li>
              </ul>
            </p>
          </div>
        </div>
      );
    }
    
    return (
      <div>
        <h3>Function Calls</h3>
        {(totalTests > 0 || totalMappings > 0) && (
          <div style={{ marginTop: '8px', marginBottom: '16px', padding: '12px', background: '#f5f5f5', borderRadius: '6px', fontSize: '14px' }}>
            <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
              {totalTests > 0 && (
                <div><strong>Total Tests:</strong> {totalTests}</div>
              )}
              {totalMappings > 0 && (
                <div><strong>Total Mappings:</strong> {totalMappings}</div>
              )}
              {testsWithCalls > 0 && (
                <div><strong>Tests with Function Calls:</strong> {testsWithCalls}</div>
              )}
            </div>
          </div>
        )}
        <div style={{ marginTop: '16px' }}>
          {mappings.length === 0 ? (
            <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
              <p style={{ color: '#666', margin: 0 }}>
                No function call mappings found. Tests may not be calling production functions directly, or the function call extraction did not find any mappings.
              </p>
            </div>
          ) : (
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {mappings.slice(0, 100).map((mapping, idx) => (
                <div key={idx} style={{ 
                  padding: '12px', 
                  marginBottom: '8px', 
                  background: 'white', 
                  borderRadius: '6px',
                  border: '1px solid #e0e0e0'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong style={{ color: '#1976d2', fontSize: '13px' }}>{mapping.test_id}</strong>
                    <span style={{ fontSize: '12px', color: '#666' }}>{mapping.file_path}</span>
                  </div>
                  {mapping.functions_tested && mapping.functions_tested.length > 0 && (
                    <div style={{ marginTop: '4px', fontSize: '12px', color: '#333' }}>
                      Functions: {mapping.functions_tested.join(', ')}
                    </div>
                  )}
                </div>
              ))}
              {mappings.length > 100 && (
                <p style={{ color: '#666', fontStyle: 'italic', marginTop: '12px' }}>
                  Showing first 100 of {mappings.length} function mappings...
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderReverseIndex = () => {
    const reverseIndex = analysisData?.reverse_index?.reverse_index || {};
    const totalProductionClasses = analysisData?.reverse_index?.total_production_classes || 0;
    const totalMappings = analysisData?.reverse_index?.total_mappings || 0;
    
    if (!reverseIndex || Object.keys(reverseIndex).length === 0) {
      return (
        <div>
          <h3>Reverse Index (Production Code → Tests)</h3>
          <div style={{ marginTop: '16px', padding: '16px', background: '#f5f5f5', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
            <p style={{ color: '#666', margin: 0 }}>
              No reverse index available. This typically means:
              <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                <li>No production code dependencies were found in the test files</li>
                <li>All imports are test framework imports (e.g., JUnit, pytest)</li>
                <li>The reverse index has not been generated yet</li>
              </ul>
            </p>
            {totalProductionClasses === 0 && totalMappings === 0 && (
              <p style={{ marginTop: '12px', color: '#666', fontStyle: 'italic' }}>
                Statistics: {totalProductionClasses} production classes, {totalMappings} mappings
              </p>
            )}
          </div>
        </div>
      );
    }
    
    return (
      <div>
        <h3>Reverse Index (Production Code → Tests)</h3>
        {totalProductionClasses > 0 && (
          <div style={{ marginTop: '8px', marginBottom: '16px', color: '#666', fontSize: '14px' }}>
            <strong>{totalProductionClasses}</strong> production classes mapped to <strong>{totalMappings}</strong> test references
          </div>
        )}
        <div style={{ marginTop: '16px' }}>
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {Object.entries(reverseIndex).slice(0, 100).map(([productionCode, testIds], idx) => (
              <div key={idx} style={{ 
                padding: '12px', 
                marginBottom: '8px', 
                background: 'white', 
                borderRadius: '6px',
                border: '1px solid #e0e0e0'
              }}>
                <strong style={{ color: '#2e7d32', fontSize: '13px' }}>{productionCode}</strong>
                <div style={{ marginTop: '4px', fontSize: '12px', color: '#666' }}>
                  Tests: {Array.isArray(testIds) ? testIds.join(', ') : JSON.stringify(testIds)}
                </div>
              </div>
            ))}
            {Object.keys(reverseIndex).length > 100 && (
              <p style={{ color: '#666', fontStyle: 'italic', marginTop: '12px' }}>
                Showing first 100 of {Object.keys(reverseIndex).length} entries...
              </p>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderTestStructure = () => {
    if (!analysisData?.test_structure) return <p>No test structure data available.</p>;
    
    const structure = analysisData.test_structure;
    
    return (
      <div>
        <h3>Test Structure</h3>
        <div style={{ marginTop: '16px' }}>
          <pre style={{ 
            background: '#f5f5f5', 
            padding: '16px', 
            borderRadius: '8px', 
            overflow: 'auto',
            fontSize: '13px',
            maxHeight: '600px'
          }}>
            {JSON.stringify(structure, null, 2)}
          </pre>
        </div>
      </div>
    );
  };

  const renderTestFiles = () => {
    if (!analysisData?.test_files?.files) return <p>No test files data available.</p>;
    
    const files = analysisData.test_files.files;
    
    return (
      <div>
        <h3>Test Files ({files.length} files)</h3>
        <div style={{ marginTop: '16px' }}>
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {files.map((file, idx) => (
              <div key={idx} style={{ 
                padding: '12px', 
                marginBottom: '8px', 
                background: 'white', 
                borderRadius: '6px',
                border: '1px solid #e0e0e0'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong style={{ color: '#1976d2' }}>{file.path}</strong>
                  <span style={{ fontSize: '12px', color: '#666' }}>
                    {file.lines || 0} lines
                  </span>
                </div>
                {file.category && (
                  <span style={{ 
                    fontSize: '12px', 
                    color: '#666',
                    marginTop: '4px',
                    display: 'block'
                  }}>
                    Category: {file.category}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderFrameworkDetection = () => {
    if (!analysisData?.framework_detection) return <p>No framework detection data available.</p>;
    
    const framework = analysisData.framework_detection;
    
    return (
      <div>
        <h3>Framework Detection</h3>
        <div style={{ marginTop: '16px', padding: '16px', background: 'white', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
            <div>
              <strong>Framework:</strong> {framework.detected_framework || 'Unknown'}
            </div>
            {framework.confidence && (
              <div>
                <strong>Confidence:</strong> {framework.confidence}
              </div>
            )}
          </div>
          {framework.evidence && (
            <div style={{ marginTop: '12px' }}>
              <strong>Evidence:</strong>
              <pre style={{ marginTop: '8px', padding: '12px', background: '#f5f5f5', borderRadius: '4px', fontSize: '12px' }}>
                {JSON.stringify(framework.evidence, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    );
  };

  const sections = [
    { id: 'summary', label: 'Summary' },
    { id: 'test_files', label: 'Test Files' },
    { id: 'framework', label: 'Framework Detection' },
    { id: 'test_registry', label: 'Test Registry' },
    { id: 'test_metadata', label: 'Test Metadata' },
    { id: 'static_dependencies', label: 'Static Dependencies' },
    { id: 'function_calls', label: 'Function Calls' },
    { id: 'reverse_index', label: 'Reverse Index' },
    { id: 'test_structure', label: 'Test Structure' },
  ];

  if (isLoading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <p>Loading analysis results...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px' }}>
        <div style={{ padding: '16px', background: '#ffebee', borderRadius: '8px', color: '#c62828', marginBottom: '16px' }}>
          {error}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={loadAnalysisResults}
            style={{ padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Retry
          </button>
          <button 
            onClick={() => navigate('/test-repositories')}
            style={{ padding: '8px 16px', background: '#666', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Back to Test Repositories
          </button>
        </div>
      </div>
    );
  }

  const summaryData = analysisData?.summary_report?.data || analysisData?.summary_report;
  
  // Fallback to API statistics if summary report is not available
  const statsData = summaryData ? {
    totalTests: summaryData.test_inventory?.total_tests || analysisData?.totalTests || 0,
    testFiles: summaryData.test_repository_overview?.total_test_files || analysisData?.testFiles || 0,
    totalTestClasses: summaryData.test_inventory?.total_test_classes || analysisData?.totalTestClasses || 0,
    totalTestMethods: summaryData.test_inventory?.total_tests || analysisData?.totalTestMethods || 0,
    functionsExtracted: summaryData.dependencies?.total_dependency_mappings || analysisData?.functionsExtracted || 0,
    modulesIdentified: summaryData.structure?.package_count || analysisData?.modulesIdentified || 0,
    totalDependencies: summaryData.dependencies?.total_dependency_mappings || analysisData?.totalDependencies || 0,
    totalProductionClasses: summaryData.dependencies?.total_production_classes_referenced || analysisData?.totalProductionClasses || 0,
    testsWithDescriptions: summaryData.metadata?.tests_with_descriptions || 0,
    framework: summaryData.test_repository_overview?.test_framework || analysisData?.framework || 'Unknown'
  } : {
    totalTests: analysisData?.totalTests || 0,
    testFiles: analysisData?.testFiles || 0,
    totalTestClasses: analysisData?.totalTestClasses || 0,
    totalTestMethods: analysisData?.totalTestMethods || 0,
    functionsExtracted: analysisData?.functionsExtracted || 0,
    modulesIdentified: analysisData?.modulesIdentified || 0,
    totalDependencies: analysisData?.totalDependencies || 0,
    totalProductionClasses: analysisData?.totalProductionClasses || 0,
    testsWithDescriptions: 0,
    framework: analysisData?.framework || 'Unknown'
  };

  return (
    <div className="analysis-results-page" style={{ padding: '20px' }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 className="page-title" style={{ fontSize: '24px', fontWeight: '600', marginBottom: '8px' }}>
            Analysis Results
          </h1>
          {testRepository && (
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color: '#666', fontSize: '14px' }}>
                <strong>Repository:</strong> {testRepository.name}
              </span>
              <span style={{ color: '#666', fontSize: '14px' }}>
                <strong>Schema:</strong> {testRepository.schema_name}
              </span>
              <span style={{ 
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: '600',
                color: 'white',
                backgroundColor: testRepository.status === 'ready' ? '#2e7d32' : testRepository.status === 'analyzing' ? '#f57c00' : '#c62828'
              }}>
                {testRepository.status?.toUpperCase() || 'PENDING'}
              </span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {analysisData?.last_updated && (
            <span style={{ fontSize: '14px', color: '#666' }}>
              Last updated: {new Date(analysisData.last_updated).toLocaleString()}
            </span>
          )}
          <button
            className="button button-primary"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : '↻ Refresh Analysis'}
          </button>
          <button
            className="button"
            onClick={() => navigate('/test-repositories')}
            style={{ background: '#666', color: 'white' }}
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Progress Messages Display */}
      {(isRefreshing || progressMessages.length > 0) && (
        <div style={{ 
          marginBottom: '24px', 
          padding: '16px', 
          background: '#f5f5f5', 
          borderRadius: '8px',
          border: '1px solid #e0e0e0',
          maxHeight: '300px',
          overflowY: 'auto'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#333' }}>
              {isRefreshing ? 'Analysis in Progress...' : 'Analysis Complete'}
            </h3>
            {!isRefreshing && progressMessages.length > 0 && (
              <button
                onClick={() => setProgressMessages([])}
                style={{
                  padding: '4px 8px',
                  background: 'transparent',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Clear
              </button>
            )}
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: '13px' }}>
            {progressMessages.length === 0 && isRefreshing && (
              <div style={{ color: '#666', fontStyle: 'italic' }}>Starting analysis...</div>
            )}
            {progressMessages.map((msg, idx) => (
              <div 
                key={idx} 
                style={{ 
                  padding: '4px 0',
                  color: msg.includes('[ERROR]') || msg.includes('ERROR') ? '#c62828' : msg.includes('[OK]') || msg.includes('SUCCESS') ? '#2e7d32' : msg.includes('[WARN]') || msg.includes('WARNING') ? '#f57c00' : '#333',
                  borderLeft: msg.includes('[ERROR]') || msg.includes('ERROR') ? '3px solid #c62828' : msg.includes('[OK]') || msg.includes('SUCCESS') ? '3px solid #2e7d32' : '3px solid transparent',
                  paddingLeft: '8px',
                  marginLeft: msg.startsWith('  →') ? '16px' : '0'
                }}
              >
                {msg}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Embedding Status */}
      <EmbeddingStatus testRepoId={testRepoId} onRegenerate={handleRefresh} />

      {/* Analysis Stats - Always show, using fallback if summary not available */}
      <div style={{ marginBottom: '24px' }}>
        <AnalysisStats analysisResults={statsData} />
      </div>

      <div className="tabs" style={{ marginBottom: '20px' }}>
        {sections.map(section => (
          <button
            key={section.id}
            className={`tab ${activeSection === section.id ? 'active' : ''}`}
            onClick={() => setActiveSection(section.id)}
          >
            {section.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeSection === 'summary' && summaryData && (
          <div>
            <h3>Summary Report</h3>
            <pre style={{ 
              background: '#f5f5f5', 
              padding: '16px', 
              borderRadius: '8px', 
              overflow: 'auto',
              fontSize: '13px',
              maxHeight: '600px'
            }}>
              {JSON.stringify(summaryData, null, 2)}
            </pre>
          </div>
        )}
        {activeSection === 'test_files' && renderTestFiles()}
        {activeSection === 'framework' && renderFrameworkDetection()}
        {activeSection === 'test_registry' && renderTestRegistry()}
        {activeSection === 'test_metadata' && renderTestMetadata()}
        {activeSection === 'static_dependencies' && renderStaticDependencies()}
        {activeSection === 'function_calls' && renderFunctionCalls()}
        {activeSection === 'reverse_index' && renderReverseIndex()}
        {activeSection === 'test_structure' && renderTestStructure()}
      </div>
    </div>
  );
};

export default TestRepositoryAnalysis;
