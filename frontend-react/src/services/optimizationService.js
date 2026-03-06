import api, { apiLong } from './api';

const optimizationService = {
  runOptimization: (data) => apiLong.post('/optimize/run', data),
  getRunStatus: (runId) => api.get(`/optimize/runs/${runId}/status`),
  listRuns: () => api.get('/optimize/runs'),
  deleteRun: (runId) => api.delete(`/optimize/runs/${runId}`),
  getResults: (runId) => api.get(`/optimize/results/${runId}`),
  getKPIs: (runId) => api.get(`/optimize/kpis/${runId}`),
  getExecutiveSummary: (runId) => api.get(`/results/${runId}/executive-summary`),
  getAllocation: (runId, filters = {}) =>
    api.get(`/results/${runId}/allocation`, { params: filters }),
  getInventoryDynamics: (runId, filters = {}) =>
    api.get(`/results/${runId}/inventory-dynamics`, { params: filters }),
  // B3: extended analytics
  getSummaryExtended: (runId) =>
    api.get(`/results/${runId}/summary-extended`),
  getVariables: (runId, filters = {}) =>
    api.get(`/results/${runId}/variables`, { params: filters }),
  getSiSs: (runId, filters = {}) =>
    api.get(`/results/${runId}/si-ss`, { params: filters }),
  getChangesDetail: (runId, filters = {}) =>
    api.get(`/results/${runId}/changes-detail`, { params: filters }),
};

export default optimizationService;
