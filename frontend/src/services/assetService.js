import { apiClient } from './apiClient';

const API_BASE = '/assets';

class AssetService {
  // ── Dashboard ──────────────────────────────────────────────────────────
  async getDashboard() {
    const response = await apiClient.get(`${API_BASE}/dashboard`);
    return response.data;
  }

  // ── Categories ─────────────────────────────────────────────────────────
  async getCategories() {
    const response = await apiClient.get(`${API_BASE}/categories`);
    return response.data;
  }

  async createCategory(data) {
    const response = await apiClient.post(`${API_BASE}/categories`, data);
    return response.data;
  }

  // ── Inventory ─────────────────────────────────────────────────────────
  async getInventory(params = {}) {
    const response = await apiClient.get(`${API_BASE}/inventory`, { params });
    return response.data;
  }

  async getAsset(id) {
    const response = await apiClient.get(`${API_BASE}/inventory/${id}`);
    return response.data;
  }

  async createAsset(data) {
    const response = await apiClient.post(`${API_BASE}/inventory`, data);
    return response.data;
  }

  async updateAsset(id, data) {
    const response = await apiClient.patch(`${API_BASE}/inventory/${id}`, data);
    return response.data;
  }

  async deleteAsset(id) {
    const response = await apiClient.delete(`${API_BASE}/inventory/${id}`);
    return response.data;
  }

  // ── Search ─────────────────────────────────────────────────────────────
  async searchAssets(q, params = {}) {
    const response = await apiClient.get(`${API_BASE}/search`, { params: { q, ...params } });
    return response.data;
  }

  // ── Export ─────────────────────────────────────────────────────────────
  async exportAssets(params = {}) {
    const response = await apiClient.get(`${API_BASE}/export`, { params });
    return response.data;
  }

  // ── Assignments ───────────────────────────────────────────────────────
  async assignAsset(data) {
    const response = await apiClient.post(`${API_BASE}/assignments`, data);
    return response.data;
  }

  async returnAsset(assignmentId, data) {
    const response = await apiClient.post(`${API_BASE}/assignments/${assignmentId}/return`, data);
    return response.data;
  }

  async getAssignments(params = {}) {
    const response = await apiClient.get(`${API_BASE}/assignments`, { params });
    return response.data;
  }

  async getMyAssets() {
    const response = await apiClient.get(`${API_BASE}/assignments/active`);
    return response.data;
  }

  async transferAsset(assignmentId, newUserId, notes) {
    const response = await apiClient.post(`${API_BASE}/transfers`, null, {
      params: { assignment_id: assignmentId, new_user_id: newUserId, notes }
    });
    return response.data;
  }

  // ── Maintenance ───────────────────────────────────────────────────────
  async scheduleMaintenance(data) {
    const response = await apiClient.post(`${API_BASE}/maintenance`, data);
    return response.data;
  }

  async getMaintenance(params = {}) {
    const response = await apiClient.get(`${API_BASE}/maintenance`, { params });
    return response.data;
  }

  async completeMaintenance(maintId, data) {
    const response = await apiClient.post(`${API_BASE}/maintenance/${maintId}/complete`, data);
    return response.data;
  }

  // ── Warranty ──────────────────────────────────────────────────────────
  async getWarrantyExpiring(days = 30) {
    const response = await apiClient.get(`${API_BASE}/warranty/expiring`, { params: { days } });
    return response.data;
  }

  // ── Licenses ──────────────────────────────────────────────────────────
  async getLicenses(params = {}) {
    const response = await apiClient.get(`${API_BASE}/licenses`, { params });
    return response.data;
  }

  async createLicense(data) {
    const response = await apiClient.post(`${API_BASE}/licenses`, data);
    return response.data;
  }

  async getLicensesExpiring(days = 30) {
    const response = await apiClient.get(`${API_BASE}/licenses/expiring`, { params: { days } });
    return response.data;
  }

