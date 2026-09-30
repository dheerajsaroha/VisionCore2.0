/**
 * Access control — the single source of truth for "may this user see this?".
 *
 * There are two independent gates, and a user must pass BOTH:
 *
 *   1. permission — an RBAC grant from the caller's role (e.g. `payroll.generate`).
 *      Admin/senior can grant or revoke these at runtime, so the answer changes
 *      without a re-login.
 *   2. feature    — an entitlement from the organization's subscription plan
 *      (e.g. `payroll`). This is NOT a permission: a tenant can hold every
 *      payroll permission and still be 402'd by the backend.
 *
 * The UI previously had three independent gate tables that disagreed with each
 * other (the nav array, the `requiredPermission` props in App.jsx, and
 * routeAuthorization.js), and no gate consulted dimension 2 at all. That is why
 * users saw navigation entries and pages they could not use, and why plan
 * upgrade messages were rendered as red error banners.
 *
 * This module replaces all three. The API remains authoritative: this is
 * presentation-layer defense in depth, not security.
 */

/**
 * Plan features that entitle whole modules, mapped to the feature code the
 * backend feature-gates on (see the `require_feature` dependency on each router
 * in backend/app/routers/).
 *
 * Only list a feature here when the backend gates the *whole* router on it.
 */
export const MODULE_FEATURES = {
  payroll: 'payroll',
  expenses: 'expenses',
  recruitment: 'recruitment',
  assets: 'assets',
  training: 'training',
  performance: 'performance_reviews',
  attendance: 'attendance',
  leave: 'leave_management',
  aiChat: 'ai_chat',
  aiFace: 'ai_face_recognition',
};

/**
 * Route policies. Every dashboard route appears here exactly once.
 *
 *   authenticated — any signed-in user
 *   permission    — RBAC grant required (absent => only `authenticated`)
 *   feature       — plan entitlement required
 */
export const routePolicies = {
  // ── Always available ──────────────────────────────────────────────────
  '/dashboard': { authenticated: true },
  '/dashboard/leave': { authenticated: true, permission: 'leave.view_self', feature: MODULE_FEATURES.leave },
  '/dashboard/settings': { authenticated: true },
  // Self-service: every employee may read their own payslips, but the payroll
  // module is plan-gated, so the feature check is what hides this for a tenant
  // without payroll rather than a permission an employee will never hold.
  '/dashboard/my-payslips': { authenticated: true, feature: MODULE_FEATURES.payroll },

  // ── Organization & identity ───────────────────────────────────────────
  '/dashboard/organization': { permission: 'org.view' },
  '/dashboard/org-hierarchy': { permission: 'org.view' },
  '/dashboard/business-units': { permission: 'departments.read' },
  '/dashboard/branches': { permission: 'org.view' },
  '/dashboard/positions': { permission: 'departments.read' },
  '/dashboard/identity-directory': { permission: 'users.read' },
  '/dashboard/users': { permission: 'users.read' },
  // HR Center is the HCM console itself, so gate it on the HCM permission the
  // route actually requires rather than on `users.read`.
  '/dashboard/hr': { permission: 'hcm.view' },

  // ── Attendance & workforce ────────────────────────────────────────────
  '/dashboard/attendance': { permission: 'attendance.history', feature: MODULE_FEATURES.attendance },
  '/dashboard/workforce/attendance': { permission: 'attendance.history', feature: MODULE_FEATURES.attendance },
  '/dashboard/workforce/timeline': { permission: 'attendance.history', feature: MODULE_FEATURES.attendance },
  '/dashboard/workforce/devices': { permission: 'platform.settings.manage' },
  '/dashboard/workforce/shifts': { permission: 'shifts.read' },
  '/dashboard/workforce/rosters': { permission: 'shifts.read' },
  '/dashboard/workforce/leave-calendar': { permission: 'attendance.history', feature: MODULE_FEATURES.leave },
  '/dashboard/workforce/leave-requests': { permission: 'attendance.history', feature: MODULE_FEATURES.leave },
  '/dashboard/workforce/holidays': { permission: 'org.settings.manage' },
  '/dashboard/workforce/planning': { permission: 'users.read' },
  '/dashboard/workforce/capacity': { permission: 'users.read' },
  '/dashboard/workforce/analytics': { permission: 'reports.attendance.export' },

  // ── HCM & growth ──────────────────────────────────────────────────────
  '/dashboard/performance': { permission: 'performance.view', feature: MODULE_FEATURES.performance },
  '/dashboard/learning': { permission: 'learning.view', feature: MODULE_FEATURES.training },
  '/dashboard/succession': { permission: 'succession.view' },
  '/dashboard/open-positions': { permission: 'recruitment.view', feature: MODULE_FEATURES.recruitment },
  '/dashboard/candidate-pipeline': { permission: 'recruitment.view', feature: MODULE_FEATURES.recruitment },

  // ── Finance ───────────────────────────────────────────────────────────
  '/dashboard/payroll': { permission: 'payroll.generate', feature: MODULE_FEATURES.payroll },
  '/dashboard/reimbursements': { permission: 'reimbursements.create', feature: MODULE_FEATURES.expenses },

  // ── Operations ────────────────────────────────────────────────────────
  '/dashboard/ticketing': { permission: 'tickets.read' },
  '/dashboard/assets': { permission: 'asset.read', feature: MODULE_FEATURES.assets },
  '/dashboard/operations': { permission: 'platform.settings.manage' },
  '/dashboard/reports': { permission: 'reports.attendance.export' },

  // ── Governance & security ─────────────────────────────────────────────
  '/dashboard/policies': { permission: 'policy.read' },
  '/dashboard/permissions': { permission: 'roles.view' },
  '/dashboard/dynamic-roles': { permission: 'roles.view' },
  // Matches the route, which is gated on `roles.view`.
  '/dashboard/approval-workflows': { permission: 'roles.view' },
  '/dashboard/scope-ownership': { permission: 'platform.settings.manage' },
  '/dashboard/enterprise': { permission: 'integration.manage' },
  '/dashboard/org-settings': { permission: 'org.settings.view' },

  // ── AI platform ───────────────────────────────────────────────────────
  '/dashboard/ai-studio': { permission: 'ai.studio.use' },
  '/dashboard/knowledge-center': { permission: 'knowledge.read' },
  '/dashboard/ai-copilot-hub': { permission: 'ai.copilot.use', feature: MODULE_FEATURES.aiChat },
  '/dashboard/ai-analytics': { permission: 'ai.analytics.read' },
  '/dashboard/prompt-manager': { permission: 'ai.prompt.manage' },
  '/dashboard/model-manager': { permission: 'ai.model.manage' },
  '/dashboard/ai-usage': { permission: 'ai.analytics.read' },
  '/dashboard/ai-governance': { permission: 'ai.governance.manage' },

  // ── Administration ────────────────────────────────────────────────────
  '/dashboard/tenant-admin': { permission: 'admin.tenant.manage' },
};

