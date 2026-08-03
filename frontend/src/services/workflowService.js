/**
 * workflowService.js — Enterprise Approval Workflow API Service
 * Sprint 2 — Entity 4
 */
import api from './apiClient';

export const workflowService = {
  // Workflows
  getWorkflows: async (params = {}) => {
    const res = await api.get('/workflow/workflows', { params });
    return res.data;
  },

  getWorkflow: async (id) => {
    const res = await api.get(`/workflow/workflows/${id}`);
    return res.data;
  },

  createWorkflow: async (data) => {
    const res = await api.post('/workflow/workflows', data);
    return res.data;
  },

  updateWorkflow: async (id, data) => {
    const res = await api.put(`/workflow/workflows/${id}`, data);
    return res.data;
  },

  deleteWorkflow: async (id) => {
    const res = await api.delete(`/workflow/workflows/${id}`);
    return res.data;
  },

  // Stages
  getStages: async (workflowId) => {
    const res = await api.get(`/workflow/workflows/${workflowId}/stages`);
    return res.data;
  },

  createStage: async (workflowId, data) => {
    const res = await api.post(`/workflow/workflows/${workflowId}/stages`, data);
    return res.data;
  },

  updateStage: async (workflowId, stageId, data) => {
    const res = await api.put(`/workflow/workflows/${workflowId}/stages/${stageId}`, data);
    return res.data;
  },

  deleteStage: async (workflowId, stageId) => {
    const res = await api.delete(`/workflow/workflows/${workflowId}/stages/${stageId}`);
    return res.data;
  },

  // Requests
  getRequests: async (params = {}) => {
    const res = await api.get('/workflow/requests', { params });
    return res.data;
  },

  getRequest: async (id) => {
    const res = await api.get(`/workflow/requests/${id}`);
    return res.data;
  },

  submitRequest: async (data) => {
    const res = await api.post('/workflow/requests', data);
    return res.data;
  },

  processAction: async (requestId, data) => {
    const res = await api.post(`/workflow/requests/${requestId}/action`, data);
    return res.data;
  },

  getPendingApprovals: async () => {
    const res = await api.get('/workflow/requests/pending');
    return res.data;
  },

  // Delegations
  getDelegations: async () => {
    const res = await api.get('/workflow/delegations');
    return res.data;
  },

  createDelegation: async (data) => {
    const res = await api.post('/workflow/delegations', data);
    return res.data;
  },

// SLA
  checkSLA: async () => {
    const res = await api.post('/workflow/sla/check');
    return res.data;
  },

  // Additional methods used by ApprovalWorkflowPage
  getPendingQueue: async () => {
    const res = await api.get('/workflow/requests/pending');
    return res.data;
  },

  getMyRequests: async () => {
    const res = await api.get('/workflow/requests', { params: { my: true } });
    return res.data;
  },

  getTemplates: async () => {
    const res = await api.get('/workflow/templates');
    return res.data;
  },

  getAnalytics: async () => {
    const res = await api.get('/workflow/analytics');
    return res.data;
  },

  executeAction: async (requestId, data) => {
    const res = await api.post(`/workflow/requests/${requestId}/action`, data);
    return res.data;
  },

  seedWorkflows: async () => {
    const res = await api.post('/workflow/seed');
    return res.data;
  },
};

export default workflowService;
