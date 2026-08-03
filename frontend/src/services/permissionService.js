import { apiClient } from './apiClient';

/**
 * Permission Service — Full Permission System API Client
 *
 * Implements all endpoints from the EAAC Permission System:
 * - CRUD permissions
 * - Bulk assign/remove
 * - Activation/deactivation
 * - Module statistics
 * - Advanced search
 * - User effective permissions
 * - Audit log
 * - Export
 * - Validation
 */
class PermissionService {
  constructor() {
    this.basePath = '/rbac/permissions';
  }

  // ── Basic CRUD ──────────────────────────────────────────────────────────

  async list(params = {}) {
    const { skip = 0, limit = 50, module, is_active, search } = params;
    const response = await apiClient.get(this.basePath, {
      params: { skip, limit, module, is_active, search },
    });
    return response.data;
  }

  async getById(id) {
    const response = await apiClient.get(`${this.basePath}/${id}`);
    return response.data;
  }

  async getDetail(id) {
    const response = await apiClient.get(`${this.basePath}/${id}/detail`);
    return response.data;
  }

  async create(data) {
    const response = await apiClient.post(this.basePath, data);
    return response.data;
  }

  async update(id, data) {
    const response = await apiClient.patch(`${this.basePath}/${id}`, data);
    return response.data;
  }

  async delete(id) {
    const response = await apiClient.delete(`${this.basePath}/${id}`);
    return response.data;
  }

  // ── Validation ──────────────────────────────────────────────────────────

  async validateNames(names) {
    const response = await apiClient.post(`${this.basePath}/validate`, { names });
    return response.data;
  }

  // ── Bulk Operations ─────────────────────────────────────────────────────

  async bulkAssign(roleId, permissionIds) {
    const response = await apiClient.post(`${this.basePath}/bulk/assign`, {
      role_id: roleId,
      permission_ids: permissionIds,
    });
    return response.data;
  }

  async bulkRemove(roleId, permissionIds) {
    const response = await apiClient.post(`${this.basePath}/bulk/remove`, {
      role_id: roleId,
      permission_ids: permissionIds,
    });
    return response.data;
  }

  // ── Activation / Deactivation ──────────────────────────────────────────

  async setStatus(id, isActive) {
    const response = await apiClient.patch(`${this.basePath}/${id}/status`, {
      is_active: isActive,
    });
    return response.data;
  }

  // ── Module Statistics ───────────────────────────────────────────────────

  async getModuleStats() {
    const response = await apiClient.get(`${this.basePath}/modules/stats`);
    return response.data;
  }

  async getModuleSummary() {
    const response = await apiClient.get(`${this.basePath}/modules/summary`);
    return response.data;
  }

  async listModules() {
    const response = await apiClient.get(`${this.basePath}/modules`);
    return response.data;
  }

  // ── Advanced Search ─────────────────────────────────────────────────────

  async searchAdvanced(params = {}) {
    const {
      search,
      module,
      group,
      is_active,
      skip = 0,
      limit = 50,
    } = params;
    const response = await apiClient.get(`${this.basePath}/search/advanced`, {
      params: { search, module, group, is_active, skip, limit },
    });
    return response.data;
  }

  // ── User Permissions ────────────────────────────────────────────────────

  async getUserPermissions(userId) {
    const response = await apiClient.get(`/rbac/user/${userId}/permissions`);
    return response.data;
  }

  async getMyPermissions() {
    const response = await apiClient.get('/rbac/me/permissions');
    return response.data;
  }

  // ── Audit Log ───────────────────────────────────────────────────────────

  async getAuditLog(limit = 100) {
    const response = await apiClient.get(`${this.basePath}/audit`, {
      params: { limit },
    });
    return response.data;
  }

  // ── Export ──────────────────────────────────────────────────────────────

  async export(format = 'json', params = {}) {
    const { module, is_active } = params;
    const response = await apiClient.get(`${this.basePath}/export`, {
      params: { format, module, is_active },
    });
    return response.data;
  }

  async exportCsv(params = {}) {
    const { module, is_active } = params;
    const response = await apiClient.get(`${this.basePath}/export`, {
      params: { format: 'csv', module, is_active },
      responseType: 'blob',
    });
    return response.data;
  }
}

export const permissionService = new PermissionService();

