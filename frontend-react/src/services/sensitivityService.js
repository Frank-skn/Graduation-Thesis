import api from './api';

const sensitivityService = {
  runSensitivity: (data) => api.post('/sensitivity/run', data),   // returns {job_id, status}
  runTornado: (data) => api.post('/sensitivity/tornado', data),   // returns {job_id, status}
  pollJob: (jobId) => api.get(`/sensitivity/jobs/${jobId}`),      // returns {status, result?}
  getResults: (sensitivityId) => api.get(`/sensitivity/${sensitivityId}`),
};

export default sensitivityService;
