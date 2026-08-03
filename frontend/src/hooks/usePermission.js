import { useEffect, useCallback } from 'react';
import { usePermissionStore } from '../store/permissionStore';
import { useSubscriptionStore } from '../store/subscriptionStore';
import { useAuthStore } from '../store/authStore';
import { apiClient } from '../services/apiClient';

/**
 * usePermission — Frontend Authorization Hook
 *
 * Provides permission-aware, feature-aware, scope-aware, and ownership-aware
 * authorization for React components. Integrated with EAAC pipeline.
 *
 * Usage:
 *   const { hasPermission, hasFeature, isLoading } = usePermission();
 *
 *   if (hasPermission('asset.create')) { ... }
 *   if (hasFeature('asset_management')) { ... }
 */
export function usePermission() {
  const permStore = usePermissionStore();
  const subStore = useSubscriptionStore();
  const authStore = useAuthStore();

  // Hydrate permissions + subscription on mount if not already cached
  useEffect(() => {
    if (!permStore.isCacheHydrated && !permStore.isLoading) {
      permStore.fetchMyPermissions();
    }
    if (!subStore.isCacheHydrated && !subStore.isLoading) {
      subStore.fetchMySubscription();
    }
  }, [
    permStore, permStore.isCacheHydrated, permStore.isLoading, permStore.fetchMyPermissions,
    subStore, subStore.isCacheHydrated, subStore.isLoading, subStore.fetchMySubscription,
  ]);

  /**
   * Check if the current user has a specific permission.
   */
  const hasPermission = useCallback(
    (permissionName) => {
      if (!permissionName) return true;
      return permStore.hasPermission(permissionName);
    },
    [permStore]
  );

  /**
   * Check if the current user has ANY of the specified permissions.
   */
  const hasAnyPermission = useCallback(
    (...permissionNames) => {
      if (permissionNames.length === 0) return true;
      return permStore.hasAnyPermission(...permissionNames);
    },
    [permStore]
  );

  /**
   * Check if the current user has ALL of the specified permissions.
   */
  const hasAllPermissions = useCallback(
    (...permissionNames) => {
      if (permissionNames.length === 0) return true;
      return permStore.hasAllPermissions(...permissionNames);
    },
    [permStore]
  );

  /**
   * Check if a feature is enabled for the current organization.
   * Delegates to subscription store for cached feature access.
   */
  const hasFeature = useCallback(
    (featureKey) => {
      if (!featureKey) return true;
      return subStore.hasFeature(featureKey);
    },
    [subStore]
  );

  /**
   * Check if the user has a minimum data scope level.
   * Evaluates based on the user's role and organization context.
   */
  const hasScope = useCallback(
    (minScope) => {
      if (!minScope) return true;
      // SuperAdmin has all scopes
      if (permStore.myRoleName === 'SuperAdmin') return true;
      // OrgAdmin has org-wide scope
      if (permStore.myRoleName === 'OrgAdmin') return true;
      // Department heads have department scope
      if (permStore.myRoleName === 'OrgDepartmentHead' && minScope === 'department') return true;
      // Team leads have team scope
      if (permStore.myRoleName === 'OrgTeamLead' && minScope === 'team') return true;
      // Employees have self scope
      if (minScope === 'self') return true;
      // Default: check if user has the 'scope.all' permission
      if (permStore.hasPermission('scope.all')) return true;
      return false;
    },
    [permStore]
  );

  /**
   * Check if the user owns a specific resource.
   * Calls the EAAC ownership endpoint for verification.
   */
  const ownsResource = useCallback(
    async (resourceType, resourceId) => {
      if (!resourceType || !resourceId) return true;

      try {
        const response = await apiClient.get(
          `/scope/ownership/check`,
          {
            params: {
              resource_type: resourceType,
              resource_id: resourceId,
            },
          }
        );
        return response.data?.is_owner === true;
      } catch {
        // On API failure, fall back to checking if user's ID matches
        const currentUser = authStore.user;
        if (currentUser && resourceType === 'user') {
          return String(currentUser.id) === String(resourceId);
        }
        return false;
      }
    },
    [authStore.user]
  );

  /**
   * Check if the user is an authorized approver for a workflow type.
   * Calls the EAAC approval workflow engine.
   */
  const canApprove = useCallback(
    async (workflowType, resourceId) => {
      if (!workflowType) return false;

      try {
        const response = await apiClient.get(
          `/workflow/can-approve`,
          {
            params: {
              workflow_type: workflowType,
              resource_id: resourceId,
            },
          }
        );
        return response.data?.can_approve === true;
      } catch {
        return false;
      }
    },
    []
  );

  return {
    // Permission checks
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,

    // Feature, scope, ownership, approval
    hasFeature,
    hasScope,
    ownsResource,
    canApprove,

    // Raw data
    permissions: permStore.myPermissions,
    permissionCount: permStore.myPermissionCount,
    roleName: permStore.myRoleName,
    isLoading: permStore.isLoading && !permStore.isCacheHydrated,
    isHydrated: permStore.isCacheHydrated,
    error: permStore.error,

    // Subscription
    planTier: subStore.planTier,
    planName: subStore.planName,

    // Refresh
    refresh: permStore.fetchMyPermissions,
    refreshSubscription: subStore.fetchMySubscription,
  };
}

/**
 * useHasPermission — Simplified hook that returns boolean directly.
 *
 * Usage:
 *   const canCreateUsers = useHasPermission('users.create');
 *   if (canCreateUsers) { ... }
 */
export function useHasPermission(permissionName) {
  const { hasPermission, isLoading } = usePermission();

  if (isLoading || !permissionName) return false;
  return hasPermission(permissionName);
}

/**
 * useRequirePermission — Imperative check that returns { allowed, reason }.
 *
 * Usage:
 *   const { allowed, reason } = useRequirePermission('users.create');
 *   if (!allowed) return <AccessDenied reason={reason} />;
 */
export function useRequirePermission(permissionName) {
  const { hasPermission, isLoading, isHydrated } = usePermission();

  if (isLoading || !isHydrated) {
    return { allowed: false, reason: 'loading' };
  }

  if (!permissionName) {
    return { allowed: true, reason: null };
  }

  const allowed = hasPermission(permissionName);
  return {
    allowed,
    reason: allowed ? null : `Missing required permission: ${permissionName}`,
  };
}
