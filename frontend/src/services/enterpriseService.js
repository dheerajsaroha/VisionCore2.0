/**
 * enterpriseService.js — Enterprise Platform Integration Service
 * Sprint 5 — Phase B: Enterprise Platform Integration
 *
 * Provides API client methods for:
 * - Event Bus management
 * - Notification management
 * - Audit trail
 * - Integration status
 */
import apiClient from './apiClient';

const EnterpriseService = {
  // ===========================================================================
  // Health & Status
  // ===========================================================================

  /**
   * Get enterprise platform health status.
   */
  getHealth: async () => {
    const response = await apiClient.get('/enterprise/health');
    return response.data;
  },

  // ===========================================================================
  // Event Bus
  // ===========================================================================

  /**
   * Get event bus history.
   */
  getEventHistory: async (params = {}) => {
    const response = await apiClient.get('/enterprise/events', { params });
    return response.data;
  },

  /**
   * Get event bus statistics.
   */
  getEventStats: async () => {
    const response = await apiClient.get('/enterprise/events/stats');
    return response.data;
  },

  /**
   * Get dead-letter queue entries.
   */
  getDeadLetterQueue: async () => {
    const response = await apiClient.get('/enterprise/events/dead-letter');
    return response.data;
  },

  /**
   * Retry a dead-letter entry.
   */
  retryDeadLetter: async (index) => {
    const response = await apiClient.post(`/enterprise/events/dead-letter/retry/${index}`);
    return response.data;
  },

  /**
   * Publish a domain event (for testing/integration).
   */
  publishEvent: async (eventType, eventData) => {
    const response = await apiClient.post('/enterprise/events/publish', null, {
      params: { event_type: eventType },
      data: eventData,
    });
    return response.data;
  },

  // ===========================================================================
  // Notifications
  // ===========================================================================

  /**
   * Get notifications for current user.
   */
  getNotifications: async (params = {}) => {
    const response = await apiClient.get('/enterprise/notifications', { params });
    return response.data;
  },

  /**
   * Mark a notification as read.
   */
  markNotificationRead: async (notificationId) => {
    const response = await apiClient.post(`/enterprise/notifications/${notificationId}/read`);
    return response.data;
  },

  /**
   * Mark all notifications as read.
   */
  markAllNotificationsRead: async () => {
    const response = await apiClient.post('/enterprise/notifications/read-all');
    return response.data;
  },

  /**
   * Get notification analytics.
   */
  getNotificationAnalytics: async () => {
    const response = await apiClient.get('/enterprise/notifications/analytics');
    return response.data;
  },

  // ===========================================================================
  // Audit Trail
  // ===========================================================================

  /**
   * Search audit entries.
   */
  searchAudit: async (params = {}) => {
    const response = await apiClient.get('/enterprise/audit', { params });
    return response.data;
  },

  /**
   * Get audit timeline.
   */
  getAuditTimeline: async (params = {}) => {
    const response = await apiClient.get('/enterprise/audit/timeline', { params });
    return response.data;
  },

  /**
   * Get compliance summary.
   */
  getComplianceSummary: async () => {
    const response = await apiClient.get('/enterprise/audit/compliance-summary');
    return response.data;
  },

  /**
   * Get risk alerts.
   */
  getRiskAlerts: async (params = {}) => {
    const response = await apiClient.get('/enterprise/audit/risk-alerts', { params });
    return response.data;
  },

  // ===========================================================================
  // Integration Status
  // ===========================================================================

  /**
   * Get cross-module integration verification status.
   */
  getIntegrationStatus: async () => {
    const response = await apiClient.get('/enterprise/integration-status');
    return response.data;
  },
};

export default EnterpriseService;

