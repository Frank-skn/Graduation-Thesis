import api from './api';

const sensitivityService = {
  runSensitivity: (data) => api.post('/sensitivity/run', data),
  getResults: (sensitivityId) => api.get(`/sensitivity/${sensitivityId}`),
  runTornado: (data) => api.post('/sensitivity/tornado', data),
};

export default sensitivityService;
