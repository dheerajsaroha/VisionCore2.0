import apiClient from './apiClient';

export const onboardingService = {
  start: (email, organizationName) =>
    apiClient.post('/onboarding/start', {
      email,
      organization_name: organizationName,
    }),

  verifyEmail: (sessionId, token) =>
    apiClient.post('/onboarding/verify-email', {
      session_id: sessionId,
      token,
    }),

  resendVerification: (sessionId) =>
    apiClient.post(`/onboarding/resend-verification?session_id=${sessionId}`),

  verifyOrganization: (sessionId, legalId = '') =>
    apiClient.post('/onboarding/verify-organization', {
      session_id: sessionId,
      legal_id: legalId,
    }),

  createAdmin: (sessionId, password, fullName) =>
    apiClient.post('/onboarding/create-admin', {
      session_id: sessionId,
      password,
      full_name: fullName,
    }),

  selectPlan: (sessionId, planCode) =>
    apiClient.post('/onboarding/select-plan', {
      session_id: sessionId,
      plan_code: planCode,
    }),

  getPlans: () => apiClient.get('/onboarding/plans'),

  saveBranding: (sessionId, branding) =>
    apiClient.post('/onboarding/branding', {
      session_id: sessionId,
      branding,
    }),

  skipBranding: (sessionId) =>
    apiClient.post(`/onboarding/skip-branding?session_id=${sessionId}`),

  saveConfiguration: (sessionId, config) =>
    apiClient.post('/onboarding/configuration', {
      session_id: sessionId,
      config,
    }),

  skipConfiguration: (sessionId) =>
    apiClient.post(`/onboarding/skip-configuration?session_id=${sessionId}`),

  complete: (sessionId) =>
    apiClient.post('/onboarding/complete', {
      session_id: sessionId,
    }),

  getProgress: (sessionId) =>
    apiClient.get(`/onboarding/progress/${sessionId}`),

  getSession: (sessionId) =>
    apiClient.get(`/onboarding/session/${sessionId}`),
};
