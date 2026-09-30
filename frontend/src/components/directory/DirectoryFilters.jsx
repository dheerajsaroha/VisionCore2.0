/**
 * DirectoryFilters.jsx
 * Search and multi-criteria filter control bar for the Enterprise User Directory.
 * Strictly adheres to Phase 2 theme engine (Dark, Light, Midnight, Nordic).
 */
import React from 'react';
import { Search, X, RotateCcw, ArrowUpDown, ArrowUp, ArrowDown, SlidersHorizontal } from 'lucide-react';
import { Button } from '../ui/Button';

export function DirectoryFilters({
  search = '',
  onSearchChange,
  roleFilter = '',
  onRoleChange,
  statusFilter = '',
  onStatusChange,
  deptFilter = '',
  onDeptChange,
  branchFilter = '',
  onBranchChange,
  managerFilter = '',
  onManagerChange,
  employmentTypeFilter = '',
  onEmploymentTypeChange,
  sortBy = 'created_at',
  onSortByChange,
  sortOrder = 'desc',
  onSortOrderToggle,
  departments = [],
  branches = [],
  managers = [],
  roles = [],
  onResetFilters,
}) {
  const rolesList = Array.isArray(roles) ? roles : (roles?.items || []);

  const hasActiveFilters = Boolean(
    search ||
    roleFilter ||
    statusFilter !== '' ||
    deptFilter ||
    branchFilter ||
    managerFilter ||
    employmentTypeFilter ||
    sortBy !== 'created_at' ||
    sortOrder !== 'desc'
  );

  return (
    <div className="glass bg-gray-900/60 border border-gray-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-xl transition-colors space-y-3">
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Search Input with Debounce support and clear button */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search name, email, employee ID, designation, department..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-gray-950/80 border border-gray-800 text-gray-100 placeholder:text-gray-500 text-xs pl-10 pr-9 py-2.5 rounded-xl focus:border-indigo-500 focus:outline-none transition-all"
            aria-label="Search identities"
          />
          {search && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Primary Filters Row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Role Filter */}
          <select
            value={roleFilter}
            onChange={(e) => onRoleChange(e.target.value)}
            className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            aria-label="Filter by role"
          >
            <option value="">All Roles</option>
            {rolesList.map((r) => (
              <option key={r.id || r.name} value={r.name}>{r.name}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
            className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            aria-label="Filter by account status"
          >
            <option value="">All Statuses</option>
            <option value="1">Active Only</option>
            <option value="0">Suspended / Inactive</option>
          </select>

          {/* Department Filter */}
          {departments.length > 0 && (
            <select
              value={deptFilter}
              onChange={(e) => onDeptChange(e.target.value)}
              className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors max-w-[160px] truncate"
              aria-label="Filter by department"
            >
              <option value="">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          )}

          {/* Branch / Location Filter */}
          {branches.length > 0 && (
            <select
              value={branchFilter}
              onChange={(e) => onBranchChange(e.target.value)}
              className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors max-w-[160px] truncate"
              aria-label="Filter by location"
            >
              <option value="">All Locations</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>{b.name}{b.city ? ` (${b.city})` : ''}</option>
              ))}
            </select>
          )}

          {/* Manager / Reporting Filter */}
          {managers.length > 0 && (
            <select
              value={managerFilter}
              onChange={(e) => onManagerChange(e.target.value)}
              className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors max-w-[160px] truncate"
              aria-label="Filter by reporting manager"
            >
              <option value="">All Managers</option>
              {managers.map((m) => (
                <option key={m.id} value={m.id}>{m.full_name}</option>
              ))}
            </select>
          )}

          {/* Employment Type Filter */}
          <select
            value={employmentTypeFilter}
            onChange={(e) => onEmploymentTypeChange(e.target.value)}
            className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            aria-label="Filter by employment type"
          >
            <option value="">All Types</option>
            <option value="EMPLOYEE">Employee</option>
            <option value="CONTRACTOR">Contractor</option>
            <option value="CONSULTANT">Consultant</option>
            <option value="VENDOR">Vendor</option>
            <option value="INTERN">Intern</option>
          </select>

          {/* Sort By Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => onSortByChange(e.target.value)}
            className="bg-gray-950/80 border border-gray-800 text-gray-300 text-xs px-3 py-2.5 rounded-xl focus:border-indigo-500 outline-none transition-colors"
            aria-label="Sort users by"
          >
            <option value="created_at">Sort: Joined Date</option>
            <option value="full_name">Sort: Full Name</option>
            <option value="email">Sort: Email Address</option>
            <option value="employee_id">Sort: Employee ID</option>
          </select>

          {/* Sort Order Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onSortOrderToggle}
            className="border border-gray-800 bg-gray-950/80 text-gray-300 hover:bg-gray-800 px-2.5 py-2 rounded-xl text-xs"
            title={`Toggle sort order (current: ${sortOrder.toUpperCase()})`}
            aria-label="Toggle sort order"
          >
            {sortOrder === 'asc' ? (
              <ArrowUp className="h-3.5 w-3.5 text-indigo-400" />
            ) : (
              <ArrowDown className="h-3.5 w-3.5 text-indigo-400" />
            )}
            <span className="ml-1 uppercase text-[10px]">{sortOrder}</span>
          </Button>

          {/* Reset Filters */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onResetFilters}
              className="text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 border border-rose-500/20 px-2.5 py-2 rounded-xl"
              title="Reset all filters"
              aria-label="Reset all filters"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1" />
              Reset
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default DirectoryFilters;
