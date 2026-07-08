import api from './api';

const dataService = {
  getOverview: () => api.get('/data-overview/'),
  getParameters: () => api.get('/data-overview/parameters'),
  updateParameter: (paramName, paramValue) =>
    api.put(`/data-overview/parameters/${paramName}`, { param_value: paramValue }),
  getDatasets: (limit = 50) => api.get('/data-overview/datasets', { params: { limit } }),
  createDataset: (data) => api.post('/data-overview/datasets', data),
  getAlgorithmParameters: () => api.get('/data-overview/algorithm-parameters'),
  getCostParameters: () => api.get('/data-overview/cost-parameters'),
  getRunsForVersion: (versionId) => api.get(`/data-overview/datasets/${versionId}/runs`),
};

export default dataService;
