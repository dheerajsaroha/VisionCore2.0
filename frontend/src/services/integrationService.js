// integrationService.js — Enterprise Integration Service
// Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

import apiClient from './apiClient';

class IntegrationService {
  // ===========================================================================
  //  Webhooks
  // ===========================================================================

  async getWebhooks() {
    const response = await apiClient.get('/integration/webhooks');
    return response.data;
  }

  async getWebhook(id) {
    const response = await apiClient.get(`/integration/webhooks/${id}`);
    return response.data;
  }

  async createWebhook(config) {
    const response = await apiClient.post('/integration/webhooks', config);
    return response.data;
  }

  async updateWebhook(id, config) {
    const response = await apiClient.patch(`/integration/webhooks/${id}`, config);
    return response.data;
  }

  async deleteWebhook(id) {
    const response = await apiClient.delete(`/integration/webhooks/${id}`);
    return response.data;
  }

  async getWebhookDeliveries(id, limit = 50) {
    const response = await apiClient.get(`/integration/webhooks/${id}/deliveries`, {
      params: { limit }
    });
    return response.data;
  }

  // ===========================================================================
  //  OAuth2 Clients
  // ===========================================================================

  async getOAuth2Clients() {
    const response = await apiClient.get('/integration/oauth2');
    return response.data;
  }

  async createOAuth2Client(config) {
    const response = await apiClient.post('/integration/oauth2', config);
    return response.data;
  }

  async exchangeOAuth2Token(clientId, code, redirectUri = '') {
    const response = await apiClient.post(`/integration/oauth2/${clientId}/exchange`, null, {
      params: { code, redirect_uri: redirectUri }
    });
    return response.data;
  }

  async refreshOAuth2Token(clientId) {
    const response = await apiClient.post(`/integration/oauth2/${clientId}/refresh`);
    return response.data;
  }

  async deleteOAuth2Client(clientId) {
    const response = await apiClient.delete(`/integration/oauth2/${clientId}`);
    return response.data;
  }

  // ===========================================================================
  //  API Keys
  // ===========================================================================

  async getApiKeys() {
    const response = await apiClient.get('/integration/api-keys');
    return response.data;
  }

  async createApiKey(config) {
    const response = await apiClient.post('/integration/api-keys', config);
    return response.data;
  }

  async revokeApiKey(keyId) {
    const response = await apiClient.post(`/integration/api-keys/${keyId}/revoke`);
    return response.data;
  }

  // ===========================================================================
  //  Connectors
  // ===========================================================================

  async getConnectors() {
    const response = await apiClient.get('/integration/connectors');
    return response.data;
  }

  async createConnector(config) {
    const response = await apiClient.post('/integration/connectors', config);
    return response.data;
  }

  async testConnector(connectorId) {
    const response = await apiClient.post(`/integration/connectors/${connectorId}/test`);
    return response.data;
  }

  async deleteConnector(connectorId) {
    const response = await apiClient.delete(`/integration/connectors/${connectorId}`);
    return response.data;
  }

  // ===========================================================================
  //  Event Dispatch
  // ===========================================================================

  async dispatchEvent(event) {
    const response = await apiClient.post('/integration/events/dispatch', event);
    return response.data;
  }

  async getAvailableEvents() {
    const response = await apiClient.get('/integration/events/available');
    return response.data;
  }

  // ===========================================================================
  //  Dead Letter Queue
  // ===========================================================================

  async getDeadLetterQueue(limit = 50) {
    const response = await apiClient.get('/integration/dead-letter', {
      params: { limit }
    });
    return response.data;
  }

  async retryDeadLetter(deliveryId) {
    const response = await apiClient.post(`/integration/dead-letter/${deliveryId}/retry`);
    return response.data;
  }

  async clearDeadLetterQueue() {
    const response = await apiClient.delete('/integration/dead-letter');
    return response.data;
  }

  // ===========================================================================
  //  Summary
  // ===========================================================================

  async getSummary() {
    const response = await apiClient.get('/integration/summary');
    return response.data;
  }
}

export const integrationService = new IntegrationService();
export default integrationService;

