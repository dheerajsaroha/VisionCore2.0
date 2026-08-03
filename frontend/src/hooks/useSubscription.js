import { useEffect, useCallback } from 'react';
import { useSubscriptionStore } from '../store/subscriptionStore';

/**
 * useSubscription — Frontend Subscription & Feature Access Hook
 *
 * Provides feature-level authorization checks backed by the Subscription Store.
 * Replaces all hardcoded subscription checks in the frontend.
 *
 * Usage:
 *   const { hasFeature, planTier, isEnterprise, isLoading } = useSubscription();
 *
 *   if (hasFeature('asset_management')) { ... }
 *   if (isEnterprise()) { ... }
 */
export function useSubscription() {
  const store = useSubscriptionStore();

  // Hydrate subscription on mount if not already cached
  useEffect(() => {
    if (!store.isCacheHydrated && !store.isLoading) {
      store.fetchMySubscription();
    }
  }, [store.isCacheHydrated, store.isLoading, store.fetchMySubscription]);

  /**
   * Check if a feature is enabled for the current organization.
   * Falls back to subscription store state.
   */
  const hasFeature = useCallback(
    (featureCode) => {
      if (!featureCode) return true; // No feature required
      return store.hasFeature(featureCode);
    },
    [store]
  );

  /**
   * Check if ALL specified features are enabled.
   */
  const hasAllFeatures = useCallback(
    (...featureCodes) => {
      if (featureCodes.length === 0) return true;
      return store.hasAllFeatures(...featureCodes);
    },
    [store]
  );

  /**
   * Check if ANY of the specified features are enabled.
   */
  const hasAnyFeature = useCallback(
    (...featureCodes) => {
      if (featureCodes.length === 0) return true;
      return store.hasAnyFeature(...featureCodes);
    },
    [store]
  );

  /**
   * Check subscription tier level.
   */
  const isEnterprise = useCallback(() => store.isEnterprise(), [store]);
  const isProfessional = useCallback(() => store.isProfessional(), [store]);
  const isStarter = useCallback(() => store.isStarter(), [store]);
  const isOnTrial = useCallback(() => store.isOnTrial(), [store]);
  const isActive = useCallback(() => store.isActive(), [store]);

  /**
   * Check licensing limits.
   */
  const getLimit = useCallback(
    (limitType) => store.getLimit(limitType),
    [store]
  );

  const isLimitExceeded = useCallback(
    (limitType, currentUsage) => store.isLimitExceeded(limitType, currentUsage),
    [store]
  );

  return {
    // Feature checks
    hasFeature,
    hasAllFeatures,
    hasAnyFeature,

    // Tier checks
    isEnterprise,
    isProfessional,
    isStarter,
    isOnTrial,
    isActive,

    // Licensing limits
    getLimit,
    isLimitExceeded,

    // Raw data
    planName: store.planName,
    planCode: store.planCode,
    planTier: store.planTier,
    status: store.status,
    billingCycle: store.billingCycle,
    enabledFeatures: store.enabledFeatures,
    featureCount: store.featureCount,
    limits: store.limits,
    usageStats: store.usageStats,
    isLoading: store.isLoading && !store.isCacheHydrated,
    isHydrated: store.isCacheHydrated,
    error: store.error,

    // Refresh
    refresh: store.fetchMySubscription,
  };
}

/**
 * useFeature — Simplified hook that returns boolean directly.
 *
 * Usage:
 *   const canUseAssets = useFeature('asset_management');
 *   if (canUseAssets) { ... }
 */
export function useFeature(featureCode) {
  const { hasFeature, isLoading } = useSubscription();

  if (isLoading || !featureCode) return false;
  return hasFeature(featureCode);
}

/**
 * useRequireFeature — Imperative check that returns { allowed, reason }.
 *
 * Usage:
 *   const { allowed, reason } = useRequireFeature('asset_management');
 *   if (!allowed) return <UpgradeRequired reason={reason} />;
 */
export function useRequireFeature(featureCode) {
  const { hasFeature, isLoading, isHydrated, planName, planTier } = useSubscription();

  if (isLoading || !isHydrated) {
    return { allowed: false, reason: 'loading' };
  }

  if (!featureCode) {
    return { allowed: true, reason: null };
  }

  const allowed = hasFeature(featureCode);
  return {
    allowed,
    reason: allowed
      ? null
      : `Feature "${featureCode}" is not available on your ${planName || 'current'} plan. Please upgrade to access this feature.`,
  };
}
