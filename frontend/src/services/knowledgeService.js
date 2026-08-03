/**
 * knowledgeService.js — Knowledge Platform API Client
 * Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
 *
 * Provides API access to:
 * - Knowledge collections management
 * - Document ingestion
 * - Knowledge search
 * - Document management
 */
import apiClient from './apiClient';

const KB_BASE = '/knowledge';

const knowledgeService = {
  // =========================================================================
  //  Collections
  // =========================================================================

  getCollections: async () => {
    const response = await apiClient.get(`${KB_BASE}/collections`);
    return response.data;
  },

  getCollection: async (collectionId) => {
    const response = await apiClient.get(`${KB_BASE}/collections/${collectionId}`);
    return response.data;
  },

  createCollection: async (data) => {
    const response = await apiClient.post(`${KB_BASE}/collections`, data);
    return response.data;
  },

  deleteCollection: async (collectionId) => {
    const response = await apiClient.delete(`${KB_BASE}/collections/${collectionId}`);
    return response.data;
  },

  // =========================================================================
  //  Documents
  // =========================================================================

  getDocuments: async (collectionId, params) => {
    const queryParams = { collection: collectionId, ...params };
    const response = await apiClient.get(`${KB_BASE}/documents`, { params: queryParams });
    return response.data;
  },

  getDocument: async (documentId) => {
    const response = await apiClient.get(`${KB_BASE}/documents/${documentId}`);
    return response.data;
  },

  ingestDocument: async (formData) => {
    const response = await apiClient.post(`${KB_BASE}/documents/ingest`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteDocument: async (documentId) => {
    const response = await apiClient.delete(`${KB_BASE}/documents/${documentId}`);
    return response.data;
  },

  // =========================================================================
  //  Search
  // =========================================================================

  search: async (query, collections, options) => {
    const response = await apiClient.post(`${KB_BASE}/search`, {
      query,
      collections,
      ...options,
    });
    return response.data;
  },

  // =========================================================================
  //  Stats
  // =========================================================================

  getStats: async () => {
    const response = await apiClient.get(`${KB_BASE}/stats`);
    return response.data;
  },
};

export default knowledgeService;

