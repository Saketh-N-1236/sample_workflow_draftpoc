import React, { useState } from 'react';
import AnalysisStats from './AnalysisStats';
import '../styles/App.css';

const ResultsDisplay = ({ analysisResults, selectionResults }) => {
  const [activeTab, setActiveTab] = useState('all');
  return (
    <div className="details-content">
      {analysisResults && (
        <div>
          <AnalysisStats analysisResults={analysisResults} />
          {analysisResults.status && (
            <div style={{ 
              padding: '12px', 
              background: analysisResults.status === 'completed' ? '#e8f5e9' : '#fff3e0',
              borderRadius: '6px',
              marginTop: '20px',
              textAlign: 'center'
            }}>
              <strong>Status:</strong> {analysisResults.status}
              {analysisResults.message && (
                <div style={{ marginTop: '8px', fontSize: '13px', color: '#666' }}>
                  {analysisResults.message}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {selectionResults && (
        <div className="details-section">
          <div className="section-title">Test Selection Results</div>
          <div className="section-content">
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '20px'
            }}>
              <div style={{ 
                padding: '12px', 
                background: '#f5f5f5', 
                borderRadius: '6px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1976d2' }}>
                  {selectionResults.totalTests || 0}
                </div>
                <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                  Total Tests Selected
                </div>
              </div>
              {selectionResults.astMatches !== undefined && (
                <div style={{ 
                  padding: '12px', 
                  background: '#f5f5f5', 
                  borderRadius: '6px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2e7d32' }}>
                    {selectionResults.astMatches}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                    AST Matches
                  </div>
                </div>
              )}
              {selectionResults.semanticMatches !== undefined && (
                <div style={{ 
                  padding: '12px', 
                  background: '#f5f5f5', 
                  borderRadius: '6px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#7b1fa2' }}>
                    {selectionResults.semanticMatches}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                    Semantic Matches
                  </div>
                </div>
              )}
            </div>
            
            {/* Tabs for filtering by match type */}
            {selectionResults.tests && selectionResults.tests.length > 0 && (
              <div style={{ marginTop: '20px', marginBottom: '16px' }}>
                <div style={{ 
                  display: 'flex', 
                  gap: '8px', 
                  borderBottom: '2px solid #e0e0e0',
                  marginBottom: '16px'
                }}>
                  {['all', 'ast', 'semantic', 'both'].map(tab => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      style={{
                        padding: '8px 16px',
                        background: activeTab === tab ? '#1976d2' : 'transparent',
                        color: activeTab === tab ? 'white' : '#666',
                        border: 'none',
                        borderBottom: activeTab === tab ? '2px solid #1976d2' : '2px solid transparent',
                        cursor: 'pointer',
                        fontSize: '13px',
                        fontWeight: activeTab === tab ? '600' : '400',
                        textTransform: 'capitalize',
                        marginBottom: '-2px'
                      }}
                    >
                      {tab === 'all' ? 'All Tests' : 
                       tab === 'ast' ? 'AST Only' :
                       tab === 'semantic' ? 'Semantic Only' :
                       'Both'}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectionResults.tests && selectionResults.tests.length > 0 ? (
              <div style={{ marginTop: '20px' }}>
                <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: '#333' }}>
                  Selected Tests ({(() => {
                    if (activeTab === 'all') return selectionResults.tests.length;
                    if (activeTab === 'ast') {
                      return selectionResults.tests.filter(t => {
                        // First check explicit flags (most reliable)
                        if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                          return t.is_ast_match === true && t.is_semantic_match === false;
                        }
                        
                        // Fallback: check arrays and properties
                        const testId = String(t.test_id);
                        const astTestIds = new Set((selectionResults.astMatchDetails || []).map(m => String(m.test_id)));
                        const semanticTestIds = new Set((selectionResults.semanticMatchDetails || []).map(m => String(m.test_id)));
                        const inAST = astTestIds.has(testId);
                        const inSemantic = semanticTestIds.has(testId) || (t.similarity && t.similarity > 0);
                        const hasASTIndicators = (
                          (t.match_type && t.match_type !== 'unknown' && t.match_type !== 'semantic') ||
                          (t.matched_classes && t.matched_classes.length > 0)
                        );
                        return (inAST || hasASTIndicators) && !inSemantic;
                      }).length;
                    }
                    if (activeTab === 'semantic') {
                      return selectionResults.tests.filter(t => {
                        // First check explicit flags (most reliable)
                        if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                          return t.is_semantic_match === true && t.is_ast_match === false;
                        }
                        
                        // Fallback: check arrays and properties
                        const testId = String(t.test_id);
                        const semanticTestIds = new Set((selectionResults.semanticMatchDetails || []).map(m => String(m.test_id)));
                        const astTestIds = new Set((selectionResults.astMatchDetails || []).map(m => String(m.test_id)));
                        const inSemantic = semanticTestIds.has(testId) || (t.similarity && t.similarity > 0);
                        const inAST = astTestIds.has(testId) || (
                          (t.match_type && t.match_type !== 'unknown' && t.match_type !== 'semantic') ||
                          (t.matched_classes && t.matched_classes.length > 0)
                        );
                        return inSemantic && !inAST;
                      }).length;
                    }
                    if (activeTab === 'both') {
                      return selectionResults.tests.filter(t => {
                        // First check explicit flags (most reliable)
                        if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                          return t.is_ast_match === true && t.is_semantic_match === true;
                        }
                        
                        // Fallback: check arrays and properties
                        const testId = String(t.test_id);
                        const astTestIds = new Set((selectionResults.astMatchDetails || []).map(m => String(m.test_id)));
                        const semanticTestIds = new Set((selectionResults.semanticMatchDetails || []).map(m => String(m.test_id)));
                        
                        // Check AST indicators (more comprehensive)
                        const inASTDetails = astTestIds.has(testId);
                        const hasASTMatchType = t.match_type && 
                          t.match_type !== 'unknown' && 
                          t.match_type !== 'semantic' &&
                          t.match_type !== '';
                        const hasMatchedClasses = t.matched_classes && t.matched_classes.length > 0;
                        const hasASTIndicators = hasASTMatchType || hasMatchedClasses;
                        const isAST = inASTDetails || hasASTIndicators;
                        
                        // Check semantic indicators (more comprehensive)
                        const inSemanticDetails = semanticTestIds.has(testId);
                        const hasSimilarity = t.similarity && typeof t.similarity === 'number' && t.similarity > 0;
                        const isSemanticMatchType = t.match_type && t.match_type.toLowerCase() === 'semantic';
                        const isSemantic = inSemanticDetails || hasSimilarity || isSemanticMatchType;
                        
                        // Must have BOTH
                        return isAST && isSemantic;
                      }).length;
                    }
                    return selectionResults.tests.length;
                  })()}):
                </div>
                <div style={{ 
                  maxHeight: '400px', 
                  overflowY: 'auto',
                  border: '1px solid #e0e0e0',
                  borderRadius: '6px',
                  padding: '12px'
                }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #e0e0e0', background: '#f9f9f9' }}>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Test ID</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Test Name</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Class</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Type</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Match Type</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Similarity</th>
                        <th style={{ padding: '8px', textAlign: 'left' }}>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        // Filter tests based on active tab
                        let filteredTests = selectionResults.tests;
                        
                        if (activeTab === 'ast') {
                          // Filter: AST matches only (NOT semantic)
                          filteredTests = selectionResults.tests.filter(t => {
                            // First check explicit flags (most reliable)
                            if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                              return t.is_ast_match === true && t.is_semantic_match === false;
                            }
                            
                            // Fallback: check arrays and properties
                            const testId = String(t.test_id);
                            const astTestIds = new Set(
                              (selectionResults.astMatchDetails || []).map(m => String(m.test_id))
                            );
                            const semanticTestIds = new Set(
                              (selectionResults.semanticMatchDetails || []).map(m => String(m.test_id))
                            );
                            const inAST = astTestIds.has(testId);
                            const inSemantic = semanticTestIds.has(testId) || (t.similarity && t.similarity > 0);
                            const hasASTIndicators = (
                              (t.match_type && t.match_type !== 'unknown' && t.match_type !== 'semantic') ||
                              (t.matched_classes && t.matched_classes.length > 0)
                            );
                            return (inAST || hasASTIndicators) && !inSemantic;
                          });
                        } else if (activeTab === 'semantic') {
                          // Filter: semantic matches only (NOT AST)
                          filteredTests = selectionResults.tests.filter(t => {
                            // First check explicit flags (most reliable)
                            if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                              return t.is_semantic_match === true && t.is_ast_match === false;
                            }
                            
                            // Fallback: check arrays and properties
                            const testId = String(t.test_id);
                            const semanticTestIds = new Set(
                              (selectionResults.semanticMatchDetails || []).map(m => String(m.test_id))
                            );
                            const astTestIds = new Set(
                              (selectionResults.astMatchDetails || []).map(m => String(m.test_id))
                            );
                            const inSemantic = semanticTestIds.has(testId) || (t.similarity && t.similarity > 0);
                            const inAST = astTestIds.has(testId) || (
                              (t.match_type && t.match_type !== 'unknown' && t.match_type !== 'semantic') ||
                              (t.matched_classes && t.matched_classes.length > 0)
                            );
                            return inSemantic && !inAST;
                          });
                        } else if (activeTab === 'both') {
                          // Get tests found by both AST and semantic
                          // Use explicit flags if available, otherwise fall back to checking arrays and properties
                          filteredTests = selectionResults.tests.filter(t => {
                            // First check explicit flags (most reliable)
                            if (t.is_ast_match !== undefined && t.is_semantic_match !== undefined) {
                              return t.is_ast_match === true && t.is_semantic_match === true;
                            }
                            
                            // Fallback: check arrays and properties
                            const testId = String(t.test_id);
                            const astTestIds = new Set(
                              (selectionResults.astMatchDetails || []).map(m => String(m.test_id))
                            );
                            const semanticTestIds = new Set(
                              (selectionResults.semanticMatchDetails || []).map(m => String(m.test_id))
                            );
                            
                            // Check AST indicators (more comprehensive)
                            const inASTDetails = astTestIds.has(testId);
                            const hasASTMatchType = t.match_type && 
                              t.match_type !== 'unknown' && 
                              t.match_type !== 'semantic' &&
                              t.match_type !== '';
                            const hasMatchedClasses = t.matched_classes && t.matched_classes.length > 0;
                            const hasASTIndicators = hasASTMatchType || hasMatchedClasses;
                            const isAST = inASTDetails || hasASTIndicators;
                            
                            // Check semantic indicators (more comprehensive)
                            const inSemanticDetails = semanticTestIds.has(testId);
                            const hasSimilarity = t.similarity && typeof t.similarity === 'number' && t.similarity > 0;
                            const isSemanticMatchType = t.match_type && t.match_type.toLowerCase() === 'semantic';
                            const isSemantic = inSemanticDetails || hasSimilarity || isSemanticMatchType;
                            
                            // Must have BOTH
                            return isAST && isSemantic;
                          });
                        }
                        
                        return filteredTests.map((test, idx) => {
                          // Find semantic match details
                          const semanticMatch = (selectionResults.semanticMatchDetails || []).find(
                            m => m.test_id === test.test_id
                          );
                          // Also check test object itself for similarity
                          const similarity = semanticMatch?.similarity || test.similarity;
                          
                          // Determine match type - check both astMatchDetails and test properties
                          // First check astMatchDetails array
                          const inASTDetails = (selectionResults.astMatchDetails || []).some(
                            m => String(m.test_id) === String(test.test_id)
                          );
                          
                          // Also check test properties for AST indicators
                          const hasASTIndicators = (
                            (test.match_type && 
                             test.match_type !== 'unknown' && 
                             test.match_type !== 'semantic') ||
                            (test.matched_classes && test.matched_classes.length > 0)
                          );
                          
                          // AST if in details OR has AST indicators (and not semantic-only)
                          const isAST = inASTDetails || (hasASTIndicators && !(test.similarity && test.similarity > 0));
                          
                          // Semantic if has semantic match OR has similarity score
                          const isSemantic = !!semanticMatch || (test.similarity && test.similarity > 0);
                          const matchTypeLabel = isAST && isSemantic ? 'Both' : 
                                                 isAST ? 'AST' : 
                                                 isSemantic ? 'Semantic' : 'Unknown';
                          
                          return (
                            <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                              <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>
                                {test.test_id}
                              </td>
                              <td style={{ padding: '8px' }}>
                                {test.method_name || 'N/A'}
                              </td>
                              <td style={{ padding: '8px', color: '#666' }}>
                                {test.class_name || '-'}
                              </td>
                              <td style={{ padding: '8px' }}>
                                <span style={{ 
                                  padding: '2px 6px', 
                                  borderRadius: '4px', 
                                  background: test.test_type === 'unit' ? '#e3f2fd' : test.test_type === 'integration' ? '#f3e5f5' : '#fff3e0',
                                  color: test.test_type === 'unit' ? '#1976d2' : test.test_type === 'integration' ? '#7b1fa2' : '#e65100',
                                  fontSize: '11px'
                                }}>
                                  {test.test_type || 'other'}
                                </span>
                              </td>
                              <td style={{ padding: '8px' }}>
                                <span style={{ 
                                  padding: '2px 6px', 
                                  borderRadius: '4px', 
                                  background: matchTypeLabel === 'Both' ? '#e1bee7' : 
                                            matchTypeLabel === 'AST' ? '#c5e1a5' : 
                                            matchTypeLabel === 'Semantic' ? '#b39ddb' : '#e0e0e0',
                                  color: matchTypeLabel === 'Both' ? '#6a1b9a' : 
                                         matchTypeLabel === 'AST' ? '#2e7d32' : 
                                         matchTypeLabel === 'Semantic' ? '#7b1fa2' : '#666',
                                  fontSize: '11px',
                                  fontWeight: '500'
                                }}>
                                  {matchTypeLabel}
                                </span>
                              </td>
                              <td style={{ padding: '8px' }}>
                                {similarity !== undefined && similarity !== null ? (
                                  <span style={{ 
                                    padding: '2px 6px', 
                                    borderRadius: '4px', 
                                    background: similarity >= 0.6 ? '#e8f5e9' : similarity >= 0.4 ? '#fff3e0' : '#ffebee',
                                    color: similarity >= 0.6 ? '#2e7d32' : similarity >= 0.4 ? '#f57c00' : '#c62828',
                                    fontSize: '11px',
                                    fontWeight: '500'
                                  }}>
                                    {(similarity * 100).toFixed(1)}%
                                  </span>
                                ) : (
                                  <span style={{ color: '#999', fontSize: '11px' }}>-</span>
                                )}
                              </td>
                              <td style={{ padding: '8px' }}>
                                <span style={{ 
                                  padding: '2px 6px', 
                                  borderRadius: '4px', 
                                  background: test.confidence === 'high' ? '#e8f5e9' : test.confidence === 'medium' ? '#fff3e0' : '#ffebee',
                                  color: test.confidence === 'high' ? '#2e7d32' : test.confidence === 'medium' ? '#f57c00' : '#c62828',
                                  fontSize: '11px',
                                  fontWeight: '500'
                                }}>
                                  {test.confidence || 'medium'}
                                </span>
                              </td>
                            </tr>
                          );
                        });
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div style={{ marginTop: '20px' }}>
                <div style={{ 
                  padding: '20px', 
                  textAlign: 'center', 
                  color: '#999', 
                  fontStyle: 'italic',
                  background: '#f9f9f9',
                  borderRadius: '6px',
                  marginBottom: '20px'
                }}>
                  No tests selected. The diff may not match any tests in the database, or the changes are in test files themselves.
                </div>
                
                {/* Show diagnostic information if available */}
                {selectionResults.diagnostics && (
                  <div style={{
                    padding: '16px',
                    background: '#f5f5f5',
                    borderRadius: '6px',
                    fontSize: '13px'
                  }}>
                    <div style={{ fontWeight: '600', marginBottom: '12px', color: '#333' }}>
                      Diagnostic Information:
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                      <div>
                        <strong>Parsed Files:</strong> {selectionResults.diagnostics.parsed_files || 0}
                      </div>
                      <div>
                        <strong>Parsed Classes:</strong> {selectionResults.diagnostics.parsed_classes || 0}
                      </div>
                      <div>
                        <strong>Exact Matches Searched:</strong> {selectionResults.diagnostics.search_exact_matches || 0}
                      </div>
                      <div>
                        <strong>Module Matches Searched:</strong> {selectionResults.diagnostics.search_module_matches || 0}
                      </div>
                      {selectionResults.diagnostics.db_reverse_index_count !== undefined && (
                        <div>
                          <strong>DB Reverse Index:</strong> {selectionResults.diagnostics.db_reverse_index_count}
                        </div>
                      )}
                      {selectionResults.diagnostics.db_test_registry_count !== undefined && (
                        <div>
                          <strong>DB Test Registry:</strong> {selectionResults.diagnostics.db_test_registry_count}
                        </div>
                      )}
                    </div>
                    
                    {/* Show search queries if available */}
                    {selectionResults.search_queries && (
                      <div style={{ marginTop: '16px' }}>
                        <div style={{ fontWeight: '600', marginBottom: '8px' }}>
                          Search Queries Used:
                        </div>
                        {selectionResults.search_queries.exact_matches && selectionResults.search_queries.exact_matches.length > 0 && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong>Exact Matches:</strong>
                            <ul style={{ margin: '4px 0 0 20px', padding: 0 }}>
                              {selectionResults.search_queries.exact_matches.slice(0, 5).map((match, idx) => (
                                <li key={idx} style={{ fontSize: '12px', color: '#666' }}>{match}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {selectionResults.search_queries.module_matches && selectionResults.search_queries.module_matches.length > 0 && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong>Module Patterns:</strong>
                            <ul style={{ margin: '4px 0 0 20px', padding: 0 }}>
                              {selectionResults.search_queries.module_matches.slice(0, 5).map((match, idx) => (
                                <li key={idx} style={{ fontSize: '12px', color: '#666' }}>{match}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {selectionResults.search_queries.changed_functions && selectionResults.search_queries.changed_functions.length > 0 && (
                          <div>
                            <strong>Changed Functions:</strong>
                            <ul style={{ margin: '4px 0 0 20px', padding: 0 }}>
                              {selectionResults.search_queries.changed_functions.slice(0, 5).map((func, idx) => (
                                <li key={idx} style={{ fontSize: '12px', color: '#666' }}>{func}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {!analysisResults && !selectionResults && (
        <div className="details-section">
          <div className="section-title">Results</div>
          <div className="section-content" style={{ color: '#999', fontStyle: 'italic' }}>
            No results yet. Run Test Analysis or Test Selection to see results here.
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsDisplay;
