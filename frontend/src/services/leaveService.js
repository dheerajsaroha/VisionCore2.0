import api from './apiClient';

export const leaveService = {
  getLeaveTypes: (activeOnly = true) =>
    api.get('/leave/types', { params: { active_only: activeOnly } }),

  createLeaveType: (data) =>
    api.post('/leave/types', data),

  updateLeaveType: (typeId, data) =>
    api.put(`/leave/types/${typeId}`, data),

  // ── Organization leave configuration ────────────────────────────────
  /** Starting leave-type sets the organization can adopt. */
  getTemplates: () => api.get('/leave/templates'),

  /**
   * Adopt a template. `replace` re-aligns existing types to the template and
   * deactivates types it does not contain, for moving onto a different
   * region's rules. It never deletes a type.
   */
  applyTemplate: (code, replace = false) =>
    api.post(`/leave/templates/${code}/apply`, null, { params: { replace } }),

  /** The organization's effective leave policy, defaults included. */
  getPolicy: (year) => api.get('/leave/policy', { params: { year } }),

  savePolicy: (data) => api.put('/leave/policy', data),

  // Omit `year` entirely so the server resolves the current leave ledger year
  // rather than pinning the client to a hard-coded one.
  getBalances: (userId = null) =>
    api.get('/leave/balance', { params: { user_id: userId } }),

  getRequests: (params = {}) =>
    api.get('/leave/requests', { params }),

  submitRequest: (data) =>
    api.post('/leave/requests', data),

  approveRequest: (requestId, status, note = '') =>
    api.post(`/leave/requests/${requestId}/approve`, { status, note }),

  cancelRequest: (requestId) =>
    api.post(`/leave/requests/${requestId}/cancel`),
};
