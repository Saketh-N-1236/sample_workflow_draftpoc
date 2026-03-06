import React, { useState, useEffect } from 'react';
import '../styles/App.css';
import api from '../services/api';

const TestSummaryModal = ({ isOpen, onClose, selectionResults, totalTestsInDb }) => {
  const [allTests, setAllTests] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadAllTests();
    }
  }, [isOpen]);

  const loadAllTests = async () => {
    setLoading(true);
    try {
      const response = await api.getAllTests();
      setAllTests(response.data.tests || []);
    } catch (error) {
      console.error('Failed to load all tests:', error);
      setAllTests([]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  // Calculate statistics
  const selectedTests = selectionResults?.tests || [];
  const selectedCount = selectedTests.length;
  const totalTests = allTests.length || totalTestsInDb || 0;
  const notSelectedCount = Math.max(0, totalTests - selectedCount);
  const selectedTestIds = new Set(selectedTests.map(t => String(t.test_id)));
  
  // Calculate average confidence score
  const confidenceScores = selectedTests
    .map(t => t.confidence_score)
    .filter(score => score !== undefined && score !== null);
  const avgConfidenceScore = confidenceScores.length > 0
    ? (confidenceScores.reduce((sum, score) => sum + score, 0) / confidenceScores.length).toFixed(1)
    : 0;
  
  // Calculate confidence distribution
  const highConfidence = confidenceScores.filter(s => s >= 70).length;
  const mediumConfidence = confidenceScores.filter(s => s >= 50 && s < 70).length;
  const lowConfidence = confidenceScores.filter(s => s < 50).length;

  // Get selected test IDs for highlighting
  const selectedTestIdsSet = new Set(selectedTests.map(t => String(t.test_id)));
  
  // Create a map of selected test details for quick lookup
  const selectedTestsMap = new Map();
  selectedTests.forEach(test => {
    selectedTestsMap.set(String(test.test_id), test);
  });

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '24px',
          maxWidth: '800px',
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '600' }}>Test Selection Summary</h2>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: '#666',
              padding: '0',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            ×
          </button>
        </div>

        {/* Summary Cards */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(4, 1fr)', 
          gap: '16px',
          marginBottom: '24px'
        }}>
          <div style={{
            padding: '20px',
            background: '#f5f5f5',
            borderRadius: '8px',
            textAlign: 'center',
            border: '2px solid #e0e0e0'
          }}>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#333', marginBottom: '8px' }}>
              {totalTests}
            </div>
            <div style={{ fontSize: '14px', color: '#666' }}>Total Tests</div>
          </div>

          <div style={{
            padding: '20px',
            background: '#e8f5e9',
            borderRadius: '8px',
            textAlign: 'center',
            border: '2px solid #4caf50'
          }}>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#2e7d32', marginBottom: '8px' }}>
              {selectedCount}
            </div>
            <div style={{ fontSize: '14px', color: '#2e7d32', fontWeight: '500' }}>Selected Tests</div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
              {totalTests > 0 ? `${((selectedCount / totalTests) * 100).toFixed(1)}%` : '0%'}
            </div>
          </div>

          <div style={{
            padding: '20px',
            background: '#ffebee',
            borderRadius: '8px',
            textAlign: 'center',
            border: '2px solid #f44336'
          }}>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#c62828', marginBottom: '8px' }}>
              {notSelectedCount}
            </div>
            <div style={{ fontSize: '14px', color: '#c62828', fontWeight: '500' }}>Not Selected</div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
              {totalTests > 0 ? `${((notSelectedCount / totalTests) * 100).toFixed(1)}%` : '0%'}
            </div>
          </div>

          <div style={{
            padding: '20px',
            background: '#fff3e0',
            borderRadius: '8px',
            textAlign: 'center',
            border: '2px solid #ff9800'
          }}>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#e65100', marginBottom: '8px' }}>
              {avgConfidenceScore}%
            </div>
            <div style={{ fontSize: '14px', color: '#e65100', fontWeight: '500' }}>Avg Confidence</div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
              {selectedCount > 0 ? `${selectedCount} tests` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Breakdown by Match Type */}
        {selectionResults && (
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>Breakdown by Match Type</h3>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(2, 1fr)', 
              gap: '12px' 
            }}>
              <div style={{
                padding: '12px',
                background: '#e3f2fd',
                borderRadius: '6px',
                border: '1px solid #90caf9'
              }}>
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>AST Matches</div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1976d2' }}>
                  {selectionResults.astMatches || 0}
                </div>
              </div>
              <div style={{
                padding: '12px',
                background: '#f3e5f5',
                borderRadius: '6px',
                border: '1px solid #ce93d8'
              }}>
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>Semantic Matches</div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#7b1fa2' }}>
                  {selectionResults.semanticMatches || 0}
                </div>
              </div>
              {selectionResults.overlapCount > 0 && (
                <div style={{
                  padding: '12px',
                  background: '#e1bee7',
                  borderRadius: '6px',
                  border: '1px solid #ba68c8',
                  gridColumn: 'span 2'
                }}>
                  <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px' }}>Found by Both Methods</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#6a1b9a' }}>
                    {selectionResults.overlapCount}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Quick Stats */}
        <div style={{ 
          padding: '16px', 
          background: '#f9f9f9', 
          borderRadius: '6px',
          marginBottom: '24px'
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>Quick Statistics</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '14px', marginBottom: '12px' }}>
            <div>
              <span style={{ color: '#666' }}>Selection Coverage: </span>
              <strong style={{ color: totalTests > 0 && (selectedCount / totalTests) >= 0.5 ? '#2e7d32' : '#f57c00' }}>
                {totalTests > 0 ? `${((selectedCount / totalTests) * 100).toFixed(1)}%` : '0%'}
              </strong>
            </div>
            <div>
              <span style={{ color: '#666' }}>Tests Remaining: </span>
              <strong style={{ color: '#c62828' }}>{notSelectedCount}</strong>
            </div>
          </div>
          
          {/* Confidence Score Distribution */}
          {selectedCount > 0 && (
            <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #e0e0e0' }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#666' }}>Confidence Score Distribution</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '13px' }}>
                <div>
                  <span style={{ color: '#666' }}>High (≥70%): </span>
                  <strong style={{ color: '#2e7d32' }}>{highConfidence}</strong>
                </div>
                <div>
                  <span style={{ color: '#666' }}>Medium (50-69%): </span>
                  <strong style={{ color: '#f57c00' }}>{mediumConfidence}</strong>
                </div>
                <div>
                  <span style={{ color: '#666' }}>Low (&lt;50%): </span>
                  <strong style={{ color: '#c62828' }}>{lowConfidence}</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Confidence Score Calculation Process */}
        {selectedCount > 0 && (
          <div style={{ 
            marginBottom: '24px', 
            padding: '16px', 
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '8px',
            color: 'white',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px', color: 'white' }}>
              📊 Confidence Score Calculation Process
            </h3>
            
            <div style={{ 
              background: 'rgba(255, 255, 255, 0.15)', 
              padding: '16px', 
              borderRadius: '6px',
              marginBottom: '16px',
              backdropFilter: 'blur(10px)'
            }}>
              <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: 'white' }}>
                Formula:
              </h4>
              <div style={{ 
                fontFamily: 'monospace', 
                fontSize: '16px', 
                background: 'rgba(0, 0, 0, 0.2)',
                padding: '12px',
                borderRadius: '4px',
                marginBottom: '12px',
                textAlign: 'center'
              }}>
                Total = (AST × 40%) + (Semantic × 30%) + (LLM × 20%) + (Speed × 10%)
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginBottom: '16px' }}>
              <div style={{ 
                background: 'rgba(255, 255, 255, 0.15)', 
                padding: '12px', 
                borderRadius: '6px',
                backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>AST Component (40%)</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>
                  Based on match type & quality
                </div>
                <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>
                  • Function-level: 85-100<br/>
                  • Exact match: 60-84<br/>
                  • Module pattern: 45-64<br/>
                  • Direct file: 50-60
                </div>
              </div>

              <div style={{ 
                background: 'rgba(255, 255, 255, 0.15)', 
                padding: '12px', 
                borderRadius: '6px',
                backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Semantic Component (30%)</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>
                  Vector similarity score
                </div>
                <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>
                  • Similarity × 100 (capped at 60)<br/>
                  • From semantic search<br/>
                  • Meaning-based matching
                </div>
              </div>

              <div style={{ 
                background: 'rgba(255, 255, 255, 0.15)', 
                padding: '12px', 
                borderRadius: '6px',
                backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>LLM Component (20%)</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>
                  AI relevance assessment
                </div>
                <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>
                  • LLM score × 100<br/>
                  • 0.0-1.0 relevance<br/>
                  • Context-aware analysis
                </div>
              </div>

              <div style={{ 
                background: 'rgba(255, 255, 255, 0.15)', 
                padding: '12px', 
                borderRadius: '6px',
                backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Speed Component (10%)</div>
                <div style={{ fontSize: '14px', fontWeight: '600' }}>
                  Fixed contribution
                </div>
                <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>
                  • Constant: 10 points<br/>
                  • Same for all tests<br/>
                  • Baseline factor
                </div>
              </div>
            </div>

            {/* Example Calculation */}
            {selectedTests.length > 0 && (() => {
              const exampleTest = selectedTests.find(t => t.confidence_breakdown) || selectedTests[0];
              const breakdown = exampleTest?.confidence_breakdown || {};
              const astScore = breakdown.ast_score ?? breakdown.astScore ?? 0;
              const vectorScore = breakdown.vector_score ?? breakdown.vectorScore ?? 0;
              const llmComponent = breakdown.llm_component ?? breakdown.llmComponent ?? 0;
              const speedComponent = breakdown.speed_component ?? breakdown.speedComponent ?? 10;
              const astPct = breakdown.ast_percentage ?? breakdown.astPercentage ?? 0;
              const semanticPct = breakdown.semantic_percentage ?? breakdown.semanticPercentage ?? 0;
              const llmPct = breakdown.llm_percentage ?? breakdown.llmPercentage ?? 0;
              const speedPct = breakdown.speed_percentage ?? breakdown.speedPercentage ?? 1;
              const totalScore = exampleTest?.confidence_score ?? 0;

              return (
                <div style={{ 
                  background: 'rgba(255, 255, 255, 0.2)', 
                  padding: '16px', 
                  borderRadius: '6px',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  marginBottom: '16px'
                }}>
                  <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: 'white' }}>
                    📝 Example Calculation (from selected tests):
                  </h4>
                  <div style={{ 
                    fontFamily: 'monospace', 
                    fontSize: '13px',
                    lineHeight: '1.8',
                    background: 'rgba(0, 0, 0, 0.2)',
                    padding: '12px',
                    borderRadius: '4px'
                  }}>
                    <div style={{ marginBottom: '8px' }}>
                      <span style={{ color: '#a8d5ff' }}>AST:</span> {astScore} × 0.40 = <strong>{astPct.toFixed(1)}%</strong>
                    </div>
                    <div style={{ marginBottom: '8px' }}>
                      <span style={{ color: '#d4a5ff' }}>Semantic:</span> {vectorScore} × 0.30 = <strong>{semanticPct.toFixed(1)}%</strong>
                    </div>
                    <div style={{ marginBottom: '8px' }}>
                      <span style={{ color: '#ffcc80' }}>LLM:</span> {llmComponent} × 0.20 = <strong>{llmPct.toFixed(1)}%</strong>
                    </div>
                    <div style={{ marginBottom: '8px' }}>
                      <span style={{ color: '#e0e0e0' }}>Speed:</span> {speedComponent} × 0.10 = <strong>{speedPct.toFixed(1)}%</strong>
                    </div>
                    <div style={{ 
                      marginTop: '12px', 
                      paddingTop: '12px', 
                      borderTop: '1px solid rgba(255, 255, 255, 0.3)',
                      fontSize: '16px',
                      fontWeight: '600'
                    }}>
                      <span style={{ color: '#fff' }}>Total Confidence Score: </span>
                      <strong style={{ color: '#ffeb3b', fontSize: '18px' }}>{totalScore}%</strong>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Actual Calculations for Selected Tests */}
            {(() => {
              // Get tests with confidence breakdown (limit to top 5 for display)
              const testsWithBreakdown = selectedTests
                .filter(t => t.confidence_breakdown)
                .slice(0, 5);
              
              if (testsWithBreakdown.length === 0) return null;

              return (
                <div style={{ 
                  background: 'rgba(255, 255, 255, 0.2)', 
                  padding: '16px', 
                  borderRadius: '6px',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.3)'
                }}>
                  <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: 'white' }}>
                    🔢 Actual Calculations (Top {testsWithBreakdown.length} Selected Tests):
                  </h4>
                  <div style={{ 
                    maxHeight: '400px',
                    overflowY: 'auto',
                    paddingRight: '8px'
                  }}>
                    {testsWithBreakdown.map((test, idx) => {
                      const breakdown = test.confidence_breakdown || {};
                      const astScore = breakdown.ast_score ?? breakdown.astScore ?? 0;
                      const vectorScore = breakdown.vector_score ?? breakdown.vectorScore ?? 0;
                      const llmComponent = breakdown.llm_component ?? breakdown.llmComponent ?? 0;
                      const speedComponent = breakdown.speed_component ?? breakdown.speedComponent ?? 10;
                      const astPct = breakdown.ast_percentage ?? breakdown.astPercentage ?? 0;
                      const semanticPct = breakdown.semantic_percentage ?? breakdown.semanticPercentage ?? 0;
                      const llmPct = breakdown.llm_percentage ?? breakdown.llmPercentage ?? 0;
                      const speedPct = breakdown.speed_percentage ?? breakdown.speedPercentage ?? 1;
                      const totalScore = test.confidence_score ?? 0;
                      const testName = test.method_name || test.test_id || `Test ${idx + 1}`;

                      return (
                        <div 
                          key={test.test_id || idx}
                          style={{ 
                            background: 'rgba(0, 0, 0, 0.2)',
                            padding: '12px',
                            borderRadius: '4px',
                            marginBottom: '12px',
                            border: '1px solid rgba(255, 255, 255, 0.1)'
                          }}
                        >
                          <div style={{ 
                            fontSize: '13px', 
                            fontWeight: '600', 
                            marginBottom: '10px',
                            color: '#ffeb3b',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}>
                            <span>{testName}</span>
                            <span style={{ 
                              fontSize: '16px',
                              color: totalScore >= 70 ? '#4caf50' : totalScore >= 50 ? '#ff9800' : '#f44336'
                            }}>
                              {totalScore}%
                            </span>
                          </div>
                          <div style={{ 
                            fontFamily: 'monospace', 
                            fontSize: '12px',
                            lineHeight: '1.6'
                          }}>
                            <div style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#a8d5ff' }}>AST ({astScore}):</span>
                              <strong style={{ color: '#fff' }}>{astPct.toFixed(1)}%</strong>
                            </div>
                            <div style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#d4a5ff' }}>Semantic ({vectorScore}):</span>
                              <strong style={{ color: '#fff' }}>{semanticPct.toFixed(1)}%</strong>
                            </div>
                            <div style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#ffcc80' }}>LLM ({llmComponent}):</span>
                              <strong style={{ color: '#fff' }}>{llmPct.toFixed(1)}%</strong>
                            </div>
                            <div style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ color: '#e0e0e0' }}>Speed ({speedComponent}):</span>
                              <strong style={{ color: '#fff' }}>{speedPct.toFixed(1)}%</strong>
                            </div>
                            <div style={{ 
                              marginTop: '8px', 
                              paddingTop: '8px', 
                              borderTop: '1px solid rgba(255, 255, 255, 0.2)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: '13px',
                              fontWeight: '600'
                            }}>
                              <span style={{ color: '#fff' }}>Total:</span>
                              <strong style={{ 
                                color: totalScore >= 70 ? '#4caf50' : totalScore >= 50 ? '#ff9800' : '#f44336',
                                fontSize: '14px'
                              }}>
                                {totalScore}%
                              </strong>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {selectedTests.filter(t => t.confidence_breakdown).length > 5 && (
                    <div style={{ 
                      marginTop: '12px', 
                      fontSize: '12px', 
                      opacity: 0.8,
                      fontStyle: 'italic',
                      textAlign: 'center'
                    }}>
                      Showing top 5 tests. {selectedTests.filter(t => t.confidence_breakdown).length - 5} more tests have detailed breakdowns in the table below.
                    </div>
                  )}
                </div>
              );
            })()}

            <div style={{ 
              marginTop: '16px', 
              padding: '12px', 
              background: 'rgba(255, 255, 255, 0.1)', 
              borderRadius: '6px',
              fontSize: '12px',
              opacity: 0.9
            }}>
              <strong>Note:</strong> AST-only tests (no semantic match) get a minimum boost to 50% to ensure they pass the 40% threshold. 
              The final score is capped between 0-100%.
            </div>
          </div>
        )}

        {/* LLM Input/Output Section */}
        {(() => {
          const llmData = selectionResults?.llmInputOutput || selectionResults?.llm_input_output;
          if (!llmData) return null;
          
          return (
            <div style={{ marginBottom: '24px', padding: '16px', background: '#f5f5f5', borderRadius: '6px', border: '2px solid #ff9800' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px', color: '#e65100' }}>
                🤖 LLM Reasoning Details
              </h3>
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#666' }}>
                  📥 Input (Prompt sent to LLM):
                </h4>
                <div style={{ 
                  padding: '12px', 
                  background: 'white', 
                  borderRadius: '4px', 
                  border: '1px solid #e0e0e0',
                  maxHeight: '300px',
                  overflowY: 'auto',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: '1.5'
                }}>
                  {llmData.input || 'No input available'}
                </div>
              </div>
              <div>
                <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: '#666' }}>
                  📤 Output (LLM Response):
                </h4>
                <div style={{ 
                  padding: '12px', 
                  background: 'white', 
                  borderRadius: '4px', 
                  border: '1px solid #e0e0e0',
                  maxHeight: '300px',
                  overflowY: 'auto',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: '1.5'
                }}>
                  {llmData.output || 'No output available'}
                </div>
                {(llmData.assessed_tests_count || llmData.assessedTestsCount) && (
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '8px', fontStyle: 'italic' }}>
                    ✓ Assessed {(llmData.assessed_tests_count || llmData.assessedTestsCount)} tests
                  </div>
                )}
              </div>
            </div>
          );
        })()}

        {/* All Tests Table */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>
            All Tests ({totalTests})
          </h3>
          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
              Loading tests...
            </div>
          ) : (
            <div style={{ 
              maxHeight: '400px', 
              overflowY: 'auto',
              border: '1px solid #e0e0e0',
              borderRadius: '6px'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e0e0e0', background: '#f9f9f9', position: 'sticky', top: 0, zIndex: 10 }}>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Test ID</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Test Name</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Class</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Type</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Match Type</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Similarity</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Score Breakdown</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Confidence</th>
                    <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>LLM</th>
                  </tr>
                </thead>
                <tbody>
                  {allTests.map((test, idx) => {
                    const testId = String(test.test_id);
                    const isSelected = selectedTestIdsSet.has(testId);
                    const selectedTest = selectedTestsMap.get(testId);
                    
                    // Get match type and similarity from selected test if available
                    const matchType = selectedTest?.match_type || (isSelected ? 'Unknown' : '-');
                    const similarity = selectedTest?.similarity;
                    const confidence = selectedTest?.confidence || (isSelected ? 'medium' : '-');
                    const confidenceScore = selectedTest?.confidence_score;
                    const confidenceBreakdown = selectedTest?.confidence_breakdown;
                    const llmScore = selectedTest?.llm_score;
                    const llmExplanation = selectedTest?.llm_explanation;
                    
                    return (
                      <tr 
                        key={idx} 
                        style={{ 
                          borderBottom: '1px solid #f0f0f0',
                          background: isSelected ? '#e8f5e9' : '#ffebee',
                          color: isSelected ? '#1b5e20' : '#c62828'
                        }}
                      >
                        <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>
                          {test.test_id}
                        </td>
                        <td style={{ padding: '8px' }}>
                          {test.method_name || 'N/A'}
                        </td>
                        <td style={{ padding: '8px' }}>
                          {test.class_name || '-'}
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            background: '#e3f2fd',
                            color: '#1976d2'
                          }}>
                            {test.test_type || 'unknown'}
                          </span>
                        </td>
                        <td style={{ padding: '8px' }}>
                          {matchType !== '-' ? (
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              background: matchType === 'Semantic' ? '#f3e5f5' : 
                                         matchType === 'AST' ? '#e8f5e9' : 
                                         matchType === 'Both' ? '#e1bee7' : '#e0e0e0',
                              color: matchType === 'Semantic' ? '#7b1fa2' : 
                                     matchType === 'AST' ? '#2e7d32' : 
                                     matchType === 'Both' ? '#6a1b9a' : '#666'
                            }}>
                              {matchType}
                            </span>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td style={{ padding: '8px' }}>
                          {similarity !== undefined && similarity !== null ? (
                            <span style={{ color: similarity >= 0.6 ? '#2e7d32' : similarity >= 0.4 ? '#f57c00' : '#c62828' }}>
                              {(similarity * 100).toFixed(1)}%
                            </span>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td style={{ padding: '8px', fontSize: '11px', minWidth: '130px' }}>
                          {confidenceBreakdown ? (
                            <div style={{ 
                              display: 'flex', 
                              flexDirection: 'column', 
                              gap: '3px', 
                              padding: '6px', 
                              background: '#f9f9f9', 
                              borderRadius: '4px',
                              border: '1px solid #e0e0e0'
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ color: '#666', fontSize: '10px', fontWeight: '500' }}>AST:</span>
                                <strong style={{ color: '#1976d2', fontSize: '11px' }}>
                                  {(confidenceBreakdown.ast_percentage ?? confidenceBreakdown.astPercentage ?? 0).toFixed(1)}%
                                </strong>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ color: '#666', fontSize: '10px', fontWeight: '500' }}>Semantic:</span>
                                <strong style={{ color: '#7b1fa2', fontSize: '11px' }}>
                                  {(confidenceBreakdown.semantic_percentage ?? confidenceBreakdown.semanticPercentage ?? 0).toFixed(1)}%
                                </strong>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ color: '#666', fontSize: '10px', fontWeight: '500' }}>LLM:</span>
                                <strong style={{ color: '#f57c00', fontSize: '11px' }}>
                                  {(confidenceBreakdown.llm_percentage ?? confidenceBreakdown.llmPercentage ?? 0).toFixed(1)}%
                                </strong>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ color: '#666', fontSize: '10px', fontWeight: '500' }}>Speed:</span>
                                <strong style={{ color: '#666', fontSize: '11px' }}>
                                  {(confidenceBreakdown.speed_percentage ?? confidenceBreakdown.speedPercentage ?? 0).toFixed(1)}%
                                </strong>
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: '#999', fontSize: '10px', fontStyle: 'italic' }}>N/A</span>
                          )}
                        </td>
                        <td style={{ padding: '8px' }}>
                          {confidenceScore !== undefined && confidenceScore !== null ? (
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              background: confidenceScore >= 70 ? '#c8e6c9' : 
                                         confidenceScore >= 50 ? '#fff9c4' : '#ffccbc',
                              color: confidenceScore >= 70 ? '#1b5e20' : 
                                     confidenceScore >= 50 ? '#f57c00' : '#c62828',
                              fontWeight: '500'
                            }}>
                              {confidenceScore}%
                            </span>
                          ) : confidence !== '-' ? (
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              background: confidence === 'high' ? '#c8e6c9' : 
                                         confidence === 'medium' ? '#fff9c4' : '#ffccbc',
                              color: confidence === 'high' ? '#1b5e20' : 
                                     confidence === 'medium' ? '#f57c00' : '#c62828'
                            }}>
                              {confidence}
                            </span>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td style={{ padding: '8px', fontSize: '11px', minWidth: '180px' }}>
                          {llmScore !== undefined && llmScore !== null ? (
                            <div style={{ 
                              display: 'flex', 
                              flexDirection: 'column', 
                              gap: '4px', 
                              padding: '6px',
                              background: '#fff3e0',
                              borderRadius: '4px',
                              border: '1px solid #ffcc80'
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ color: '#666', fontSize: '10px', fontWeight: '500' }}>Score:</span>
                                <strong style={{ 
                                  color: llmScore >= 0.7 ? '#2e7d32' : llmScore >= 0.4 ? '#f57c00' : '#c62828',
                                  fontSize: '12px'
                                }}>
                                  {(llmScore * 100).toFixed(0)}%
                                </strong>
                              </div>
                              {llmExplanation && (
                                <div style={{ 
                                  fontSize: '10px', 
                                  color: '#666', 
                                  fontStyle: 'italic',
                                  padding: '4px',
                                  background: 'white',
                                  borderRadius: '3px',
                                  maxHeight: '50px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  lineHeight: '1.4'
                                }} title={llmExplanation}>
                                  {llmExplanation.length > 60 ? llmExplanation.substring(0, 60) + '...' : llmExplanation}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: '#999', fontSize: '10px', fontStyle: 'italic' }}>N/A</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Close Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '10px 24px',
              background: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TestSummaryModal;
