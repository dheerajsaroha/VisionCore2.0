/**
 * UserTable.jsx
 * Enterprise User Directory Table with sortable headers, loading skeletons,
 * empty state, keyboard navigation, and responsive layout.
 */
import React from 'react';
import { Table, TableHeader, TableBody, TableHead, TableRow } from '../ui/Table';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { Avatar } from '../ui/Avatar';
import { UserTableRow } from './UserTableRow';
import { UserStatusBadge, RoleBadge, EmploymentTypeBadge } from './UserStatusBadge';
import { UserActions } from './UserActions';
import { Users, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

export function UserTable({
  users = [],
  loading = false,
  sortBy = 'created_at',
  sortOrder = 'desc',
  onSortChange,
  currentUserId,
  canCreate = false,
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
  onCreate,
  onResetFilters,
}) {
  const renderSortIndicator = (field) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="h-3 w-3 opacity-30 group-hover:opacity-70 transition-opacity" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="h-3 w-3 text-indigo-400" />
    ) : (
      <ArrowDown className="h-3 w-3 text-indigo-400" />
    );
  };

  const handleHeaderClick = (field) => {
    if (!onSortChange) return;
    if (sortBy === field) {
      onSortChange(field, sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      onSortChange(field, 'asc');
    }
  };

  if (loading) {
    return (
      <div className="glass bg-gray-900/60 border border-gray-800/80 rounded-2xl overflow-hidden shadow-xl p-4">
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 py-3 px-2 border-b border-gray-800/60 last:border-0">
              <Skeleton className="h-10 w-10 rounded-full bg-gray-800" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-48 bg-gray-800" />
                <Skeleton className="h-3 w-32 bg-gray-800" />
              </div>
              <Skeleton className="h-6 w-24 rounded-md bg-gray-800 hidden sm:block" />
              <Skeleton className="h-6 w-20 rounded-md bg-gray-800 hidden md:block" />
              <Skeleton className="h-8 w-8 rounded-lg bg-gray-800" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!users || users.length === 0) {
    return (
      <div className="glass bg-gray-900/60 border border-gray-800/80 rounded-2xl p-12 text-center shadow-xl">
        <EmptyState
          icon={Users}
          title="No identities found"
          description="No workforce identities matched your search filters or active criteria."
          actionText={canCreate ? "Provision Identity" : "Reset Filters"}
          onAction={canCreate ? onCreate : onResetFilters}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Mobile / Tablet Responsive Cards View (Visible on screens < lg) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 lg:hidden">
        {users.map((u) => (
          <div
            key={u.id}
            onClick={() => onView(u)}
            tabIndex={0}
            role="button"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onView(u);
              }
            }}
            aria-label={`Identity card for ${u.full_name}`}
            className="glass bg-gray-900/60 border border-gray-800/80 rounded-2xl p-4 shadow-lg hover:border-gray-700 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500 space-y-3"
          >
            {/* Top row: Avatar + Name + Actions */}
            <div className="flex items-start justify-between gap-2.5">
              <div className="flex items-center gap-3 min-w-0">
                <Avatar
                  name={u.full_name}
                  size="md"
                  className="ring-2 ring-gray-800 shadow-sm shrink-0"
                />
                <div className="min-w-0">
                  <div className="font-semibold text-sm text-gray-100 truncate flex items-center gap-1.5">
                    <span className="truncate">{u.full_name}</span>
                  </div>
                  <div className="text-xs text-gray-400 truncate mt-0.5">
                    {u.email}
                  </div>
                </div>
              </div>

              <div onClick={(e) => e.stopPropagation()}>
                <UserActions
                  user={u}
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
              </div>
            </div>

            {/* Badges row: Role, Status, Type, Employee ID */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-gray-800/60">
              <RoleBadge role={u.role} />
              <UserStatusBadge
                isActive={Boolean(u.is_active)}
                hasFaceEnrolled={Boolean(u.has_face_enrolled)}
              />
              <EmploymentTypeBadge type={u.employment_type} />
              <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md bg-gray-950/80 border border-gray-800 text-gray-300 ml-auto">
                {u.employee_id || `EMP-${u.id}`}
              </span>
            </div>

            {/* Details Grid: Department, Designation, Manager, Location */}
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-300 pt-1">
              <div className="bg-gray-950/40 p-2 rounded-xl border border-gray-800/50">
                <span className="text-[10px] uppercase font-bold text-gray-400 block">Department</span>
                <span className="truncate block mt-0.5 font-medium">{u.department?.name || 'Unassigned'}</span>
              </div>
              <div className="bg-gray-950/40 p-2 rounded-xl border border-gray-800/50">
                <span className="text-[10px] uppercase font-bold text-gray-400 block">Designation</span>
                <span className="truncate block mt-0.5 font-medium">{u.designation || 'Staff'}</span>
              </div>
              <div className="bg-gray-950/40 p-2 rounded-xl border border-gray-800/50">
                <span className="text-[10px] uppercase font-bold text-gray-400 block">Location</span>
                <span className="truncate block mt-0.5">{u.location || 'Headquarters'}</span>
              </div>
              <div className="bg-gray-950/40 p-2 rounded-xl border border-gray-800/50">
                <span className="text-[10px] uppercase font-bold text-gray-400 block">Manager</span>
                <span className="truncate block mt-0.5">{u.manager_name || '—'}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Enterprise Table View (Visible on screens >= lg) */}
      <div className="hidden lg:block glass bg-gray-900/60 border border-gray-800/80 rounded-2xl overflow-hidden shadow-xl transition-colors">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-gray-800 bg-gray-950/40">
                {/* Employee/User */}
                <TableHead
                  onClick={() => handleHeaderClick('full_name')}
                  className="cursor-pointer select-none group py-3 px-4"
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-gray-400 group-hover:text-gray-200 transition-colors">
                    <span>Identity</span>
                    {renderSortIndicator('full_name')}
                  </div>
                </TableHead>

                {/* Employee ID */}
                <TableHead
                  onClick={() => handleHeaderClick('employee_id')}
                  className="cursor-pointer select-none group py-3 px-4"
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-gray-400 group-hover:text-gray-200 transition-colors">
                    <span>Employee ID</span>
                    {renderSortIndicator('employee_id')}
                  </div>
                </TableHead>

                {/* Role */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Role
                </TableHead>

                {/* Department */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Department
                </TableHead>

                {/* Designation */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Designation
                </TableHead>

                {/* Employment Type */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Type
                </TableHead>

                {/* Status */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Status
                </TableHead>

                {/* Manager */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Manager
                </TableHead>

                {/* Location */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Location
                </TableHead>

                {/* Joined Date */}
                <TableHead
                  onClick={() => handleHeaderClick('created_at')}
                  className="cursor-pointer select-none group py-3 px-4"
                >
                  <div className="flex items-center gap-1.5 text-xs font-bold text-gray-400 group-hover:text-gray-200 transition-colors">
                    <span>Joined</span>
                    {renderSortIndicator('created_at')}
                  </div>
                </TableHead>

                {/* Last Activity */}
                <TableHead className="py-3 px-4 text-xs font-bold text-gray-400">
                  Last Activity
                </TableHead>

                {/* Actions */}
                <TableHead className="py-3 px-4 text-right text-xs font-bold text-gray-400">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {users.map((u) => (
                <UserTableRow
                  key={u.id}
                  user={u}
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
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}

export default UserTable;
