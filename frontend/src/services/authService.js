import apiClient from './apiClient';

export const authService = {
  login: (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    return apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },

  register: (data) => apiClient.post('/auth/register', data),

  logout: (token) =>
    apiClient.post('/auth/logout', null, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  refreshToken: () => apiClient.post('/auth/refresh'),

  getMe: (token) =>
    apiClient.get('/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    }),

  forgotPassword: (email) => apiClient.post('/auth/forgot-password', { email }),

  resetPassword: (token, newPassword) =>
    apiClient.post('/auth/reset-password', { token, new_password: newPassword }),
};
