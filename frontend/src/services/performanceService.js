import api from './apiClient';

const API_BASE = '/performance';

export const performanceService = {
  // Cycles
  getCycles: (params) => api.get(`${API_BASE}/cycles`, { params }),
  createCycle: (data) => api.post(`${API_BASE}/cycles`, data),

  // Competencies
  getCompetencies: () => api.get(`${API_BASE}/competencies`),
  createCompetency: (data) => api.post(`${API_BASE}/competencies`, data),

  // KPIs
  getKPIs: () => api.get(`${API_BASE}/kpis`),
  createKPI: (data) => api.post(`${API_BASE}/kpis`, data),
  assignKPI: (data) => api.post(`${API_BASE}/kpis/assign`, data),
  getKPIAssignments: (params) => api.get(`${API_BASE}/kpis/assignments`, { params }),
  updateKPIAssignmentProgress: (id, actualValue) => api.patch(`${API_BASE}/kpis/assignments/${id}`, { actual_value: actualValue }),

  // Goals
  getGoals: (params) => api.get(`${API_BASE}/goals`, { params }),
  createGoal: (data) => api.post(`${API_BASE}/goals`, data),
  logGoalProgress: (id, value, note) => api.post(`${API_BASE}/goals/${id}/progress`, { value, note }),

  // Reviews
  getReviews: (params) => api.get(`${API_BASE}/reviews`, { params }),
  createReview: (data) => api.post(`${API_BASE}/reviews`, data),
  submitReview: (id, data) => api.post(`${API_BASE}/reviews/${id}/submit`, data),

  // Feedback
  getFeedback: (params) => api.get(`${API_BASE}/feedback`, { params }),
  submitFeedback: (data) => api.post(`${API_BASE}/feedback`, data),

  // PIPs
  getPIPs: (params) => api.get(`${API_BASE}/pips`, { params }),
  createPIP: (data) => api.post(`${API_BASE}/pips`, data),

  // Promotions
  getPromotions: () => api.get(`${API_BASE}/promotions`),
  createPromotion: (data) => api.post(`${API_BASE}/promotions`, data),
  actOnPromotion: (id, status, decisionNotes) => api.post(`${API_BASE}/promotions/${id}/action`, { status, decision_notes: decisionNotes }),

  // Analytics
  getAnalytics: (params) => api.get(`${API_BASE}/analytics/dashboard`, { params }),
};
