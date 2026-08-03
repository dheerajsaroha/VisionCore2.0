/**
 * operationsService.js — Enterprise Platform Operations Service
 * Sprint 5 — Phase C: Enterprise Platform Operations
 *
 * Centralized API client for:
 * - Health & Monitoring
 * - Scheduler / Jobs
 * - Analytics
 * - Search
 * - Reporting
 * - Configuration Center
 * - Intelligence (Anomalies, Insights, Risk)
 */
import apiClient from './apiClient';

const BASE = '/operations';

// =============================================================================
//  Health & Monitoring
// =============================================================================

export const getPlatformHealth = async () => {
  const response = await apiClient.get(`${BASE}/health`);
  return response.data;
};

export const getPlatformMetrics = async (name = '', minutes = 60) => {
  const response = await apiClient.get(`${BASE}/metrics`, {
    params: { name, minutes }
  });
  return response.data;
};

export const getOperationsDashboard = async () => {
  const response = await apiClient.get(`${BASE}/dashboard`);
  return response.data;
};

// =============================================================================
//  Scheduler / Jobs
// =============================================================================

export const listJobs = async (params = {}) => {
  const response = await apiClient.get(`${BASE}/jobs`, { params });
  return response.data;
};

export const getJob = async (jobId) => {
  const response = await apiClient.get(`${BASE}/jobs/${jobId}`);
  return response.data;
};

export const createJob = async (jobData) => {
  const response = await apiClient.post(`${BASE}/jobs`, jobData);
  return response.data;
};

export const cancelJob = async (jobId) => {
  const response = await apiClient.post(`${BASE}/jobs/${jobId}/cancel`);
  return response.data;
};

export const getJobDefinitions = async () => {
  const response = await apiClient.get(`${BASE}/jobs/definitions`);
  return response.data;
};

export const startScheduler = async () => {
  const response = await apiClient.post(`${BASE}/scheduler/start`);
  return response.data;
};

export const stopScheduler = async () => {
  const response = await apiClient.post(`${BASE}/scheduler/stop`);
  return response.data;
};

export const seedDefaultJobs = async () => {
  const response = await apiClient.post(`${BASE}/scheduler/seed`);
  return response.data;
};

// =============================================================================
//  Analytics
// =============================================================================

export const getAnalyticsSection = async (section, orgId = '') => {
  const response = await apiClient.get(`${BASE}/analytics/${section}`, {
    params: { org_id: orgId }
  });
  return response.data;
};

export const getExecutiveDashboard = async (orgId = '') => {
  const response = await apiClient.get(`${BASE}/analytics/dashboard`, {
    params: { org_id: orgId }
  });
  return response.data;
};

// =============================================================================
//  Search
// =============================================================================

export const globalSearch = async (query, params = {}) => {
  const response = await apiClient.get(`${BASE}/search`, {
    params: { query, ...params }
  });
  return response.data;
};

export const getSearchHistory = async (limit = 50) => {
  const response = await apiClient.get(`${BASE}/search/history`, {
    params: { limit }
  });
  return response.data;
};

// =============================================================================
//  Reporting
// =============================================================================

export const generateReport = async (reportData) => {
  const response = await apiClient.post(`${BASE}/reports/generate`, reportData);
  return response.data;
};

export const listReports = async (params = {}) => {
  const response = await apiClient.get(`${BASE}/reports`, { params });
  return response.data;
};

export const getReportTemplates = async () => {
  const response = await apiClient.get(`${BASE}/reports/templates`);
  return response.data;
};

// =============================================================================
//  Configuration Center
// =============================================================================

export const getConfigurations = async (category = '') => {
  const response = await apiClient.get(`${BASE}/config`, {
    params: { category }
  });
  return response.data;
};

export const updateConfiguration = async (key, value) => {
  const response = await apiClient.put(`${BASE}/config`, { key, value });
  return response.data;
};

export const getFeatureFlags = async () => {
  const response = await apiClient.get(`${BASE}/config/feature-flags`);
  return response.data;
};

export const getConfigCategories = async () => {
  const response = await apiClient.get(`${BASE}/config/categories`);
  return response.data;
};

// =============================================================================
//  Intelligence
// =============================================================================

export const getAnomalies = async (orgId = '') => {
  const response = await apiClient.get(`${BASE}/intelligence/anomalies`, {
    params: { org_id: orgId }
  });
  return response.data;
};

export const getInsights = async (orgId = '') => {
  const response = await apiClient.get(`${BASE}/intelligence/insights`, {
    params: { org_id: orgId }
  });
  return response.data;
};

export const getRiskAssessment = async (orgId = '') => {
  const response = await apiClient.get(`${BASE}/intelligence/risk`, {
    params: { org_id: orgId }
  });
  return response.data;
};

export const getIntelligenceDashboard = async (orgId = '') => {
  const response = await apiClient.get(`${BASE}/intelligence/dashboard`, {
    params: { org_id: orgId }
  });
  return response.data;
};

// =============================================================================
//  Events
// =============================================================================

export const getEventHistory = async (params = {}) => {
  const response = await apiClient.get(`${BASE}/events`, { params });
  return response.data;
};

export const getEventStats = async () => {
  const response = await apiClient.get(`${BASE}/events/stats`);
  return response.data;
};