  // ── Vendors ───────────────────────────────────────────────────────────
  async getVendors() {
    const response = await apiClient.get(`${API_BASE}/vendors`);
    return response.data;
  }

  async createVendor(data) {
    const response = await apiClient.post(`${API_BASE}/vendors`, data);
    return response.data;
  }

  // ── Purchase Orders ───────────────────────────────────────────────────
  async getPurchaseOrders() {
    const response = await apiClient.get(`${API_BASE}/purchase-orders`);
    return response.data;
  }

  async createPurchaseOrder(data) {
    const response = await apiClient.post(`${API_BASE}/purchase-orders`, data);
    return response.data;
  }

  async receivePurchaseOrder(poId, items) {
    const response = await apiClient.post(`${API_BASE}/purchase-orders/${poId}/receive`, items);
    return response.data;
  }

  // ── Audits ────────────────────────────────────────────────────────────
  async getAudits() {
    const response = await apiClient.get(`${API_BASE}/audits`);
    return response.data;
  }

  async createAudit(data) {
    const response = await apiClient.post(`${API_BASE}/audits`, data);
    return response.data;
  }

  async completeAudit(auditId, results) {
    const response = await apiClient.post(`${API_BASE}/audits/${auditId}/complete`, results);
    return response.data;
  }

  // ── Depreciation ──────────────────────────────────────────────────────
  async computeDepreciation(assetId) {
    const response = await apiClient.post(`${API_BASE}/depreciation/compute`, null, {
      params: { asset_id: assetId }
    });
    return response.data;
  }

  async getDepreciationSchedule(assetId) {
    const response = await apiClient.get(`${API_BASE}/depreciation/${assetId}`);
    return response.data;
  }

  // ── Disposals ─────────────────────────────────────────────────────────
  async getDisposals() {
    const response = await apiClient.get(`${API_BASE}/disposals`);
    return response.data;
  }

  async disposeAsset(data) {
    const response = await apiClient.post(`${API_BASE}/disposals`, data);
    return response.data;
  }

  // ── Consumables ──────────────────────────────────────────────────────
  async getConsumables(lowStockOnly = false) {
    const response = await apiClient.get(`${API_BASE}/consumables`, {
      params: { low_stock_only: lowStockOnly }
    });
    return response.data;
  }

  async createConsumable(data) {
    const response = await apiClient.post(`${API_BASE}/consumables`, data);
    return response.data;
  }

  async issueConsumable(data) {
    const response = await apiClient.post(`${API_BASE}/consumable-issuances`, data);
    return response.data;
  }

  // ── Insurance ─────────────────────────────────────────────────────────
  async addInsurance(data) {
    const response = await apiClient.post(`${API_BASE}/insurance`, data);
    return response.data;
  }

  // ── Bulk Operations ───────────────────────────────────────────────────
  async bulkAssign(assetIds, userId) {
    const response = await apiClient.post(`${API_BASE}/bulk/assign`, assetIds, {
      params: { user_id: userId }
    });
    return response.data;
  }

  async bulkImport(assets) {
    const response = await apiClient.post(`${API_BASE}/bulk/import`, assets);
    return response.data;
  }

  // ── Reports ───────────────────────────────────────────────────────────
  async getDepartmentAllocation() {
    const response = await apiClient.get(`${API_BASE}/reports/department-allocation`);
    return response.data;
  }

  async getAssetUtilization() {
    const response = await apiClient.get(`${API_BASE}/reports/asset-utilization`);
    return response.data;
  }

  async getProcurementTrends(months = 12) {
    const response = await apiClient.get(`${API_BASE}/reports/procurement-trends`, {
      params: { months }
    });
    return response.data;
  }

  async getMaintenanceCosts(months = 12) {
    const response = await apiClient.get(`${API_BASE}/reports/maintenance-costs`, {
      params: { months }
    });
    return response.data;
  }
}

export const assetService = new AssetService();

