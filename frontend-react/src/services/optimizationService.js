import api from './api';

const optimizationService = {
  runOptimization: (data) => api.post('/optimize/run', data),
  getResults: (runId) => api.get(`/optimize/results/${runId}`),
  getKPIs: (runId) => api.get(`/optimize/kpis/${runId}`),
  getExecutiveSummary: (runId) => api.get(`/results/${runId}/executive-summary`),
  getAllocation: (runId, filters = {}) =>
    api.get(`/results/${runId}/allocation`, { params: filters }),
  getInventoryDynamics: (runId, filters = {}) =>
    api.get(`/results/${runId}/inventory-dynamics`, { params: filters }),
};

export default optimizationService;
