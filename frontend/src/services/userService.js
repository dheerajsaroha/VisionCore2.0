import apiClient from './apiClient';

export const userService = {
  getUsers: (params = {}) => apiClient.get('/users/', { params }),

  createUser: (data) => apiClient.post('/users/', data),

  getUserById: (id) => apiClient.get(`/users/${id}`),

  updateUser: (id, data) => apiClient.patch(`/users/${id}`, data),

  deleteUser: (id) => apiClient.delete(`/users/${id}`),

  enrollFace: (userId, faceEmbedding) =>
    apiClient.post(`/users/${userId}/enroll`, { face_embedding: faceEmbedding }),
};
