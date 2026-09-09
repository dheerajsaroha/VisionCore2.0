import apiClient from './apiClient';

export const notificationService = {
  getNotifications: (params = {}) =>
    apiClient.get('/notifications', { params }),

  getUnreadCount: () =>
    apiClient.get('/notifications/unread-count'),

  markRead: (notificationId) =>
    apiClient.patch(`/notifications/${notificationId}/read`),

  markAllRead: () =>
    apiClient.patch('/notifications/read-all'),

  dismiss: (notificationId) =>
    apiClient.delete(`/notifications/${notificationId}`),
};
