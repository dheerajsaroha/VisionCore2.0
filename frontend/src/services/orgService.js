import apiClient from './apiClient';

export const orgService = {
  getCurrentOrganization: async () => {
    const response = await apiClient.get('/org/current');
    return response.data;
  },
  updateOrganization: async (data) => {
    const response = await apiClient.put('/org/', data);
    return response.data;
  },
  getApiKeys: async () => {
    const response = await apiClient.get('/org/api-keys');
    return response.data;
  },
  createApiKey: async (data) => {
    const response = await apiClient.post('/org/api-keys', data);
    return response.data;
  },
  revokeApiKey: async (id) => {
    const response = await apiClient.delete(`/org/api-keys/${id}`);
    return response.data;
  }
};
