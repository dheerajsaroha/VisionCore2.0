import apiClient from './apiClient';

/**
 * userService.js — Production-grade Enterprise User & Identity API Client
 * Scoped to multi-tenant organization boundaries and RBAC permissions.
 */

// userId -> object URL of the enrollment capture
const facePhotoUrlCache = new Map();
// Concurrent requests for the same user share one round trip.
const facePhotoInFlight = new Map();

export const userService = {
  // Query users with search, role, is_active, dept_id, sort_by, sort_order, pagination parameters
  getUsers: (params = {}) => apiClient.get('/users/', { params }),

  // Fetch summary aggregation metrics for identities in current tenant
  getUsersSummary: () => apiClient.get('/users/summary'),

  // Fetch single user profile by ID
  getUserById: (id) => apiClient.get(`/users/${id}`),

  // Fetch effective permissions for a user
  getUserPermissions: (id) => apiClient.get(`/rbac/user/${id}/permissions`),

  // Fetch trusted devices & active sessions for an identity
  getTrustedDevices: (id) => apiClient.get(`/identity/${id}/trusted-devices`),

  // Fetch available roles
  getRoles: (params = {}) => apiClient.get('/rbac/roles', { params }),

  // Fetch tenant branches / locations
  getBranches: () => apiClient.get('/branches'),

  // Create new user / employee identity
  createUser: (data) => apiClient.post('/users/', data),

  // Update existing user profile
  updateUser: (id, data) => apiClient.patch(`/users/${id}`, data),

  // Update own user profile
  updateMyProfile: (data) => apiClient.patch('/users/me', data),

  // Soft delete / archive user
  deleteUser: (id) => apiClient.delete(`/users/${id}`),

  // Activate user identity
  activateIdentity: (id) => apiClient.post(`/identity/${id}/activate`),

  // Suspend user identity with audit reason
  suspendIdentity: (id, reason) => apiClient.post(`/identity/${id}/suspend`, { reason }),

  // Get identity lifecycle timeline audit trail
  getIdentityTimeline: (id) => apiClient.get(`/identity/${id}/timeline`),

  // Get employment record details
  getEmploymentRecord: (id) => apiClient.get(`/employment/${id}`),

  // Hire employee record
  hireEmployee: (id, data) => apiClient.post(`/employment/${id}/hire`, data),

  // Transfer employee
  transferEmployee: (id, data) => apiClient.post(`/employment/${id}/transfer`, data),

  // Promote employee
  promoteEmployee: (id, data) => apiClient.post(`/employment/${id}/promote`, data),

  // Biometric face enrollment
  enrollFace: async (userId, fileOrEmbedding) => {
    if (fileOrEmbedding instanceof File) {
      const formData = new FormData();
      formData.append("file", fileOrEmbedding);
      return apiClient.post(`/users/${userId}/enroll-face`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    }
    return apiClient.post(`/users/${userId}/enroll`, { image_base64: fileOrEmbedding });
  },

  // Enrollment capture registered with a user's biometric template. Fetched as
  // a blob because the endpoint is JWT-protected and cannot be a plain <img src>.
  getFacePhoto: (userId) =>
    apiClient.get(`/users/${userId}/face-photo`, { responseType: 'blob' }),

  // Cached object URLs keyed by user id; avoids re-fetching the same capture
  // for every list render. Misses are not cached so a later enrollment shows up.
  //
  // In-flight requests are de-duplicated separately. The attendance feed mounts
  // an avatar per row, so one employee appearing in several rows (or React
  // re-running the effect) previously issued the same request several times —
  // a miss is not cached, so every one of those was a real round trip.
  async getFacePhotoUrl(userId) {
    if (!userId) return null;
    if (facePhotoUrlCache.has(userId)) return facePhotoUrlCache.get(userId);
    if (facePhotoInFlight.has(userId)) return facePhotoInFlight.get(userId);

    const request = (async () => {
      try {
        // This endpoint is refused for anyone but the subject and holders of
        // `users.update`. Callers check first; suppressing the toast as well means
        // a permission that changes mid-session degrades to initials instead of
        // painting an error over the dashboard.
        const res = await apiClient.get(`/users/${userId}/face-photo`, {
          responseType: 'blob',
          suppressForbiddenToast: true,
        });
        const url = URL.createObjectURL(new Blob([res.data], { type: res.headers?.['content-type'] || 'image/jpeg' }));
        facePhotoUrlCache.set(userId, url);
        return url;
      } catch (err) {
        return null;
      } finally {
        facePhotoInFlight.delete(userId);
      }
    })();

    facePhotoInFlight.set(userId, request);
    return request;
  },

  clearFacePhotoCache(userId) {
    if (userId == null) return;
    const url = facePhotoUrlCache.get(userId);
    if (url) {
      URL.revokeObjectURL(url);
      facePhotoUrlCache.delete(userId);
    }
  },
};

export default userService;
