import apiClient from './apiClient';

export const userService = {
  getUsers: (params = {}) => apiClient.get('/users/', { params }),

  createUser: (data) => apiClient.post('/users/', data),

  getUserById: (id) => apiClient.get(`/users/${id}`),

  updateUser: (id, data) => apiClient.patch(`/users/${id}`, data),

  updateMyProfile: (data) => apiClient.patch('/users/me', data),


  deleteUser: (id) => apiClient.delete(`/users/${id}`),

  enrollFace: async (userId, fileOrEmbedding) => {
    if (fileOrEmbedding instanceof File) {
      const formData = new FormData();
      formData.append("file", fileOrEmbedding);
      return apiClient.post(`/users/${userId}/enroll-face`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    }
    return apiClient.post(`/users/${userId}/enroll`, { face_embedding: fileOrEmbedding });
  },
};
