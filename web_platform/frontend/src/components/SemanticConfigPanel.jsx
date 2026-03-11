import React, { useState, useEffect } from 'react';
import api from '../services/api';
import '../styles/App.css';

const SemanticConfigPanel = ({ repoId, onSave, onCancel }) => {
  const [config, setConfig] = useState({
    similarity_threshold: null,
    max_results: 10000,  // High limit to effectively remove upper bound
    use_adaptive_thresholds: true,
    use_multi_query: false,
    top_k: null,
    top_p: null,
    // Advanced RAG settings
    use_advanced_rag: true,
    use_query_rewriting: true,
    use_llm_reranking: true,
    rerank_top_k: 50,
    num_query_variations: 3,
    quality_threshold: 0.4
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(true);

  // Load saved configuration on mount
  useEffect(() => {
    const loadConfig = async () => {
      if (!repoId) {
        setLoadingConfig(false);
        return;
      }

      try {
        setLoadingConfig(true);
        const response = await api.getSemanticConfig(repoId);
        if (response.data) {
          setConfig({
            similarity_threshold: response.data.similarity_threshold ?? null,
            max_results: response.data.max_results ?? 10000,
            use_adaptive_thresholds: response.data.use_adaptive_thresholds ?? true,
            use_multi_query: response.data.use_multi_query ?? false,
            top_k: response.data.top_k ?? null,
            top_p: response.data.top_p ?? null,
            use_advanced_rag: response.data.use_advanced_rag ?? true,
            use_query_rewriting: response.data.use_query_rewriting ?? true,
            use_llm_reranking: response.data.use_llm_reranking ?? true,
            rerank_top_k: response.data.rerank_top_k ?? 50,
            num_query_variations: response.data.num_query_variations ?? 3,
            quality_threshold: response.data.quality_threshold ?? 0.4
          });
        }
      } catch (err) {
        console.error('Failed to load semantic config:', err);
        // Use defaults if loading fails
      } finally {
        setLoadingConfig(false);
      }
    };

    loadConfig();
  }, [repoId]);

  const handleThresholdChange = (e) => {
    const value = e.target.value;
    setConfig({
      ...config,
      similarity_threshold: value === '' ? null : parseFloat(value)
    });
  };

  const handleMaxResultsChange = (e) => {
    setConfig({
      ...config,
      max_results: parseInt(e.target.value) || 10000
    });
  };

  const handleToggle = (field) => {
    setConfig({
      ...config,
      [field]: !config[field]
    });
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      // Validate
      if (config.similarity_threshold !== null) {
        if (config.similarity_threshold < 0 || config.similarity_threshold > 1) {
          setError('Similarity threshold must be between 0.0 and 1.0');
          setLoading(false);
          return;
        }
      }

        if (config.max_results < 1) {
          setError('Max results must be at least 1');
          setLoading(false);
          return;
        }

        if (config.top_k !== null && config.top_k < 1) {
          setError('Top K must be at least 1');
          setLoading(false);
          return;
        }

        if (config.top_p !== null) {
          if (config.top_p < 0 || config.top_p > 1) {
            setError('Top P must be between 0.0 and 1.0');
            setLoading(false);
            return;
          }
        }

        if (config.rerank_top_k < 1) {
          setError('Re-rank Top K must be at least 1');
          setLoading(false);
          return;
        }

        if (config.num_query_variations < 1) {
          setError('Query Variations must be at least 1');
          setLoading(false);
          return;
        }

        if (config.quality_threshold !== undefined) {
          if (config.quality_threshold < 0 || config.quality_threshold > 1) {
            setError('Quality Threshold must be between 0.0 and 1.0');
            setLoading(false);
            return;
          }
        }

      if (repoId) {
        await api.configureSemanticSearch(repoId, config);
      }

      setSuccess(true);
      setTimeout(() => {
        if (onSave) {
          onSave(config);
        }
      }, 1000);
    } catch (err) {
      console.error('Failed to save semantic config:', err);
      setError(err.response?.data?.detail || 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setConfig({
      similarity_threshold: null,
      max_results: 10000,
      use_adaptive_thresholds: true,
      use_multi_query: false,
      top_k: null,
      top_p: null,
      use_advanced_rag: true,
      use_query_rewriting: true,
      use_llm_reranking: true,
      rerank_top_k: 50,
      num_query_variations: 3,
      quality_threshold: 0.4
    });
    setError(null);
    setSuccess(false);
  };

  const handleNumberChange = (field) => (e) => {
    const value = e.target.value;
    setConfig({
      ...config,
      [field]: value === '' ? (field === 'rerank_top_k' ? 50 : 3) : parseInt(value) || (field === 'rerank_top_k' ? 50 : 3)
    });
  };

  return (
    <div style={{ 
      padding: '20px', 
      background: 'white', 
      borderRadius: '8px', 
      border: '1px solid #e0e0e0'
    }}>
      <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', fontWeight: '600' }}>
        Semantic Search Configuration
      </h3>

      {error && (
        <div style={{ 
          padding: '12px', 
          background: '#ffebee', 
          borderRadius: '4px',
          marginBottom: '16px',
          color: '#f44336',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{ 
          padding: '12px', 
          background: '#e8f5e9', 
          borderRadius: '4px',
          marginBottom: '16px',
          color: '#2e7d32',
          fontSize: '14px'
        }}>
          Configuration saved successfully!
        </div>
      )}

      <div style={{ marginBottom: '20px' }}>
        <label style={{ 
          display: 'block', 
          marginBottom: '8px', 
          fontSize: '14px', 
          fontWeight: '500' 
        }}>
          Similarity Threshold
          <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
            {config.use_advanced_rag 
              ? '(0.3 - 0.7, initial filter for vector search)'
              : '(0.3 - 0.7, leave empty for adaptive)'
            }
          </span>
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.1"
          value={config.similarity_threshold === null ? '' : config.similarity_threshold}
          onChange={handleThresholdChange}
          placeholder="Auto (adaptive thresholds)"
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
          {config.use_advanced_rag 
            ? (config.similarity_threshold === null 
                ? 'Using default threshold (0.5) as initial filter. Final filtering uses Quality Threshold.'
                : `Initial filter: ${config.similarity_threshold}. Final filtering uses Quality Threshold.`)
            : (config.similarity_threshold === null 
                ? 'Using adaptive thresholds (strict → moderate → lenient)'
                : `Fixed threshold: ${config.similarity_threshold}`)
          }
        </div>
      </div>

      {!config.use_advanced_rag && (
        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontSize: '14px', 
            fontWeight: '500' 
          }}>
            Max Results
          </label>
          <input
            type="number"
            min="1"
            value={config.max_results}
            onChange={handleMaxResultsChange}
            placeholder="10000 (no limit)"
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          />
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            Set to 10000 or higher to effectively remove limits
          </div>
        </div>
      )}
      

      {!config.use_advanced_rag && (
        <>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              cursor: 'pointer',
              fontSize: '14px'
            }}>
              <input
                type="checkbox"
                checked={config.use_adaptive_thresholds}
                onChange={() => handleToggle('use_adaptive_thresholds')}
                style={{ marginRight: '8px' }}
              />
              Use Adaptive Thresholds
              <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
                (Try multiple thresholds for better coverage)
              </span>
            </label>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              cursor: 'pointer',
              fontSize: '14px'
            }}>
              <input
                type="checkbox"
                checked={config.use_multi_query}
                onChange={() => handleToggle('use_multi_query')}
                style={{ marginRight: '8px' }}
              />
              Use Multi-Query Search
              <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
                (Generate multiple query variations)
              </span>
            </label>
          </div>
        </>
      )}


      <div style={{ 
        marginTop: '24px', 
        paddingTop: '20px', 
        borderTop: '2px solid #e0e0e0' 
      }}>
        <h4 style={{ 
          margin: '0 0 16px 0', 
          fontSize: '16px', 
          fontWeight: '600',
          color: '#1976d2'
        }}>
          Advanced RAG Settings
        </h4>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            cursor: 'pointer',
            fontSize: '14px'
          }}>
            <input
              type="checkbox"
              checked={config.use_advanced_rag}
              onChange={() => handleToggle('use_advanced_rag')}
              style={{ marginRight: '8px' }}
            />
            Use Advanced RAG
            <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
              (Enable LLM-powered query understanding, rewriting, and re-ranking)
            </span>
          </label>
        </div>

        {config.use_advanced_rag && (
          <>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'flex', 
                alignItems: 'center', 
                cursor: 'pointer',
                fontSize: '14px'
              }}>
                <input
                  type="checkbox"
                  checked={config.use_query_rewriting}
                  onChange={() => handleToggle('use_query_rewriting')}
                  style={{ marginRight: '8px' }}
                />
                Use Query Rewriting
                <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
                  (Generate multiple query variations with LLM)
                </span>
              </label>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'flex', 
                alignItems: 'center', 
                cursor: 'pointer',
                fontSize: '14px'
              }}>
                <input
                  type="checkbox"
                  checked={config.use_llm_reranking}
                  onChange={() => handleToggle('use_llm_reranking')}
                  style={{ marginRight: '8px' }}
                />
                Use LLM Re-ranking
                <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px', fontWeight: 'normal' }}>
                  (Re-rank results using LLM relevance assessment)
                </span>
              </label>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                fontSize: '14px', 
                fontWeight: '500' 
              }}>
                Re-rank Top K
                <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
                  (Number of candidates to re-rank)
                </span>
              </label>
              <input
                type="number"
                min="1"
                value={config.rerank_top_k}
                onChange={handleNumberChange('rerank_top_k')}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                fontSize: '14px', 
                fontWeight: '500' 
              }}>
                Query Variations
                <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
                  (Number of query variations to generate)
                </span>
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={config.num_query_variations}
                onChange={handleNumberChange('num_query_variations')}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              />
            </div>

            {config.use_llm_reranking && (
              <div style={{ marginBottom: '20px' }}>
                <label style={{ 
                  display: 'block', 
                  marginBottom: '8px', 
                  fontSize: '14px', 
                  fontWeight: '500' 
                }}>
                  Quality Threshold
                  <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal', marginLeft: '8px' }}>
                    (Minimum relevance score: 0.0 - 1.0)
                  </span>
                </label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={config.quality_threshold}
                  onChange={(e) => {
                    const value = parseFloat(e.target.value) || 0.4;
                    setConfig({
                      ...config,
                      quality_threshold: Math.max(0, Math.min(1, value))
                    });
                  }}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    fontSize: '14px'
                  }}
                />
                <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                  Only tests with LLM relevance score ≥ {config.quality_threshold} will be returned. 
                  Lower = more tests, Higher = fewer but more relevant tests.
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div style={{ 
        display: 'flex', 
        gap: '12px', 
        justifyContent: 'flex-end',
        paddingTop: '16px',
        borderTop: '1px solid #e0e0e0'
      }}>
        <button
          onClick={handleReset}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: 'transparent',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px'
          }}
        >
          Reset
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={loading}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px'
            }}
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleSave}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: loading ? '#ccc' : '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500'
          }}
        >
          {loading ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
};

export default SemanticConfigPanel;
