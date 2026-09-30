import apiClient from './apiClient';

export const departmentService = {
  /**
   * `config` is forwarded to axios. Callers that expect a permission denial
   * should pass `{ suppressForbiddenToast: true }` so an expected 403 does not
   * surface as an error notification.
   */
  getDepartments: (config) => apiClient.get('/org/departments/', config),
  getShifts: (config) => apiClient.get('/org/shifts/', config),
};
