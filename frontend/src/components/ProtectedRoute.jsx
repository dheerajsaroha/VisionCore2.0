import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { DashboardSkeleton } from './SkeletonLoader';
import { permissionForPath } from '../lib/routeAuthorization';

/**
 * ProtectedRoute - Guards routes based on authentication, permissions, and features.
 *
 * @param {React.ReactNode} children - The component to render if authorized
 * @param {string} requiredRole - (DEPRECATED) Legacy role-based check — use requiredPermission instead
 * @param {string[]} requiredRoles - Optional list of allowed roles
 * @param {string} requiredPermission - Permission required to access this route
 * @param {string} requiredFeature - Feature flag required (e.g., 'payroll', 'recruitment')
 * @param {string} redirectTo - Where to redirect on auth failure (default: /login)
 * @param {string} fallbackPath - Where to redirect on permission failure (default: /dashboard)
 */
export const ProtectedRoute = ({
  children,
  requiredRole,
  requiredRoles,
  requiredPermission,
  requiredFeature,
  redirectTo = '/login',
  fallbackPath = '/403',
}) => {
  const { isAuthenticated, user, isHydrated: authHydrated, authorizationInitialized } = useAuthStore();
  const { hasPermission, hasFeature, isHydrated: permHydrated, isLoading: permLoading } = usePermission();
  const location = useLocation();
  const routePermission = requiredPermission || permissionForPath(location.pathname);

  // Show loading while auth state is being restored
  if (!authHydrated || (isAuthenticated && routePermission && (!authorizationInitialized || permLoading || !permHydrated))) {
    return <DashboardSkeleton />;
  }

  // Redirect unauthenticated users
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // ── Permission-based check ──────────────────────────────────────────
  if (routePermission) {
    if (!hasPermission(routePermission)) {
      return <Navigate to={fallbackPath} replace />;
    }
  }

  // ── Feature-based check ────────────────────────────────────────────
  if (requiredFeature) {
    if (!hasFeature(requiredFeature)) {
      return <Navigate to={fallbackPath} replace />;
    }
  }

  // ── Role-based check (Legacy / Fallback) ──────────────────────────────────
  const allowedRoles = requiredRoles || (requiredRole ? [requiredRole] : null);
  if (allowedRoles) {
    const userRole = user?.role?.name || user?.role;
    if (!allowedRoles.includes(userRole)) {
      return <Navigate to={fallbackPath} replace />;
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
