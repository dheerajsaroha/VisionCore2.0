import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { DashboardSkeleton } from './SkeletonLoader';

/**
 * ProtectedRoute - Guards routes based on authentication, permissions, and features.
 *
 * @param {React.ReactNode} children - The component to render if authorized
 * @param {string} requiredRole - (DEPRECATED) Legacy role-based check — use requiredPermission instead
 * @param {string} requiredPermission - Permission required to access this route
 * @param {string} requiredFeature - Feature flag required (e.g., 'payroll', 'recruitment')
 * @param {string} redirectTo - Where to redirect on auth failure (default: /login)
 * @param {string} fallbackPath - Where to redirect on permission failure (default: /dashboard)
 *
 * Usage:
 *   <ProtectedRoute requiredPermission="users.read">
 *     <UserManagement />
 *   </ProtectedRoute>
 *
 *   <ProtectedRoute requiredFeature="payroll" requiredPermission="payroll.read">
 *     <Payroll />
 *   </ProtectedRoute>
 *
 * NOTE: requiredRole is DEPRECATED. Migrate to requiredPermission.
 */
export const ProtectedRoute = ({
  children,
  requiredRole,
  requiredPermission,
  requiredFeature,
  redirectTo = '/login',
  fallbackPath = '/dashboard',
}) => {
  const { isAuthenticated, user, isHydrated: authHydrated } = useAuthStore();
  const { hasPermission, hasFeature, isHydrated: permHydrated, isLoading: permLoading } = usePermission();
  const location = useLocation();

  // Show loading while auth state is being restored
  if (!authHydrated || (requiredPermission && permLoading)) {
    return <DashboardSkeleton />;
  }

  // Redirect unauthenticated users
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // ── NEW: Permission-based check ──────────────────────────────────────────
  if (requiredPermission) {
    if (!permHydrated) {
      return <DashboardSkeleton />;
    }

    if (!hasPermission(requiredPermission)) {
      return <Navigate to={fallbackPath} replace />;
    }
  }

  // ── NEW: Feature-based check ────────────────────────────────────────────
  if (requiredFeature) {
    if (!hasFeature(requiredFeature)) {
      return <Navigate to={fallbackPath} replace />;
    }
  }

  // ── DEPRECATED: Legacy role-based check ──────────────────────────────────
  if (requiredRole) {
    const userRole = user?.role?.name;
    const allowedRoles = requiredRole === 'Admin'
      ? ['Admin', 'Manager', 'SuperAdmin']
      : [requiredRole];

    if (!allowedRoles.includes(userRole)) {
      return <Navigate to={fallbackPath} replace />;
    }
  }

  return children;
};

/**
 * PermissionRoute — Alias for ProtectedRoute with permission-based access.
 *
 * Usage:
 *   <PermissionRoute permission="users.read" feature="attendance">
 *     <UsersPage />
 *   </PermissionRoute>
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

