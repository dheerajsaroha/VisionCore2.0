import api from './apiClient';

export const dynamicRoleService = {
  seedTemplates: async () => {
    const res = await api.post('/dynamic-roles/seed');
    return res.data;
  },

  getTemplates: async (category = null) => {
    const res = await api.get('/dynamic-roles/templates', { params: { category } });
    return res.data;
  },

  getRoles: async (tier = null) => {
    const res = await api.get('/dynamic-roles/roles', { params: { tier } });
    return res.data;
  },

  getRoleById: async (roleId) => {
    const res = await api.get(`/dynamic-roles/roles/${roleId}`);
    return res.data;
  },

  createRole: async (roleData) => {
    const res = await api.post('/dynamic-roles/roles', roleData);
    return res.data;
  },

  createRoleFromTemplate: async (templateCode, customName = null, customCode = null) => {
    const res = await api.post('/dynamic-roles/roles/from-template', null, {
      params: { template_code: templateCode, custom_name: customName, custom_code: customCode }
    });
    return res.data;
  },

  cloneRole: async (roleId, newCode, newName) => {
    const res = await api.post(`/dynamic-roles/roles/${roleId}/clone`, null, {
      params: { new_code: newCode, new_name: newName }
    });
    return res.data;
  },

  updateRole: async (roleId, updates) => {
    const res = await api.put(`/dynamic-roles/roles/${roleId}`, updates);
    return res.data;
  },

  deleteRole: async (roleId) => {
    const res = await api.delete(`/dynamic-roles/roles/${roleId}`);
    return res.data;
  },

  createInheritance: async (parentRoleId, childRoleId, options = {}) => {
    const res = await api.post('/dynamic-roles/roles/inheritance', {
      parent_role_id: parentRoleId,
      child_role_id: childRoleId,
      ...options
    });
    return res.data;
  },

  assignRole: async (userId, roleId, isPrimary = false, expiresAt = null) => {
    const res = await api.post('/dynamic-roles/roles/assign', {
      user_id: userId,
      role_id: roleId,
      is_primary: isPrimary,
      expires_at: expiresAt
    });
    return res.data;
  },

  removeAssignment: async (assignmentId) => {
    const res = await api.delete(`/dynamic-roles/roles/assignment/${assignmentId}`);
    return res.data;
  },

  getRoleVersions: async (roleId) => {
    const res = await api.get(`/dynamic-roles/roles/${roleId}/versions`);
    return res.data;
  },

  rollbackVersion: async (roleId, targetVersion) => {
    const res = await api.post(`/dynamic-roles/roles/${roleId}/rollback/${targetVersion}`);
    return res.data;
  },

  getRoleDiff: async (roleId, v1, v2) => {
    const res = await api.get(`/dynamic-roles/roles/${roleId}/diff`, { params: { v1, v2 } });
    return res.data;
  },

  getEffectiveAuthorization: async (userId = null) => {
    const res = await api.get('/dynamic-roles/effective-authorization', { params: { user_id: userId } });
    return res.data;
  }
};

export default dynamicRoleService;
