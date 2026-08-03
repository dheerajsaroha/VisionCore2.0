import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { permissionService } from '../services/permissionService';

/**
 * Permission Store — Manages permission data and user permission cache
 *
 * Features:
 * - Fetches and caches the current user's effective permissions
 * - Caches all permissions for the admin management UI
 * - Handles loading/error states
 * - Provides bulk operations for role-permission management
 */
export const usePermissionStore = create(
  persist(
    (set, get) => ({
      // Current user's effective permissions
      myPermissions: [],
      myPermissionCount: 0,
      myRoleName: '',

      // Permission catalogue (for admin management)
      permissions: [],
      totalPermissions: 0,

      // Module statistics
      moduleStats: [],
      moduleSummary: [],

      // UI States
      isLoading: false,
      isCacheHydrated: false,
      error: null,

      // ── My Permissions ──────────────────────────────────────────────────

      fetchMyPermissions: async () => {
        try {
          const data = await permissionService.getMyPermissions();
          set({
            myPermissions: data.permissions || [],
            myPermissionCount: data.permission_count || 0,
            myRoleName: data.role_name || '',
            isCacheHydrated: true,
          });
          return data;
        } catch (error) {
          set({ error: error.message, isCacheHydrated: true });
          return null;
        }
      },

      hasPermission: (permission) => {
        const { myPermissions } = get();
        return myPermissions.includes(permission);
      },

      hasAnyPermission: (...permissions) => {
        const { myPermissions } = get();
        const userSet = new Set(myPermissions);
        return permissions.some((p) => userSet.has(p));
      },

      hasAllPermissions: (...permissions) => {
        const { myPermissions } = get();
        const userSet = new Set(myPermissions);
        return permissions.every((p) => userSet.has(p));
      },

      // ── Permission Catalogue ────────────────────────────────────────────

      fetchPermissions: async (params = {}) => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.list(params);
          set({
            permissions: data.permissions || [],
            totalPermissions: data.total || 0,
            isLoading: false,
          });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      // ── Module Statistics ──────────────────────────────────────────────

      fetchModuleStats: async () => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.getModuleStats();
          set({
            moduleStats: data.modules || [],
            isLoading: false,
          });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      fetchModuleSummary: async () => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.getModuleSummary();
          set({
            moduleSummary: data.modules || [],
            isLoading: false,
          });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      // ── Bulk Operations ────────────────────────────────────────────────

      bulkAssign: async (roleId, permissionIds) => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.bulkAssign(roleId, permissionIds);
          set({ isLoading: false });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      bulkRemove: async (roleId, permissionIds) => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.bulkRemove(roleId, permissionIds);
          set({ isLoading: false });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      // ── Activation / Deactivation ──────────────────────────────────────

      setPermissionStatus: async (id, isActive) => {
        set({ isLoading: true, error: null });
        try {
          const data = await permissionService.setStatus(id, isActive);
          set({ isLoading: false });
          // Refresh permissions after status change
          get().fetchPermissions();
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      // ── CRUD ───────────────────────────────────────────────────────────

      createPermission: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const result = await permissionService.create(data);
          set({ isLoading: false });
          get().fetchPermissions();
          return result;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      updatePermission: async (id, data) => {
        set({ isLoading: true, error: null });
        try {
          const result = await permissionService.update(id, data);
          set({ isLoading: false });
          get().fetchPermissions();
          return result;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return null;
        }
      },

      deletePermission: async (id) => {
        set({ isLoading: true, error: null });
        try {
          await permissionService.delete(id);
          set({ isLoading: false });
          get().fetchPermissions();
          return true;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          return false;
        }
      },

      // ── Reset ──────────────────────────────────────────────────────────

      reset: () => {
        set({
          myPermissions: [],
          myPermissionCount: 0,
          myRoleName: '',
          permissions: [],
          totalPermissions: 0,
          moduleStats: [],
          moduleSummary: [],
          isLoading: false,
          error: null,
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'permission-storage',
      partialize: (state) => ({
        myPermissions: state.myPermissions,
        myPermissionCount: state.myPermissionCount,
        myRoleName: state.myRoleName,
        isCacheHydrated: state.isCacheHydrated,
      }),
    }
  )
);

