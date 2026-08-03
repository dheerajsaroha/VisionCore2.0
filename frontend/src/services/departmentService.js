import apiClient from './apiClient';

export const departmentService = {
  getDepartments: () => apiClient.get('/org/departments/'),
  getShifts: () => apiClient.get('/org/shifts/'),
};
