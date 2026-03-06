import api from './api';

const insightsService = {
  getInsights: (runId) => api.get(`/insights/${runId}`),
  generateInsights: (data) => api.post('/insights/', data),
};

export default insightsService;
