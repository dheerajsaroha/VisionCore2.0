/**
 * UserTableRow.jsx
 * Accessible table row representing a workforce identity in the directory.
 * Responsive, keyboard-navigable, and theme-adaptive.
 */
import React from 'react';
import { Avatar } from '../ui/Avatar';
import { TableRow, TableCell } from '../ui/Table';
import { UserStatusBadge, RoleBadge, EmploymentTypeBadge } from './UserStatusBadge';
import { UserActions } from './UserActions';
import { formatDate } from '../../lib/utils';
import { Mail, Building2, MapPin } from 'lucide-react';

export function UserTableRow({
  user,
  currentUserId,
  canEdit = false,
  canDelete = false,
  canAssignRole = false,
  canViewTimeline = true,
  onView,
  onEdit,
  onAssignRole,
  onActivate,
  onSuspend,
  onEnroll,
  onTimeline,
  onDelete,
}) {
  const formatActivity = (dt) => {
    if (!dt) return 'Never';
    return formatDate(dt);
  };

  return (
    <TableRow
      key={user.id}
      onClick={() => onView(user)}
      className="cursor-pointer group hover:bg-gray-800/40 transition-colors border-b border-gray-800/80"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onView(user);
        }
      }}
      aria-label={`Identity row for ${user.full_name}`}
    >
      {/* 1. Identity / User */}
      <TableCell className="py-3.5 px-4">
        <div className="flex items-center gap-3">
          <Avatar
            name={user.full_name}
            size="md"
            className="ring-2 ring-gray-800 group-hover:ring-indigo-500/40 transition-all shadow-sm"
          />
          <div className="min-w-0 max-w-[200px]">
            <div className="font-semibold text-sm text-gray-100 group-hover:text-indigo-300 transition-colors truncate">
              {user.full_name}
            </div>
            <div className="text-xs text-gray-400 flex items-center gap-1 mt-0.5 truncate">
              <Mail className="h-3 w-3 shrink-0 text-gray-500" />
              <span className="truncate">{user.email}</span>
            </div>
          </div>
        </div>
      </TableCell>

      {/* 2. Employee ID */}
      <TableCell className="py-3.5 px-4">
        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-md bg-gray-950/80 border border-gray-800 text-gray-300">
          {user.employee_id || `EMP-${user.id}`}
        </span>
      </TableCell>

      {/* 3. Role */}
      <TableCell className="py-3.5 px-4">
        <RoleBadge role={user.role} />
      </TableCell>

      {/* 4. Department */}
      <TableCell className="py-3.5 px-4">
        <div className="text-xs font-medium text-gray-200 flex items-center gap-1.5 truncate">
          <Building2 className="h-3.5 w-3.5 text-gray-500 shrink-0" />
          <span className="truncate">{user.department?.name || 'Unassigned'}</span>
        </div>
      </TableCell>

      {/* 5. Designation */}
      <TableCell className="py-3.5 px-4">
        <div className="text-xs text-gray-300 font-medium truncate max-w-[140px]" title={user.designation || 'Staff'}>
          {user.designation || 'Staff'}
        </div>
      </TableCell>

      {/* 6. Employment Type */}
      <TableCell className="py-3.5 px-4">
        <EmploymentTypeBadge type={user.employment_type} />
      </TableCell>

      {/* 7. Status & Biometrics */}
      <TableCell className="py-3.5 px-4">
        <UserStatusBadge
          isActive={Boolean(user.is_active)}
          hasFaceEnrolled={Boolean(user.has_face_enrolled)}
        />
      </TableCell>

      {/* 8. Manager */}
      <TableCell className="py-3.5 px-4">
        <span className="text-xs text-gray-400 truncate max-w-[120px] block">
          {user.manager_name || '—'}
        </span>
      </TableCell>

      {/* 9. Location */}
      <TableCell className="py-3.5 px-4">
        <div className="text-xs text-gray-400 flex items-center gap-1 truncate max-w-[130px]">
          <MapPin className="h-3 w-3 text-gray-500 shrink-0" />
          <span className="truncate">{user.location || 'Headquarters'}</span>
        </div>
      </TableCell>

      {/* 10. Joined Date */}
      <TableCell className="py-3.5 px-4 text-xs text-gray-400 whitespace-nowrap">
        {formatDate(user.created_at)}
      </TableCell>

      {/* 11. Last Activity */}
      <TableCell className="py-3.5 px-4 text-xs text-gray-400 whitespace-nowrap">
        {formatActivity(user.last_activity)}
      </TableCell>

      {/* 12. Actions */}
      <TableCell className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
        <UserActions
          user={user}
          currentUserId={currentUserId}
          canEdit={canEdit}
          canDelete={canDelete}
          canAssignRole={canAssignRole}
          canViewTimeline={canViewTimeline}
          onView={onView}
          onEdit={onEdit}
          onAssignRole={onAssignRole}
          onActivate={onActivate}
          onSuspend={onSuspend}
          onEnroll={onEnroll}
          onTimeline={onTimeline}
          onDelete={onDelete}
        />
      </TableCell>
    </TableRow>
  );
}

export default UserTableRow;
