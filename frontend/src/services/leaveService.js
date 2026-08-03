import api from './apiClient';

export const leaveService = {
  getLeaveTypes: (activeOnly = true) =>
    api.get('/leave/types', { params: { active_only: activeOnly } }),

  createLeaveType: (data) =>
    api.post('/leave/types', data),

  updateLeaveType: (typeId, data) =>
    api.put(`/leave/types/${typeId}`, data),

  getBalances: (userId = null, year = 2025) =>
    api.get('/leave/balance', { params: { user_id: userId, year } }),

  getRequests: (params = {}) =>
    api.get('/leave/requests', { params }),

  submitRequest: (data) =>
    api.post('/leave/requests', data),

  approveRequest: (requestId, status, note = '') =>
    api.post(`/leave/requests/${requestId}/approve`, { status, note }),

  cancelRequest: (requestId) =>
    api.post(`/leave/requests/${requestId}/cancel`),
};