export const accessReasons = {
  PERMISSION: 'permission',
  FEATURE: 'feature',
  AUTH: 'auth',
};

export const routeAccessForPath = (path) => routePolicies[path] || null;
export const permissionForPath = (path) => routeAccessForPath(path)?.permission || null;
export const featureForPath = (path) => routeAccessForPath(path)?.feature || null;

/**
 * Resolve a path to the policy that applies to it.
 *
 * Exact match first. If a path has no policy of its own, fall back to the
 * longest registered ancestor so a nested route (e.g. a deep link) is not
 * treated as unguarded just because the exact string is absent.
 */
export const resolvePolicy = (path) => {
  if (!path) return null;
  if (routePolicies[path]) return routePolicies[path];

  let best = null;
  let bestLen = 0;
  for (const key of Object.keys(routePolicies)) {
    if (path.startsWith(`${key}/`) && key.length > bestLen) {
      best = routePolicies[key];
      bestLen = key.length;
    }
  }
  return best;
};

/**
 * Evaluate a policy against the caller's live capabilities.
 *
 * Returns `{ allowed, reason }` rather than a bare boolean so callers can
 * render a meaningful "ask your admin" vs "upgrade your plan" state instead of
 * a generic denial.
 *
 * A policy with no `permission` and no `feature` is authenticated-only.
 */
export const canAccess = (policy, { hasPermission, hasFeature, isAuthenticated } = {}) => {
  if (!isAuthenticated) {
    return { allowed: false, reason: accessReasons.AUTH };
  }
  if (!policy) {
    // No policy registered: authenticated-only, matching the previous
    // behaviour of leaving unlisted routes open to any signed-in user.
    return { allowed: true, reason: null };
  }
  if (policy.permission && !hasPermission(policy.permission)) {
    return { allowed: false, reason: accessReasons.PERMISSION, missing: policy.permission };
  }
  if (policy.feature && !hasFeature(policy.feature)) {
    return { allowed: false, reason: accessReasons.FEATURE, missing: policy.feature };
  }
  return { allowed: true, reason: null };
};

/**
 * Build an evaluator bound to a set of capabilities. Convenient for filtering
 * lists (nav, command palette, quick links) in one pass.
 */
export const createEvaluator = (caps) => (policy) => canAccess(policy, caps);

/**
 * Whether the caller may action an approval from the dashboard.
 *
 * COUPLING WARNING: this mirrors `_is_hr_or_admin` / `_is_manager` in
 * backend/app/routers/dashboard.py, which gate the approval action on a
 * *role-name substring*, not on a permission. The UI has to agree with that
 * predicate or the Approve/Reject buttons raise a 403 for every employee.
 *
 * The durable fix is to make the backend permission-gated; when it is, this
 * function should be replaced by a permission check. Until then both sides
 * must change together.
 */
export const canApproveWorkflows = (roleName) => {
  const name = String(roleName || '').toLowerCase();
  if (!name) return false;
  const privileged = ['admin', 'hr', 'super', 'platform'];
  const supervisory = ['manager', 'supervisor', 'lead'];
  return privileged.some((t) => name.includes(t)) || supervisory.some((t) => name.includes(t));
};
