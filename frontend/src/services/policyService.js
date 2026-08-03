import { apiClient } from './apiClient';

const API_BASE = '/policy';

class PolicyService {
  // ── Categories ──────────────────────────────────────────────────────────
  async getCategories() {
    const response = await apiClient.get(`${API_BASE}/categories`);
    return response.data;
  }

  async createCategory(data) {
    const response = await apiClient.post(`${API_BASE}/categories`, data);
    return response.data;
  }

  async updateCategory(id, data) {
    const response = await apiClient.patch(`${API_BASE}/categories/${id}`, data);
    return response.data;
  }

  // ── Tags ────────────────────────────────────────────────────────────────
  async getTags() {
    const response = await apiClient.get(`${API_BASE}/tags`);
    return response.data;
  }

  async createTag(data) {
    const response = await apiClient.post(`${API_BASE}/tags`, data);
    return response.data;
  }

  // ── Documents (Search + CRUD) ──────────────────────────────────────────
  async searchDocuments(params = {}) {
    const response = await apiClient.get(`${API_BASE}/documents`, { params });
    return response.data;
  }

  async getDocument(id) {
    const response = await apiClient.get(`${API_BASE}/documents/${id}`);
    return response.data;
  }

  async createDocument(data) {
    const response = await apiClient.post(`${API_BASE}/documents`, data);
    return response.data;
  }

  async updateDocument(id, data) {
    const response = await apiClient.patch(`${API_BASE}/documents/${id}`, data);
    return response.data;
  }

  async publishDocument(id) {
    const response = await apiClient.post(`${API_BASE}/documents/${id}/publish`);
    return response.data;
  }

  async archiveDocument(id) {
    const response = await apiClient.post(`${API_BASE}/documents/${id}/archive`);
    return response.data;
  }

  // ── Versions ────────────────────────────────────────────────────────────
  async getVersions(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/versions`);
    return response.data;
  }

  async createVersion(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/versions`, data);
    return response.data;
  }

  // ── Attachments ─────────────────────────────────────────────────────────
  async getAttachments(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/attachments`);
    return response.data;
  }

  async createAttachment(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/attachments`, data);
    return response.data;
  }

  // ── Distribution ────────────────────────────────────────────────────────
  async getDistributions(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/distributions`);
    return response.data;
  }

  async createDistribution(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/distributions`, data);
    return response.data;
  }

  async distributeToOrg(docId) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/distribute/org`);
    return response.data;
  }

  async distributeToDepartment(docId, deptId) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/distribute/department/${deptId}`);
    return response.data;
  }

  async distributeToUser(docId, userId) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/distribute/user/${userId}`);
    return response.data;
  }

  async getDistributionStats() {
    const response = await apiClient.get(`${API_BASE}/distribution-stats`);
    return response.data;
  }

  // ── Acknowledgements ────────────────────────────────────────────────────
  async getAcknowledgements(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/acknowledgements`);
    return response.data;
  }

  async acknowledgePolicy(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/acknowledge`, data);
    return response.data;
  }

  async getPendingAcknowledgements() {
    const response = await apiClient.get(`${API_BASE}/pending-acknowledgements`);
    return response.data;
  }

  // ── Signatures ──────────────────────────────────────────────────────────
  async getSignatures(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/signatures`);
    return response.data;
  }

  async signDocument(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/sign`, data);
    return response.data;
  }

  async verifySignature(sigId) {
    const response = await apiClient.get(`${API_BASE}/signatures/${sigId}/verify`);
    return response.data;
  }

  // ── Templates ───────────────────────────────────────────────────────────
  async getTemplates() {
    const response = await apiClient.get(`${API_BASE}/templates`);
    return response.data;
  }

  async createTemplate(data) {
    const response = await apiClient.post(`${API_BASE}/templates`, data);
    return response.data;
  }

  // ── Reminders & Notifications ───────────────────────────────────────────
  async createReminder(docId, data) {
    const response = await apiClient.post(`${API_BASE}/documents/${docId}/reminders`, data);
    return response.data;
  }

  async getReminders(docId) {
    const response = await apiClient.get(`${API_BASE}/documents/${docId}/reminders`);
    return response.data;
  }

  async processReminders() {
    const response = await apiClient.post(`${API_BASE}/reminders/process`);
    return response.data;
  }

  async getNotifications(unreadOnly = false) {
    const response = await apiClient.get(`${API_BASE}/notifications`, {
      params: { unread_only: unreadOnly },
    });
    return response.data;
  }

  async markNotificationRead(notifId) {
    const response = await apiClient.post(`${API_BASE}/notifications/${notifId}/read`);
    return response.data;
  }

  async getReminderStats() {
    const response = await apiClient.get(`${API_BASE}/reminder-stats`);
    return response.data;
  }

  // ── Compliance ──────────────────────────────────────────────────────────
  async getComplianceRules() {
    const response = await apiClient.get(`${API_BASE}/compliance-rules`);
    return response.data;
  }

  async createComplianceRule(data) {
    const response = await apiClient.post(`${API_BASE}/compliance-rules`, data);
    return response.data;
  }

  async getComplianceSummary() {
    const response = await apiClient.get(`${API_BASE}/compliance/summary`);
    return response.data;
  }

  async runComplianceCheck(userId) {
    const response = await apiClient.post(`${API_BASE}/compliance/check`, null, {
      params: userId ? { user_id: userId } : {},
    });
    return response.data;
  }

  async getComplianceBreaches() {
    const response = await apiClient.get(`${API_BASE}/compliance/breaches`);
    return response.data;
  }

  async getComplianceTrend(days = 90) {
    const response = await apiClient.get(`${API_BASE}/compliance/trend`, {
      params: { days },
    });
    return response.data;
  }

  // ── Analytics & Reports ─────────────────────────────────────────────────
  async getAnalytics() {
    const response = await apiClient.get(`${API_BASE}/analytics/dashboard`);
    return response.data;
  }

  async getReport() {
    const response = await apiClient.get(`${API_BASE}/analytics/report`);
    return response.data;
  }

  // ── Utility ─────────────────────────────────────────────────────────────
  async getUsersForPolicy(docId) {
    const response = await apiClient.get(`${API_BASE}/users-for-policy/${docId}`);
    return response.data;
  }
}

export const policyService = new PolicyService();

