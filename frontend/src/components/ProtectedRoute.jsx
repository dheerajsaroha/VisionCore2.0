import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Lock, CreditCard, ArrowLeft } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { DashboardSkeleton } from './SkeletonLoader';
import { canAccess, resolvePolicy, accessReasons } from '../lib/accessControl';

/**
 * The denial panel shown in place of a module the user may not open.
 *
 * Rendered inside the dashboard shell rather than redirected to, so the user
 * keeps their navigation and, more importantly, is told *why*: "ask an
 * administrator" and "not in your plan" are different problems with different
 * fixes, and collapsing both into a generic 403 is what made this feel broken.
 */
const AccessNotice = ({ reason, missing, onBack }) => {
  const isFeature = reason === accessReasons.FEATURE;

  const config = isFeature
    ? {
        icon: CreditCard,
        title: 'Not included in your plan',
        body: `This area needs the "${missing}" feature, which your organization’s current subscription does not include. An administrator can upgrade the plan to enable it.`,
        accent: 'text-amber-400',
        ring: 'border-amber-500/30 bg-amber-500/5',
      }
    : {
        icon: Lock,
        title: 'You do not have access to this area',
        body: `This area requires the "${missing}" permission. An administrator can grant it to your role.`,
        accent: 'text-indigo-400',
        ring: 'border-indigo-500/30 bg-indigo-500/5',
      };

  const Icon = config.icon;

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className={`w-full max-w-md rounded-2xl border p-8 text-center ${config.ring}`}>
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gray-800/60">
          <Icon className={`h-7 w-7 ${config.accent}`} />
        </div>
        <h1 className="mt-5 text-xl font-semibold text-white">{config.title}</h1>
        <p className="mt-3 text-sm leading-relaxed text-gray-400">{config.body}</p>
        <button
          type="button"
          onClick={onBack}
          className="mt-6 inline-flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition hover:bg-gray-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </button>
      </div>
    </div>
  );
};

/**
 * ProtectedRoute - Guards routes on authentication, RBAC permission, and plan
 * feature.
 *
 * The gate is resolved from the single policy table in `lib/accessControl.js`
 * (with an explicit `requiredPermission`/`requiredFeature` prop still
 * overriding it), so the route guard and the sidebar can no longer disagree
 * about what a user may open.
 *
 * A denial renders in place instead of redirecting, preserving the shell and
 * explaining whether an administrator or a plan upgrade is the fix.
 */
export const ProtectedRoute = ({
  children,
  requiredRole,
  requiredRoles,
  requiredPermission,
  requiredFeature,
  redirectTo = '/login',
  fallbackPath = null,
}) => {
  const { isAuthenticated, user, isHydrated: authHydrated, authorizationInitialized } = useAuthStore();
  const { hasPermission, hasFeature, isHydrated: permHydrated, isLoading: permLoading, featuresResolved } = usePermission();
  const location = useLocation();

  const policy = resolvePolicy(location.pathname);
  const effectivePermission = requiredPermission || policy?.permission;
  const effectiveFeature = requiredFeature || policy?.feature;
  const needsAuthorization = Boolean(effectivePermission || effectiveFeature);
  // A feature-gated route must not be evaluated until the plan's feature list is
  // known. Otherwise a slow subscription request reads as an empty feature set,
  // and the guard renders "Not included in your plan" for a plan that does
  // include it. The permission check alone is safe to run early.
  const needsFeatures = Boolean(effectiveFeature);

  // Show loading while auth state is being restored
  if (
    !authHydrated ||
    (isAuthenticated && needsAuthorization && (!authorizationInitialized || permLoading || !permHydrated)) ||
    (isAuthenticated && needsFeatures && !featuresResolved)
  ) {
    return <DashboardSkeleton />;
  }

  // Redirect unauthenticated users
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // ── Permission + feature gate ───────────────────────────────────────
  const verdict = canAccess(
    { permission: effectivePermission, feature: effectiveFeature },
    { hasPermission, hasFeature, isAuthenticated }
  );

  if (!verdict.allowed) {
    // An explicit fallback path still wins, for callers that want a redirect.
    if (fallbackPath) {
      return <Navigate to={fallbackPath} replace />;
    }
    return (
      <AccessNotice
        reason={verdict.reason}
        missing={verdict.missing}
        onBack={() => window.history.back()}
      />
    );
  }

  // ── Role-based check (Legacy / Fallback) ─────────────────────────────
  const allowedRoles = requiredRoles || (requiredRole ? [requiredRole] : null);
  if (allowedRoles) {
    const userRole = user?.role?.name || user?.role;
    if (!allowedRoles.includes(userRole)) {
      if (fallbackPath) {
        return <Navigate to={fallbackPath} replace />;
      }
      return (
        <AccessNotice
          reason={accessReasons.PERMISSION}
          missing={userRole || 'a different role'}
          onBack={() => window.history.back()}
        />
      );
    }
  }

  return children;
};

/**
 * PermissionRoute — Alias for ProtectedRoute with permission-based access.
 */
export const PermissionRoute = ({ permission, feature, children, ...props }) => (
  <ProtectedRoute
    requiredPermission={permission}
    requiredFeature={feature}
    {...props}
  >
    {children}
  </ProtectedRoute>
);

export default ProtectedRoute;
