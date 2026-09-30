import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '../services/apiClient';

const API_BASE = '/subscription';

/**
 * Subscription Store — Manages the current user's organization subscription
 *
 * Features:
 * - Fetches and caches the organization's subscription plan & features
 * - Provides feature-level access checks
 * - Handles loading/error states
 * - Auto-invalidates on logout
 */
export const useSubscriptionStore = create(
  persist(
    (set, get) => ({
      // Subscription plan
      plan: null,
      planName: '',
      planCode: '',
      planTier: 0,
      status: '',
      billingCycle: '',
      startDate: null,
      endDate: null,
      autoRenew: false,

      // Enabled features (cached as Set for O(1) lookup)
      enabledFeatures: [],
      enabledFeatureSet: new Set(),
      featureCount: 0,

      // Feature flags (per-org overrides)
      featureFlags: {},

      // Licensing limits & usage
      limits: [],
      usageStats: null,

      // UI States
      isLoading: false,
      isCacheHydrated: false,
      // Two separate flags, because "have we finished asking?" and "did the
      // answer come back?" are different questions and need different handling:
      //   featuresResolved  - the lookup has settled, one way or the other.
      //                       Governs whether gated UI should wait.
      //   featuresAvailable - the plan's feature list is authoritative.
      //                       Governs whether the set can be trusted to deny.
      featuresResolved: false,
      featuresAvailable: false,
      error: null,

      // ── Fetch Subscription ──────────────────────────────────────────────

      fetchMySubscription: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.get(`${API_BASE}/my/subscription`);
          const data = response.data;

          const plan = data.plan || null;
          const enabledFeatures = data.enabled_features || [];

          set({
            plan,
            planName: data.plan_name || '',
            planCode: plan?.code || '',
            planTier: plan?.tier || 0,
            status: data.status || '',
            billingCycle: data.billing_cycle || '',
            startDate: data.start_date || null,
            endDate: data.end_date || null,
            autoRenew: data.auto_renew || false,
            enabledFeatures,
            enabledFeatureSet: new Set(enabledFeatures),
            featureCount: enabledFeatures.length,
            limits: plan?.limits || [],
            usageStats: data.usage_stats || null,
            isLoading: false,
            isCacheHydrated: true,
            featuresResolved: true,
            featuresAvailable: true,
          });
          return data;
        } catch (error) {
          set({
            isLoading: false,
            isCacheHydrated: true,
            // Settled, but the answer is unknown — not "the plan lacks these".
            // Gated UI must stop waiting (otherwise it would block forever), and
            // must not trust the empty set to deny. The API stays authoritative,
            // so failing open only means the backend gets the final say.
            featuresResolved: true,
            featuresAvailable: false,
            error: error.response?.data?.detail || error.message || 'Failed to load subscription',
          });
          return null;
        }
      },

      // ── Check Feature Access ────────────────────────────────────────────

      /**
       * Check if a feature is enabled for the current organization.
       * Uses cached data first, then falls back to API check.
       */
      hasFeature: (featureCode) => {
        if (!featureCode) return true;
        const { enabledFeatureSet, featureFlags, featuresAvailable } = get();

        // Check feature flags first (org-level overrides). An override is
        // authoritative even when the plan lookup failed.
        if (featureFlags[featureCode] !== undefined) {
          return featureFlags[featureCode];
        }

        if (featuresAvailable) {
          return enabledFeatureSet.has(featureCode);
        }

        // Still loading, or the lookup failed. Do not assert the plan lacks the
        // feature: that produced a false "Not included in your plan" on the
        // attendance page, which was both wrong and locked the user out. Allow
        // the item to render and let the API refuse it authoritatively.
        return true;
      },

      /**
       * Check if ALL specified features are enabled.
       */
      hasAllFeatures: (...featureCodes) => {
        if (featureCodes.length === 0) return true;
        const { hasFeature } = get();
        return featureCodes.every((fc) => hasFeature(fc));
      },

      /**
       * Check if ANY of the specified features are enabled.
       */
      hasAnyFeature: (...featureCodes) => {
        if (featureCodes.length === 0) return true;
        const { hasFeature } = get();
        return featureCodes.some((fc) => hasFeature(fc));
      },

      // ── Remote Feature Check ────────────────────────────────────────────

      checkFeatureAccess: async (featureCode) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.get(`${API_BASE}/check/${featureCode}`);
          const result = response.data;

          // Update cache with result
          const { featureFlags } = get();
          featureFlags[featureCode] = result.allowed;

          set({
            featureFlags: { ...featureFlags },
            isLoading: false,
          });

          return result;
        } catch (error) {
          set({
            isLoading: false,
            error: error.response?.data?.detail || error.message,
          });
          return { allowed: false, reason: 'API error' };
        }
      },

      // ── Subscription Tier Checks ────────────────────────────────────────

      isEnterprise: () => {
        const { planTier } = get();
        return planTier >= 3;
      },

      isProfessional: () => {
        const { planTier } = get();
        return planTier >= 2;
      },

      isStarter: () => {
        const { planTier } = get();
        return planTier >= 1;
      },

      isOnTrial: () => {
        const { status } = get();
        return status === 'trialing';
      },

      isActive: () => {
        const { status } = get();
        return status === 'active' || status === 'trialing';
      },

      // ── Licensing Limits ────────────────────────────────────────────────

      getLimit: (limitType) => {
        const { limits } = get();
        return limits.find((l) => l.limit_type === limitType) || null;
      },

      isLimitExceeded: (limitType, currentUsage) => {
        const limit = get().getLimit(limitType);
        if (!limit || limit.is_unlimited) return false;
        return currentUsage >= limit.hard_limit;
      },

      // ── Reset ───────────────────────────────────────────────────────────

      reset: () => {
        set({
          plan: null,
          planName: '',
          planCode: '',
          planTier: 0,
          status: '',
          billingCycle: '',
          startDate: null,
          endDate: null,
          autoRenew: false,
          enabledFeatures: [],
          enabledFeatureSet: new Set(),
          featureCount: 0,
          featureFlags: {},
          limits: [],
          usageStats: null,
          isLoading: false,
          error: null,
        });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'subscription-storage',
      partialize: (state) => ({
        planName: state.planName,
        planCode: state.planCode,
        planTier: state.planTier,
        status: state.status,
        enabledFeatures: state.enabledFeatures,
        featureCount: state.featureCount,
        limits: state.limits,
        isCacheHydrated: state.isCacheHydrated,
      }),
    }
  )
);
