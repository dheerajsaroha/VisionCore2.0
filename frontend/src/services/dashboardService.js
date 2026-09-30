/**
 * dashboardService.js
 * API client for the Phase 4 Unified Role-Aware Dashboard & Workforce Command Center.
 */
import apiClient from './apiClient';

export const dashboardService = {
  /**
   * Executive & Role-Aware Command Center Overview (SuperAdmin, OrgAdmin, HR, Manager, Employee)
   */
  getOverview: async () => {
    try {
      const res = await apiClient.get('/dashboard/overview');
      return res.data;
    } catch (err) {
      console.warn('Dashboard overview fetch failed, utilizing fallback metrics:', err);
      return null;
    }
  },

  /**
   * Workforce distribution, headcount dynamics, employment types & branches
   */
  getWorkforceBreakdown: async (departmentId = null) => {
    try {
      const params = departmentId && departmentId !== 'all' ? { department_id: departmentId } : {};
      const res = await apiClient.get('/dashboard/workforce-breakdown', { params });
      return res.data;
    } catch (err) {
      console.warn('Workforce breakdown fetch failed, utilizing fallback metrics:', err);
      return null;
    }
  },

  /**
   * Real-time attendance intelligence, 7-day trend, and live biometric feed
   */
  getAttendanceStats: async () => {
    try {
      const res = await apiClient.get('/dashboard/attendance-stats');
      return res.data;
    } catch (err) {
      console.warn('Attendance stats fetch failed, utilizing fallback metrics:', err);
      return null;
    }
  },

  /**
   * Personal leave balances for employees or team leave schedules for managers/admins
   */
  getLeaveOverview: async () => {
    try {
      const res = await apiClient.get('/dashboard/leave-overview');
      return res.data;
    } catch (err) {
      console.warn('Leave overview fetch failed, utilizing fallback metrics:', err);
      return null;
    }
  },

  /**
   * Centralized actionable approvals across Leaves, Expenses, Corrections, Workflows
   */
  getPendingApprovals: async () => {
    try {
      const res = await apiClient.get('/dashboard/pending-approvals');
      return res.data;
    } catch (err) {
      console.warn('Pending approvals fetch failed, utilizing fallback metrics:', err);
      return [];
    }
  },

  /**
   * Execute immediate approval or rejection action on an entity
   */
  processApprovalAction: async (itemType, itemId, action, note = '') => {
    const res = await apiClient.post(`/dashboard/approvals/${itemType}/${itemId}/action`, {
      action,
      note,
    });
    return res.data;
  },

  /**
   * Operational, compliance, and attendance anomaly alerts
   */
  getAlerts: async () => {
    try {
      const res = await apiClient.get('/dashboard/alerts');
      return res.data;
    } catch (err) {
      console.warn('Alerts fetch failed, utilizing fallback metrics:', err);
      return [];
    }
  },

  /**
   * Chronological tenant audit and activity stream
   */
  getActivityFeed: async (filterType = 'all', limit = 15) => {
    try {
      const res = await apiClient.get('/dashboard/activity-feed', {
        params: { filter_type: filterType, limit },
      });
      return res.data;
    } catch (err) {
      console.warn('Activity feed fetch failed, utilizing fallback metrics:', err);
      return [];
    }
  },

  /**
   * Multi-dimensional interactive analytics (attendance compliance, leave utilization, hiring)
   */
  getAnalytics: async () => {
    try {
      const res = await apiClient.get('/dashboard/analytics');
      return res.data;
    } catch (err) {
      console.warn('Analytics fetch failed, utilizing fallback metrics:', err);
      return null;
    }
  },

  /**
   * Role-scoped AI Insights generated from organizational data
   */
  getAIInsights: async () => {
    try {
      const res = await apiClient.get('/dashboard/ai-insights');
      return res.data;
    } catch (err) {
      console.warn('AI insights fetch failed, utilizing fallback metrics:', err);
      return [];
    }
  },
};

export default dashboardService;
