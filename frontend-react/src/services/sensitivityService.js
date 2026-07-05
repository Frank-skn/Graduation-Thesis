import api from './api';

const sensitivityService = {
  runSensitivity: (data) => api.post('/sensitivity/run', data),   // returns {job_id, status}
  runTornado: (data) => api.post('/sensitivity/tornado', data),   // returns {job_id, status}
  pollJob: (jobId) => api.get(`/sensitivity/jobs/${jobId}`),      // returns {status, result?}
  cancelJob: (jobId) => api.post(`/sensitivity/jobs/${jobId}/cancel`),
  getResults: (sensitivityId) => api.get(`/sensitivity/${sensitivityId}`),
  // History of past jobs (for D2/D3 resume after navigating away)
  getHistory: (params = {}) => api.get('/sensitivity/history', { params }),
};

export default sensitivityService;
