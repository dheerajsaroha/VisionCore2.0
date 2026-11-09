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
  const isCacheHydrated = useSubscriptionStore((state) => state.isCacheHydrated);
  const isLoadingState = useSubscriptionStore((state) => state.isLoading);
  const fetchMySubscription = useSubscriptionStore((state) => state.fetchMySubscription);
  const hasFeatureForOrg = useSubscriptionStore((state) => state.hasFeature);
  const hasAllFeaturesForOrg = useSubscriptionStore((state) => state.hasAllFeatures);
  const hasAnyFeatureForOrg = useSubscriptionStore((state) => state.hasAnyFeature);
  const isEnterpriseForOrg = useSubscriptionStore((state) => state.isEnterprise);
  const isProfessionalForOrg = useSubscriptionStore((state) => state.isProfessional);
  const isStarterForOrg = useSubscriptionStore((state) => state.isStarter);
  const isOnTrialForOrg = useSubscriptionStore((state) => state.isOnTrial);
  const isActiveForOrg = useSubscriptionStore((state) => state.isActive);
  const getLimitForOrg = useSubscriptionStore((state) => state.getLimit);
  const isLimitExceededForOrg = useSubscriptionStore((state) => state.isLimitExceeded);
  const planName = useSubscriptionStore((state) => state.planName);
  const planCode = useSubscriptionStore((state) => state.planCode);
  const planTier = useSubscriptionStore((state) => state.planTier);
  const status = useSubscriptionStore((state) => state.status);
  const billingCycle = useSubscriptionStore((state) => state.billingCycle);
  const enabledFeatures = useSubscriptionStore((state) => state.enabledFeatures);
  const featureCount = useSubscriptionStore((state) => state.featureCount);
  const limits = useSubscriptionStore((state) => state.limits);
  const usageStats = useSubscriptionStore((state) => state.usageStats);
  const error = useSubscriptionStore((state) => state.error);

  // Hydrate subscription on mount if not already cached
  useEffect(() => {
    if (!isCacheHydrated && !isLoadingState) {
      fetchMySubscription();
    }
  }, [isCacheHydrated, isLoadingState, fetchMySubscription]);

  /**
   * Check if a feature is enabled for the current organization.
   * Falls back to subscription store state.
   */
  const hasFeature = useCallback(
    (featureCode) => {
      if (!featureCode) return true; // No feature required
      return hasFeatureForOrg(featureCode);
    },
    [hasFeatureForOrg]
  );

  /**
   * Check if ALL specified features are enabled.
   */
  const hasAllFeatures = useCallback(
    (...featureCodes) => {
      if (featureCodes.length === 0) return true;
      return hasAllFeaturesForOrg(...featureCodes);
    },
    [hasAllFeaturesForOrg]
  );

  /**
   * Check if ANY of the specified features are enabled.
   */
  const hasAnyFeature = useCallback(
    (...featureCodes) => {
      if (featureCodes.length === 0) return true;
      return hasAnyFeatureForOrg(...featureCodes);
    },
    [hasAnyFeatureForOrg]
  );

  /**
   * Check subscription tier level.
   */
  const isEnterprise = useCallback(() => isEnterpriseForOrg(), [isEnterpriseForOrg]);
  const isProfessional = useCallback(() => isProfessionalForOrg(), [isProfessionalForOrg]);
  const isStarter = useCallback(() => isStarterForOrg(), [isStarterForOrg]);
  const isOnTrial = useCallback(() => isOnTrialForOrg(), [isOnTrialForOrg]);
  const isActive = useCallback(() => isActiveForOrg(), [isActiveForOrg]);

  /**
   * Check licensing limits.
   */
  const getLimit = useCallback(
    (limitType) => getLimitForOrg(limitType),
    [getLimitForOrg]
  );

  const isLimitExceeded = useCallback(
    (limitType, currentUsage) => isLimitExceededForOrg(limitType, currentUsage),
    [isLimitExceededForOrg]
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
    planName,
    planCode,
    planTier,
    status,
    billingCycle,
    enabledFeatures,
    featureCount,
    limits,
    usageStats,
    isLoading: isLoadingState && !isCacheHydrated,
    isHydrated: isCacheHydrated,
    error,

    // Refresh
    refresh: fetchMySubscription,
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
  const { hasFeature, isLoading, isHydrated, planName } = useSubscription();

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
