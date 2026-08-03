/**
 * tenantService.js — Tenant Administration API Client
 * Sprint 6 — Phase B: Enterprise Multi-Tenant SaaS Completion
 *
 * Covers:
 * - Tenant CRUD and lifecycle
 * - Branding management
 * - Custom domain management
 * - Configuration management
 * - Tenant isolation
 * - Tenant analytics
 * - Billing & subscription management
 */
import apiClient from './apiClient';

const BASE = '/tenant';
const BILLING = '/billing';

// =========================================================================
// Tenant Management
// =========================================================================

export const tenantService = {
  // List tenants
  list: (params = {}) =>
    apiClient.get(BASE, { params }).then((r) => r.data),

  // Get tenant details
  get: (orgId) =>
    apiClient.get(`${BASE}/${orgId}`).then((r) => r.data),

  // Provision a new tenant
  provision: (data) =>
    apiClient.post(`${BASE}/provision`, null, { params: data }).then((r) => r.data),

  // Suspend tenant
  suspend: (orgId, reason = 'Administrative action') =>
    apiClient.post(`${BASE}/${orgId}/suspend`, null, { params: { reason } }).then((r) => r.data),

  // Activate tenant
  activate: (orgId, reason = 'Administrative action') =>
    apiClient.post(`${BASE}/${orgId}/activate`, null, { params: { reason } }).then((r) => r.data),

  // Delete tenant
  delete: (orgId, reason = 'Administrative action') =>
    apiClient.delete(`${BASE}/${orgId}`, { params: { reason } }).then((r) => r.data),
};

// =========================================================================
// Branding
// =========================================================================

export const brandingService = {
  // Get branding
  get: (orgId) =>
    apiClient.get(`${BASE}/${orgId}/branding`).then((r) => r.data),

  // Update branding
  update: (orgId, brandingData) =>
    apiClient.put(`${BASE}/${orgId}/branding`, brandingData).then((r) => r.data),

  // Reset branding to defaults
  reset: (orgId) =>
    apiClient.post(`${BASE}/${orgId}/branding/reset`).then((r) => r.data),

  // Get branding preview
  preview: (orgId) =>
    apiClient.get(`${BASE}/${orgId}/branding/preview`).then((r) => r.data),

  // Set custom domain
  setDomain: (orgId, domain) =>
    apiClient.post(`${BASE}/${orgId}/domain`, null, { params: { domain } }).then((r) => r.data),

  // Verify domain
  verifyDomain: (orgId, domain, verified = true) =>
    apiClient.post(`${BASE}/${orgId}/domain/verify`, null, { params: { domain, verified } }).then((r) => r.data),
};

// =========================================================================
// Configuration
// =========================================================================

export const configService = {
  // Get config
  get: (orgId, category = null) => {
    const params = {};
    if (category) params.category = category;
    return apiClient.get(`${BASE}/${orgId}/config`, { params }).then((r) => r.data);
  },

  // Update config
  update: (orgId, config) =>
    apiClient.put(`${BASE}/${orgId}/config`, config).then((r) => r.data),

  // Get config definitions
  getDefinitions: () =>
    apiClient.get(`${BASE}/config/definitions`).then((r) => r.data),
};

// =========================================================================
// Isolation
// =========================================================================

export const isolationService = {
  // Get isolation report for a tenant
  getReport: (orgId) =>
    apiClient.get(`${BASE}/${orgId}/isolation`).then((r) => r.data),

  // Get global isolation summary
  getSummary: () =>
    apiClient.get(`${BASE}/isolation/summary`).then((r) => r.data),
};

// =========================================================================
// Analytics
// =========================================================================

export const analyticsService = {
  // Get tenant analytics dashboard
  getDashboard: (orgId) =>
    apiClient.get(`${BASE}/${orgId}/analytics`).then((r) => r.data),

  // Get platform-wide summary
  getPlatformSummary: () =>
    apiClient.get(`${BASE}/analytics/platform-summary`).then((r) => r.data),
};

// =========================================================================
// Billing
// =========================================================================

export const billingService = {
  // Change subscription plan
  changePlan: (data) =>
    apiClient.post(`${BILLING}/subscription/change`, data).then((r) => r.data),

  // Manage trial
  manageTrial: (data) =>
    apiClient.post(`${BILLING}/subscription/trial`, data).then((r) => r.data),

  // Configure renewal
  configureRenewal: (data) =>
    apiClient.post(`${BILLING}/subscription/renewal`, data).then((r) => r.data),

  // Generate invoice
  generateInvoice: (organizationId, billingCycle = 'monthly') =>
    apiClient.post(`${BILLING}/invoices/generate`, null, { params: { organization_id: organizationId, billing_cycle: billingCycle } }).then((r) => r.data),

  // List invoices
  listInvoices: (params = {}) =>
    apiClient.get(`${BILLING}/invoices`, { params }).then((r) => r.data),

  // Get billing analytics
  getAnalytics: (organizationId) =>
    apiClient.get(`${BILLING}/analytics/${organizationId}`).then((r) => r.data),

  // Get billing events
  getEvents: (organizationId, limit = 50) =>
    apiClient.get(`${BILLING}/events/${organizationId}`, { params: { limit } }).then((r) => r.data),

  // Get payment providers
  getProviders: () =>
    apiClient.get(`${BILLING}/providers`).then((r) => r.data),
};

// =========================================================================
// Onboarding
// =========================================================================

export const onboardingService = {
  // Start onboarding
  start: (data) =>
    apiClient.post('/onboarding/start', data).then((r) => r.data),

  // Verify email
  verifyEmail: (data) =>
    apiClient.post('/onboarding/verify-email', data).then((r) => r.data),

  // Resend verification
  resendVerification: (sessionId) =>
    apiClient.post('/onboarding/resend-verification', null, { params: { session_id: sessionId } }).then((r) => r.data),

  // Verify organization
  verifyOrganization: (data) =>
    apiClient.post('/onboarding/verify-organization', data).then((r) => r.data),

  // Create admin and provision
  createAdmin: (data) =>
    apiClient.post('/onboarding/create-admin', data).then((r) => r.data),

  // Select plan
  selectPlan: (data) =>
    apiClient.post('/onboarding/select-plan', data).then((r) => r.data),

  // Get available plans
  getPlans: () =>
    apiClient.get('/onboarding/plans').then((r) => r.data),

  // Save branding
  saveBranding: (data) =>
    apiClient.post('/onboarding/branding', data).then((r) => r.data),

  // Skip branding
  skipBranding: (sessionId) =>
    apiClient.post('/onboarding/skip-branding', null, { params: { session_id: sessionId } }).then((r) => r.data),

  // Save configuration
  saveConfiguration: (data) =>
    apiClient.post('/onboarding/configuration', data).then((r) => r.data),

  // Skip configuration
  skipConfiguration: (sessionId) =>
    apiClient.post('/onboarding/skip-configuration', null, { params: { session_id: sessionId } }).then((r) => r.data),

  // Complete onboarding
  complete: (data) =>
    apiClient.post('/onboarding/complete', data).then((r) => r.data),

  // Get progress
  getProgress: (sessionId) =>
    apiClient.get(`/onboarding/progress/${sessionId}`).then((r) => r.data),

  // Get session
  getSession: (sessionId) =>
    apiClient.get(`/onboarding/session/${sessionId}`).then((r) => r.data),
};

export default {
  tenantService,
  brandingService,
  configService,
  isolationService,
  analyticsService,
  billingService,
  onboardingService,
};
