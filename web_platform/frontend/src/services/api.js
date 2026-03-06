import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  listRepositories: () => {
    return api.get('/repositories');
  },

  getRepository: (repoId) => {
    return api.get(`/repositories/${repoId}`);
  },

  connectRepository: (data) => {
    // data can be a string (backward compatibility) or object with url and provider
    const requestData = typeof data === 'string' 
      ? { url: data }
      : data;
    return api.post('/repositories/connect', requestData);
  },

  refreshRepository: (repoId) => {
    return api.post(`/repositories/${repoId}/refresh`);
  },

  updateRepository: (repoId, data) => {
    return api.put(`/repositories/${repoId}`, data);
  },

  listBranches: (repoId) => {
    return api.get(`/repositories/${repoId}/branches`);
  },

  getDiff: (repoId) => {
    return api.get(`/repositories/${repoId}/diff`);
  },

  runAnalysis: (repoId) => {
    return api.post(`/repositories/${repoId}/analyze`);
  },

  getAnalysisStatus: (repoId) => {
    return api.get(`/repositories/${repoId}/analysis/status`);
  },

  selectTests: (repoId) => {
    return api.post(`/repositories/${repoId}/select-tests`);
  },

  getResults: (repoId) => {
    return api.get(`/repositories/${repoId}/results`);
  },

  // Analysis Results
  getAnalysisResults: () => {
    return api.get('/analysis/results');
  },

  refreshAnalysis: () => {
    return api.post('/analysis/refresh');
  },

  // Semantic Retrieval
  getEmbeddingStatus: () => {
    return api.get('/analysis/embedding-status');
  },

  configureSemanticSearch: (repoId, config) => {
    return api.post(`/repositories/${repoId}/configure-semantic`, config);
  },

  getTotalTestsCount: () => {
    return api.get('/analysis/total-tests');
  },

  getAllTests: () => {
    return api.get('/analysis/all-tests');
  },

  // Risk Analysis
  updateRiskThreshold: (repoId, threshold) => {
    return api.patch(`/repositories/${repoId}/threshold`, { threshold });
  },

  getRiskThreshold: (repoId) => {
    return api.get(`/repositories/${repoId}`);
  },
};
