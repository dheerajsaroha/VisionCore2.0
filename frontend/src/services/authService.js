import apiClient from './apiClient';

export const authService = {
  /**
   * `organization` is optional. The backend only needs it when one email has
   * accounts in more than one organisation and the same password works for
   * both, in which case it answers 409 with the list of organisations. Leaving
   * it undefined is the normal path.
   */
  login: (email, password, organization) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    if (organization) formData.append('organization', organization);

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

  // Accepts either credential. `token` is the emailed link; `email`+`code` is
  // the 6-digit alternative, for people who cannot follow a link (a
  // phone-only mailbox, a stripped HTML message, a mail client that rewrites
  // URLs). The backend treats both as the same single-use credential.
  resetPassword: ({ token, email, code, newPassword }) =>
    apiClient.post('/auth/reset-password', {
      token: token || undefined,
      email: email || undefined,
      otp: code || undefined,
      new_password: newPassword,
    }),

  // Revokes every active session and blacklists the current token, so the
  // caller is signed out afterwards.
  changePassword: (currentPassword, newPassword) =>
    apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};
