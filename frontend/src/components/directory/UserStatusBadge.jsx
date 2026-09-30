/**
 * UserStatusBadge.jsx
 * Status indicators for account status, role, and biometric enrollment.
 * Theme-adaptive according to Phase 2 design system.
 */
import React from 'react';
import { Badge } from '../ui/Badge';
import { Fingerprint } from 'lucide-react';

export function UserStatusBadge({ isActive, hasFaceEnrolled }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* Account Active/Suspended Badge */}
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
          isActive
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
        }`}
      >
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            isActive ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
          }`}
        />
        {isActive ? 'Active' : 'Suspended'}
      </span>

      {/* Biometric Enrollment Chip */}
      {hasFaceEnrolled ? (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
          title="Face biometric template enrolled & active"
        >
          <Fingerprint className="h-3 w-3" />
          Enrolled
        </span>
      ) : null}
    </div>
  );
}

export function RoleBadge({ role }) {
  const roleName = typeof role === 'string' ? role : role?.name || 'User';
  let variant = 'default';
  if (['SuperAdmin', 'OrgAdmin', 'Admin'].includes(roleName)) variant = 'primary';
  else if (['Manager', 'OrgManager', 'Supervisor'].includes(roleName)) variant = 'info';
  else if (['HR', 'Finance'].includes(roleName)) variant = 'warning';

  return (
    <Badge variant={variant} className="text-xs font-medium px-2.5 py-0.5">
      {roleName}
    </Badge>
  );
}

export function EmploymentTypeBadge({ type = 'EMPLOYEE' }) {
  const cleanType = (type || 'EMPLOYEE').toUpperCase();
  let styleClass = 'bg-gray-800 text-gray-300 border-gray-700';
  if (cleanType === 'CONTRACTOR') styleClass = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  if (cleanType === 'CONSULTANT') styleClass = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
  if (cleanType === 'VENDOR') styleClass = 'bg-orange-500/10 text-orange-400 border-orange-500/20';
  if (cleanType === 'INTERN') styleClass = 'bg-sky-500/10 text-sky-400 border-sky-500/20';

  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold border ${styleClass}`}>
      {cleanType}
    </span>
  );
}

export default UserStatusBadge;
