import api from './apiClient';

const API_BASE = '/succession';

export const successionService = {
  getKeyPositions: () => api.get(`${API_BASE}/key-positions`),
  createKeyPosition: (data) => api.post(`${API_BASE}/key-positions`, data),
  getSuccessionPlans: () => api.get(`${API_BASE}/plans`),
  nominateCandidate: (planId, data) => api.post(`${API_BASE}/plans/${planId}/candidates`, data),
  getNineBoxGrid: () => api.get(`${API_BASE}/nine-box`),
  evaluateNineBox: (data) => api.post(`${API_BASE}/nine-box`, data),
  getCareerPaths: () => api.get(`${API_BASE}/career-paths`),
  createCareerPath: (data) => api.post(`${API_BASE}/career-paths`, data),
  getIDPs: (params) => api.get(`${API_BASE}/idp`, { params }),
  createIDP: (data) => api.post(`${API_BASE}/idp`, data),
  getFlightRisks: () => api.get(`${API_BASE}/flight-risk`),
  assessFlightRisk: (data) => api.post(`${API_BASE}/flight-risk`, data),
  getMentorships: () => api.get(`${API_BASE}/mentorship`),
  createMentorship: (data) => api.post(`${API_BASE}/mentorship`, data),
  getAnalytics: () => api.get(`${API_BASE}/analytics/dashboard`),
};
