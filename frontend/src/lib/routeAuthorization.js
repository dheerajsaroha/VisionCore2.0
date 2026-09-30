/**
 * Re-exported from the unified access layer.
 *
 * This module previously held its own policy table that drifted from both the
 * nav array and the `requiredPermission` props in App.jsx. It now re-exports
 * the single table in `accessControl.js` so the two cannot disagree again.
 */
export {
  routePolicies,
  routeAccessForPath,
  permissionForPath,
  featureForPath,
  resolvePolicy,
  canAccess,
  createEvaluator,
  accessReasons,
  MODULE_FEATURES,
} from './accessControl';
