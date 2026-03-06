import api from './api';

const scenarioService = {
  createScenario: (data) => api.post('/scenarios/', data),
  getScenarios: (limit = 50) => api.get('/scenarios/', { params: { limit } }),
  getScenario: (scenarioId) => api.get(`/scenarios/${scenarioId}`),
  deleteScenario: (scenarioId) => api.delete(`/scenarios/${scenarioId}`),
  getWhatIfTemplates: () => api.get('/whatif/templates'),
  createWhatIf: (data) => api.post('/whatif/', data),
  compareWhatIf: (baseRunId, compareRunId) =>
    api.get('/whatif/compare', { params: { base_run_id: baseRunId, compare_run_id: compareRunId } }),
};

export default scenarioService;
