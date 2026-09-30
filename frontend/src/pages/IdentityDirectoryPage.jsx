/**
 * IdentityDirectoryPage.jsx
 * Production-Grade Enterprise Identity Directory & Workforce User Management.
 * Phase 5 Core Deliverable for VisionCore 2.0.
 *
 * Capabilities:
 * - Server-side search & multi-criteria filtering (Role, Status, Department, Employment Type)
 * - Server-side sorting & pagination
 * - Real KPI aggregations (Total, Active, Suspended, Privileged, Biometric Enrolled)
 * - Fine-grained RBAC authorization (users.read, users.create, users.update, users.delete, roles.assign)
 * - Strict multi-tenant organization scoping
 * - Comprehensive multi-tab identity dossier drawer
 * - Identity provisioning & profile updating workflows
 * - Dedicated RBAC role assignment with capability preview
 * - Consequence-aware account suspension with mandatory audit reason logging
 * - Neural biometric face enrollment via live camera
 * - Immutable lifecycle audit timeline viewer
 * - Full Phase 2 theme engine support (Dark, Light, Midnight, Nordic)
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '../store/authStore';
import { usePermissionStore } from '../store/permissionStore';
import { useToast } from '../components/ui/Toast';
import { Pagination } from '../components/ui/Pagination';

import {
  DirectoryHeader,
  DirectorySummary,
  DirectoryFilters,
  UserTable,
  UserDetailDrawer,
  UserFormModal,
  RoleAssignmentModal,
  UserDeactivateDialog,
  UserArchiveDialog,
  BiometricEnrollModal,
  IdentityTimelineModal,
} from '../components/directory';

import userService from '../services/userService';
import { departmentService } from '../services/departmentService';

const DEFAULT_PAGE_SIZE = 20;

export default function IdentityDirectoryPage() {
  const { user: currentUser } = useAuthStore();
  const toast = useToast();
  const { hasPermission } = usePermissionStore();

  // RBAC permissions
  const canReadUsers = hasPermission('users.read');
  const canCreateUsers = hasPermission('users.create');
  const canEditUsers = hasPermission('users.update');
  const canDeleteUsers = hasPermission('users.delete');
  // Updating another identity's role also passes through the protected user
  // update endpoint, so reflect both server-side requirements in the UI.
  const canAssignRole = canEditUsers && (
    hasPermission('roles.assign') || currentUser?.role?.name === 'SuperAdmin'
  );

  // Table Data & Pagination State
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // Filters State
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [branchFilter, setBranchFilter] = useState('');
  const [managerFilter, setManagerFilter] = useState('');
  const [employmentTypeFilter, setEmploymentTypeFilter] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Summary Metrics State
  const [summary, setSummary] = useState({
    total: 0,
    active_count: 0,
    inactive_count: 0,
    privileged_count: 0,
    enrolled_count: 0,
  });
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Metadata catalogs
  const [departments, setDepartments] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [branches, setBranches] = useState([]);
  const [roles, setRoles] = useState([]);

  // Active Modals & Selected Records
  const [selectedUser, setSelectedUser] = useState(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  const [formModalOpen, setFormModalOpen] = useState(false);
  const [formMode, setFormMode] = useState('create');
  const [formTargetUser, setFormTargetUser] = useState(null);
  const [formLoading, setFormLoading] = useState(false);

  const [roleModalUser, setRoleModalUser] = useState(null);
  const [roleLoading, setRoleLoading] = useState(false);

  const [suspendUser, setSuspendUser] = useState(null);
  const [suspendLoading, setSuspendLoading] = useState(false);

  const [archiveUser, setArchiveUser] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const [enrollUser, setEnrollUser] = useState(null);
  const [timelineUser, setTimelineUser] = useState(null);

  // Search Debounce handler (300ms)
  const debounceTimerRef = useRef(null);
  const usersRequestIdRef = useRef(0);
  const summaryRequestIdRef = useRef(0);
  // Selected identity is tracked through a ref: fetchUsers must not depend on
  // it, otherwise refreshing the open drawer would invalidate the callback,
  // re-trigger the fetch effect, and storm the users endpoint.
  const selectedUserIdRef = useRef(null);

  useEffect(() => {
    selectedUserIdRef.current = selectedUser?.id ?? null;
  }, [selectedUser]);

  useEffect(() => () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  }, []);

  const handleSearchChange = (val) => {
    setSearch(val);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedSearch(val);
      setPage(1);
    }, 300);
  };

  // Fetch Summary Metrics
  const fetchSummary = useCallback(async () => {
    if (!canReadUsers) return;
    const requestId = ++summaryRequestIdRef.current;
    try {
      setLoadingSummary(true);
      const res = await userService.getUsersSummary();
      if (requestId === summaryRequestIdRef.current) setSummary(res.data);
    } catch (err) {
      if (requestId === summaryRequestIdRef.current) {
        console.error('Failed to fetch user summary:', err);
      }
    } finally {
      if (requestId === summaryRequestIdRef.current) setLoadingSummary(false);
    }
  }, [canReadUsers]);

  // Fetch Users with active filters & server pagination
  const fetchUsers = useCallback(async () => {
    if (!canReadUsers) return;
    const requestId = ++usersRequestIdRef.current;
    try {
      setLoadingUsers(true);
      const params = {
        skip: (page - 1) * pageSize,
        limit: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      };

      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (roleFilter) params.role = roleFilter;
      if (statusFilter !== '') params.is_active = Number(statusFilter);
      if (deptFilter) params.dept_id = Number(deptFilter);
      if (branchFilter) params.branch_id = Number(branchFilter);
      if (managerFilter) params.manager_id = Number(managerFilter);
      if (employmentTypeFilter) params.employment_type = employmentTypeFilter;

      const res = await userService.getUsers(params);
      const fetchedUsers = res.data?.users || [];
      const fetchedTotal = res.data?.total || 0;

      if (requestId !== usersRequestIdRef.current) return;

      setUsers(fetchedUsers);
      setTotalUsers(fetchedTotal);

      // If detailed user drawer is open, keep selected user updated. Compare
      // before replacing so an unchanged record does not re-render the page.
      const selectedId = selectedUserIdRef.current;
      if (selectedId != null) {
        const updatedSelected = fetchedUsers.find((u) => u.id === selectedId);
        if (updatedSelected) {
          setSelectedUser((prev) => (
            prev && JSON.stringify(prev) === JSON.stringify(updatedSelected)
              ? prev
              : updatedSelected
          ));
        }
      }
    } catch (err) {
      if (requestId === usersRequestIdRef.current) {
        console.error('Failed to fetch directory users:', err);
        toast({
          message: err.response?.data?.detail || 'Failed to retrieve directory records.',
          type: 'error',
        });
      }
    } finally {
      if (requestId === usersRequestIdRef.current) setLoadingUsers(false);
    }
  }, [
    canReadUsers,
    page,
    pageSize,
    debouncedSearch,
    roleFilter,
    statusFilter,
    deptFilter,
    branchFilter,
    managerFilter,
    employmentTypeFilter,
    sortBy,
    sortOrder,
    toast,
  ]);

  // Fetch Catalogs (Departments, Shifts, Roles, Branches)
  const fetchMetadata = useCallback(async () => {
    try {
      const [deptRes, shiftRes, rolesRes, branchRes] = await Promise.allSettled([
        departmentService.getDepartments(),
        departmentService.getShifts(),
        userService.getRoles(),
        userService.getBranches(),
      ]);

      if (deptRes.status === 'fulfilled') setDepartments(deptRes.value.data || []);
      if (shiftRes.status === 'fulfilled') setShifts(shiftRes.value.data || []);
      if (rolesRes.status === 'fulfilled') {
        const rData = rolesRes.value.data;
        setRoles(Array.isArray(rData) ? rData : (rData?.roles || rData?.items || []));
      }
      if (branchRes.status === 'fulfilled') setBranches(branchRes.value.data || []);
    } catch (e) {
      console.warn('Metadata fetch partial error:', e);
    }
  }, []);

  // Initial Data Load
  useEffect(() => {
    fetchMetadata();
    fetchSummary();
  }, [fetchMetadata, fetchSummary]);

  // Refetch directory when filters or pagination changes
  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Manual Refresh handler
  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchUsers(), fetchSummary()]);
    setRefreshing(false);
    toast({ message: 'Identity Directory refreshed.', type: 'info' });
  };

  // Reset Filters handler
  const handleResetFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setRoleFilter('');
    setStatusFilter('');
    setDeptFilter('');
    setBranchFilter('');
    setManagerFilter('');
    setEmploymentTypeFilter('');
    setSortBy('created_at');
    setSortOrder('desc');
    setPage(1);
  };

  // Sort change handler
  const handleSortChange = (newSortBy, newSortOrder) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
    setPage(1);
  };

  // Detail Drawer Handlers
  const handleOpenDetail = (user) => {
    setSelectedUser(user);
    setIsDetailOpen(true);
  };

  const handleCloseDetail = () => {
    setIsDetailOpen(false);
    setSelectedUser(null);
  };

  // Provisioning & Edit Modal Handlers
  const handleOpenCreate = () => {
    setFormMode('create');
    setFormTargetUser(null);
    setFormModalOpen(true);
  };

  const handleOpenEdit = (user) => {
    setFormMode('edit');
    setFormTargetUser(user);
    setFormModalOpen(true);
  };

  const handleFormSubmit = async (formData) => {
    setFormLoading(true);
    try {
      if (formMode === 'create') {
        const res = await userService.createUser(formData);
        toast({
          message: `Identity provisioned successfully for ${res.data.full_name}.`,
          type: 'success',
        });
      } else {
        const res = await userService.updateUser(formTargetUser.id, formData);
        toast({
          message: `Profile updated for ${res.data.full_name}.`,
          type: 'success',
        });
      }
      setFormModalOpen(false);
      fetchUsers();
      fetchSummary();
    } catch (err) {
      toast({
        message: err.response?.data?.detail || 'Failed to save identity changes.',
        type: 'error',
      });
      throw err;
    } finally {
      setFormLoading(false);
    }
  };

  // Role Assignment Handlers
  const handleOpenRoleAssign = (user) => {
    setRoleModalUser(user);
  };

  const handleRoleAssignConfirm = async (userId, newRole) => {
    setRoleLoading(true);
    try {
      await userService.updateUser(userId, { role: newRole });
      toast({
        message: `Role updated to ${newRole} for ${roleModalUser.full_name}.`,
        type: 'success',
      });
      setRoleModalUser(null);
      fetchUsers();
      fetchSummary();
    } catch (err) {
      toast({
        message: err.response?.data?.detail || 'Failed to update role.',
        type: 'error',
      });
    } finally {
      setRoleLoading(false);
    }
  };

  // Account Activation Handler
  const handleActivateUser = async (user) => {
    try {
      await userService.activateIdentity(user.id);
      toast({
        message: `Account activated for ${user.full_name}.`,
        type: 'success',
      });
      fetchUsers();
      fetchSummary();
    } catch (err) {
      toast({
        message: err.response?.data?.detail || 'Failed to activate identity.',
        type: 'error',
      });
    }
  };

  // Account Suspension Handlers
  const handleOpenSuspend = (user) => {
    setSuspendUser(user);
  };

  const handleSuspendConfirm = async (userId, reason) => {
    setSuspendLoading(true);
    try {
      await userService.suspendIdentity(userId, reason);
      toast({
        message: `Account suspended for ${suspendUser.full_name}. Active sessions revoked.`,
        type: 'warning',
      });
      setSuspendUser(null);
      fetchUsers();
      fetchSummary();
    } catch (err) {
      toast({
        message: err.response?.data?.detail || 'Failed to suspend identity.',
        type: 'error',
      });
    } finally {
      setSuspendLoading(false);
    }
  };

  // Soft Delete / Archive Handlers
  const handleDeleteUser = (user) => {
    if (currentUser?.id === user.id) {
      toast({ message: 'You cannot delete or archive your own account.', type: 'error' });
      return;
    }
    setArchiveUser(user);
  };

  const handleArchiveConfirm = async (user) => {
    setArchiveLoading(true);
    try {
      await userService.deleteUser(user.id);
      toast({
        message: `Identity ${user.full_name} has been deactivated and archived.`,
        type: 'success',
      });
      if (selectedUser?.id === user.id) handleCloseDetail();
      setArchiveUser(null);
      fetchUsers();
      fetchSummary();
    } catch (err) {
      toast({
        message: err.response?.data?.detail || 'Failed to archive identity.',
        type: 'error',
      });
    } finally {
      setArchiveLoading(false);
    }
  };

  const totalPages = Math.ceil(totalUsers / pageSize) || 1;

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* 1. Page Header */}
      <DirectoryHeader
        totalCount={totalUsers}
        canCreate={canCreateUsers}
        onCreate={handleOpenCreate}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        orgName={currentUser?.organization?.name || currentUser?.org_name || ''}
      />

      {/* 2. Directory Summary Metrics */}
      <DirectorySummary
        total={summary.total}
        activeCount={summary.active_count}
        inactiveCount={summary.inactive_count}
        adminCount={summary.privileged_count}
        enrolledCount={summary.enrolled_count}
        loading={loadingSummary}
      />

      {/* 3. Search & Multi-Filter Toolbar */}
      <DirectoryFilters
        search={search}
        onSearchChange={handleSearchChange}
        roleFilter={roleFilter}
        onRoleChange={(r) => { setRoleFilter(r); setPage(1); }}
        statusFilter={statusFilter}
        onStatusChange={(s) => { setStatusFilter(s); setPage(1); }}
        deptFilter={deptFilter}
        onDeptChange={(d) => { setDeptFilter(d); setPage(1); }}
        branchFilter={branchFilter}
        onBranchChange={(b) => { setBranchFilter(b); setPage(1); }}
        managerFilter={managerFilter}
        onManagerChange={(m) => { setManagerFilter(m); setPage(1); }}
        employmentTypeFilter={employmentTypeFilter}
        onEmploymentTypeChange={(t) => { setEmploymentTypeFilter(t); setPage(1); }}
        sortBy={sortBy}
        onSortByChange={(f) => { setSortBy(f); setPage(1); }}
        sortOrder={sortOrder}
        onSortOrderToggle={() => handleSortChange(sortBy, sortOrder === 'asc' ? 'desc' : 'asc')}
        departments={departments}
        branches={branches}
        managers={users}
        roles={roles}
        onResetFilters={handleResetFilters}
      />

      {/* 4. Enterprise Identity Directory Table */}
      <UserTable
        users={users}
        loading={loadingUsers}
        total={totalUsers}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSortChange={handleSortChange}
        currentUserId={currentUser?.id}
        canCreate={canCreateUsers}
        canEdit={canEditUsers}
        canDelete={canDeleteUsers}
        canAssignRole={canAssignRole}
        canViewTimeline={canReadUsers}
        onView={handleOpenDetail}
        onEdit={handleOpenEdit}
        onAssignRole={handleOpenRoleAssign}
        onActivate={handleActivateUser}
        onSuspend={handleOpenSuspend}
        onEnroll={(u) => setEnrollUser(u)}
        onTimeline={(u) => setTimelineUser(u)}
        onDelete={handleDeleteUser}
        onCreate={handleOpenCreate}
        onResetFilters={handleResetFilters}
      />

      {/* 5. Directory Server-Side Pagination */}
      {totalUsers > 0 && (
        <div className="glass bg-gray-900/60 border border-gray-800/80 rounded-2xl px-6 py-3 shadow-lg">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={(p) => setPage(p)}
            pageSize={pageSize}
            totalItems={totalUsers}
            onPageSizeChange={(sz) => {
              setPageSize(sz);
              setPage(1);
            }}
          />
        </div>
      )}

      {/* 6. Comprehensive User Detail / Dossier Drawer */}
      <UserDetailDrawer
        user={selectedUser}
        isOpen={isDetailOpen}
        onClose={handleCloseDetail}
        currentUserId={currentUser?.id}
        canEdit={canEditUsers}
        canDelete={canDeleteUsers}
        canAssignRole={canAssignRole}
        onEdit={handleOpenEdit}
        onAssignRole={handleOpenRoleAssign}
        onActivate={handleActivateUser}
        onSuspend={handleOpenSuspend}
        onEnroll={(u) => setEnrollUser(u)}
        onDelete={handleDeleteUser}
      />

      {/* 7. Provision / Edit Identity Modal */}
      <UserFormModal
        isOpen={formModalOpen}
        onClose={() => setFormModalOpen(false)}
        mode={formMode}
        initialUser={formTargetUser}
        departments={departments}
        shifts={shifts}
        branches={branches}
        managers={users}
        roles={roles}
        canAssignRole={canAssignRole}
        onSubmit={handleFormSubmit}
        loading={formLoading}
      />

      {/* 8. Role Assignment Modal */}
      <RoleAssignmentModal
        isOpen={Boolean(roleModalUser)}
        onClose={() => setRoleModalUser(null)}
        user={roleModalUser}
        roles={roles}
        onAssign={handleRoleAssignConfirm}
        loading={roleLoading}
      />

      {/* 9. Consequence-Aware Suspension Dialog */}
      <UserDeactivateDialog
        isOpen={Boolean(suspendUser)}
        onClose={() => setSuspendUser(null)}
        user={suspendUser}
        onConfirm={handleSuspendConfirm}
        loading={suspendLoading}
      />

      {/* 10. Consequence-Aware Archive Dialog */}
      <UserArchiveDialog
        isOpen={Boolean(archiveUser)}
        onClose={() => setArchiveUser(null)}
        user={archiveUser}
        currentUserId={currentUser?.id}
        onConfirm={handleArchiveConfirm}
        loading={archiveLoading}
      />

      {/* 10. Neural Biometric Face Enrollment Modal */}
      <BiometricEnrollModal
        isOpen={Boolean(enrollUser)}
        onClose={() => setEnrollUser(null)}
        user={enrollUser}
        onSuccess={() => {
          toast({
            message: `Neural face template registered for ${enrollUser.full_name}.`,
            type: 'success',
          });
          fetchUsers();
          fetchSummary();
        }}
      />

      {/* 11. Lifecycle Audit Timeline Modal */}
      <IdentityTimelineModal
        isOpen={Boolean(timelineUser)}
        onClose={() => setTimelineUser(null)}
        user={timelineUser}
      />
    </motion.div>
  );
}
