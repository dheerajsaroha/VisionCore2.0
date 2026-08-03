/**
 * scopeService.js — Enterprise Data Scope & Resource Ownership API Service
 */
import api from './apiClient';

export const scopeService = {
  getDataScopes: async (params = {}) => {
    const res = await api.get('/scope/data-scopes', { params });
    return res.data;
  },
  createDataScope: async (payload) => {
    const res = await api.post('/scope/data-scopes', payload);
    return res.data;
  },
  getRoleDataScopes: async (params = {}) => {
    const res = await api.get('/scope/role-data-scopes', { params });
    return res.data;
  },
  createRoleDataScope: async (payload) => {
    const res = await api.post('/scope/role-data-scopes', payload);
    return res.data;
  },
  deleteRoleDataScope: async (id) => {
    const res = await api.delete(`/scope/role-data-scopes/${id}`);
    return res.data;
  },
  getOwnerships: async (params = {}) => {
    const res = await api.get('/scope/ownerships', { params });
    return res.data;
  },
  assignOwnership: async (payload) => {
    const res = await api.post('/scope/ownerships', payload);
    return res.data;
  },
  transferOwnership: async (payload) => {
    const res = await api.post('/scope/ownerships/transfer', payload);
    return res.data;
  },
  getOwnershipHistory: async (params = {}) => {
    const res = await api.get('/scope/ownerships/history', { params });
    return res.data;
  },
  getDelegations: async (params = {}) => {
    const res = await api.get('/scope/delegations', { params });
    return res.data;
  },
  createDelegation: async (payload) => {
    const res = await api.post('/scope/delegations', payload);
    return res.data;
  },
  getRules: async () => {
    const res = await api.get('/scope/rules');
    return res.data;
  },
  createRule: async (payload) => {
    const res = await api.post('/scope/rules', payload);
    return res.data;
  },
  getPolicies: async () => {
    const res = await api.get('/scope/policies');
    return res.data;
  },
  getEffectiveScope: async (permission) => {
    const res = await api.get('/scope/effective-scope', { params: { permission } });
    return res.data;
  },
  inspectAuthorization: async (payload) => {
    const res = await api.post('/scope/inspect', payload);
    return res.data;
  },
  seedData: async () => {
    const res = await api.post('/scope/seed');
    return res.data;
  },
};

export default scopeService;
