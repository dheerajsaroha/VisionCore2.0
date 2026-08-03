/**
 * aiService.js — AI Platform API Client
 * Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
 *
 * Provides API access to:
 * - AI Provider management
 * - Model registry
 * - Prompt management
 * - AI completions
 * - Embeddings
 * - RAG queries
 * - Copilot interactions
 * - Predictive analytics
 * - AI Workflow
 * - AI Governance
 * - Usage & Cost tracking
 */
import apiClient from './apiClient';

const AI_BASE = '/ai';

const aiService = {
  // =========================================================================
  //  Provider Management
  // =========================================================================

  getProviders: async () => {
    const response = await apiClient.get(`${AI_BASE}/providers`);
    return response.data;
  },

  getProvider: async (providerId) => {
    const response = await apiClient.get(`${AI_BASE}/providers/${providerId}`);
    return response.data;
  },

  registerProvider: async (config) => {
    const response = await apiClient.post(`${AI_BASE}/providers`, config);
    return response.data;
  },

  removeProvider: async (providerId) => {
    const response = await apiClient.delete(`${AI_BASE}/providers/${providerId}`);
    return response.data;
  },

  checkProviderHealth: async (providerId) => {
    const response = await apiClient.get(`${AI_BASE}/providers/${providerId}/health`);
    return response.data;
  },

  // =========================================================================
  //  Model Registry
  // =========================================================================

  getModels: async (capability) => {
    const params = capability ? { capability } : {};
    const response = await apiClient.get(`${AI_BASE}/models`, { params });
    return response.data;
  },

  registerModel: async (registration) => {
    const response = await apiClient.post(`${AI_BASE}/models`, registration);
    return response.data;
  },

  getModel: async (modelId) => {
    const response = await apiClient.get(`${AI_BASE}/models/${modelId}`);
    return response.data;
  },

  // =========================================================================
  //  Prompt Management
  // =========================================================================

  getPrompts: async (category) => {
    const params = category ? { category } : {};
    const response = await apiClient.get(`${AI_BASE}/prompts`, { params });
    return response.data;
  },

  registerPrompt: async (template) => {
    const response = await apiClient.post(`${AI_BASE}/prompts`, template);
    return response.data;
  },

  getPrompt: async (promptId) => {
    const response = await apiClient.get(`${AI_BASE}/prompts/${promptId}`);
    return response.data;
  },

  renderPrompt: async (promptId, variables) => {
    const response = await apiClient.post(`${AI_BASE}/prompts/${promptId}/render`, { variables });
    return response.data;
  },

  // =========================================================================
  //  Completions
  // =========================================================================

  complete: async (request) => {
    const response = await apiClient.post(`${AI_BASE}/complete`, request);
    return response.data;
  },

  completeStream: async (request, onChunk) => {
    const response = await fetch(`/ai/complete/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      const lines = text.split('\n').filter(l => l.startsWith('data: '));
      for (const line of lines) {
        try {
          const chunk = JSON.parse(line.slice(6));
          onChunk(chunk);
        } catch {
          // ignore parse errors
        }
      }
    }
  },

  // =========================================================================
  //  Embeddings
  // =========================================================================

  generateEmbedding: async (request) => {
    const response = await apiClient.post(`${AI_BASE}/embeddings`, request);
    return response.data;
  },

  generateEmbeddingsBatch: async (request) => {
    const response = await apiClient.post(`${AI_BASE}/embeddings/batch`, request);
    return response.data;
  },

  // =========================================================================
  //  RAG
  // =========================================================================

  ragQuery: async (query) => {
    const response = await apiClient.post(`${AI_BASE}/rag/query`, query);
    return response.data;
  },

  // =========================================================================
  //  Copilot
  // =========================================================================

  copilotQuery: async (request) => {
    const response = await apiClient.post(`${AI_BASE}/copilot`, request);
    return response.data;
  },

  getCopilotConversations: async (domain) => {
    const params = domain ? { domain } : {};
    const response = await apiClient.get(`${AI_BASE}/copilot/conversations`, { params });
    return response.data;
  },

  getCopilotConversation: async (conversationId) => {
    const response = await apiClient.get(`${AI_BASE}/copilot/conversations/${conversationId}`);
    return response.data;
  },

  // =========================================================================
  //  Predictive Analytics
  // =========================================================================

  predict: async (request) => {
    const response = await apiClient.post(`${AI_BASE}/predict`, request);
    return response.data;
  },

  getForecast: async (modelType, params) => {
    const response = await apiClient.post(`${AI_BASE}/predict/forecast`, {
      model_type: modelType,
      params,
    });
    return response.data;
  },

  // =========================================================================
  //  AI Workflow
  // =========================================================================

  analyzeWorkflowRequest: async (requestId, entityType, payload) => {
    const response = await apiClient.post(`${AI_BASE}/workflow/analyze`, {
      request_id: requestId,
      entity_type: entityType,
      payload,
    });
    return response.data;
  },

  // =========================================================================
  //  AI Governance
  // =========================================================================

  getGovernanceDashboard: async () => {
    const response = await apiClient.get(`${AI_BASE}/governance/dashboard`);
    return response.data;
  },

  getComplianceReport: async (organizationId) => {
    const params = organizationId ? { organization_id: organizationId } : {};
    const response = await apiClient.get(`${AI_BASE}/governance/compliance`, { params });
    return response.data;
  },

  searchAuditTrail: async (filters) => {
    const response = await apiClient.get(`${AI_BASE}/governance/audit`, { params: filters });
    return response.data;
  },

  // =========================================================================
  //  Usage & Cost
  // =========================================================================

  getUsageSummary: async (orgId, periodStart, periodEnd) => {
    const params = {};
    if (orgId) params.organization_id = orgId;
    if (periodStart) params.period_start = periodStart;
    if (periodEnd) params.period_end = periodEnd;
    const response = await apiClient.get(`${AI_BASE}/usage`, { params });
    return response.data;
  },

  getCostAnalytics: async (orgId) => {
    const params = orgId ? { organization_id: orgId } : {};
    const response = await apiClient.get(`${AI_BASE}/usage/costs`, { params });
    return response.data;
  },

  // =========================================================================
  //  Health & Stats
  // =========================================================================

  getAIHealth: async () => {
    const response = await apiClient.get(`${AI_BASE}/health`);
    return response.data;
  },

  getAIStats: async () => {
    const response = await apiClient.get(`${AI_BASE}/stats`);
    return response.data;
  },
};

export default aiService;

