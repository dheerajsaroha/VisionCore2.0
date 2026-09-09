import apiClient from './apiClient';

export const attendanceService = {
  getLogs: (params = {}) => apiClient.get('/attendance/logs', { params }),

  checkIn: (data) => apiClient.post('/attendance/check-in', data),
  checkOut: (data = {}) => apiClient.post('/attendance/check-out', data),


  getWellnessHeatmap: () => apiClient.get('/attendance/wellness-heatmap'),

  getProductivityReport: () => apiClient.get('/attendance/productivity-report'),

  // Per-user monthly summary used in EmployeeDetailModal
  getAttendanceSummary: (params = {}) =>
    apiClient.get('/attendance/summary', { params }).catch(() => ({ data: null })),
};
