import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Search,
  Filter,
  CheckCircle,
  XCircle,
  RefreshCw,
  Download,
  Eye,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Sliders,
  Lock,
} from 'lucide-react';
import { usePermissionStore } from '../store/permissionStore';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { cn } from '../lib/utils';

const PAGE_SIZE = 25;

export default function PermissionManagement() {
  const store = usePermissionStore();

  // Local state
  const [permissions, setPermissions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [modules, setModules] = useState([]);
  const [selectedPermission, setSelectedPermission] = useState(null);
  const [moduleStats, setModuleStats] = useState([]);
  const [showModules, setShowModules] = useState(false);
  const [actionFeedback, setActionFeedback] = useState(null);

  // Fetch permissions
  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        search: search || undefined,
        module: moduleFilter || undefined,
        is_active: activeFilter !== '' ? activeFilter === 'true' : undefined,
      };
      const data = await store.fetchPermissions(params);
      if (data) {
        setPermissions(data.permissions || []);
        setTotal(data.total || 0);
      }
    } finally {
      setLoading(false);
    }
  }, [page, search, moduleFilter, activeFilter, store]);

  // Fetch modules
  const fetchModules = useCallback(async () => {
    try {
      const data = await store.fetchModuleSummary();
      if (data) {
        setModules(data.modules || []);
      }
    } catch {}
  }, [store]);

  // Fetch module stats for detail view
  const fetchModuleStats = useCallback(async () => {
    try {
      const data = await store.fetchModuleStats();
      if (data) {
        setModuleStats(data.modules || []);
      }
    } catch {}
  }, [store]);

  useEffect(() => {
    fetchPermissions();
  }, [fetchPermissions]);

  useEffect(() => {
    fetchModules();
  }, [fetchModules]);

  // Handle search submit
  const handleSearch = (e) => {
    e.preventDefault();
    setPage(0);
    fetchPermissions();
  };

  // Handle permission toggle
  const handleToggleStatus = async (perm) => {
    const result = await store.setPermissionStatus(perm.id, !perm.is_active);
    if (result?.success) {
      setActionFeedback({
        type: 'success',
        message: result.message,
      });
      fetchPermissions();
    } else {
      setActionFeedback({
        type: 'error',
        message: result?.message || 'Failed to update status',
      });
    }
    setTimeout(() => setActionFeedback(null), 3000);
  };

  // Handle view module stats
  const handleViewModules = () => {
    setShowModules(!showModules);
    if (!showModules) {
      fetchModuleStats();
    }
  };

  // Export
  const handleExport = async (format) => {
    try {
      const data = await store.exportPermissions(format);
      const blob = format === 'csv'
        ? new Blob([data], { type: 'text/csv' })
        : new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `permissions.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <motion.div
      className="space-y-6 lg:space-y-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Permission Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {total} permissions across {modules.length} modules
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleExport('json')}
            className="flex items-center gap-1"
          >
            <Download className="h-4 w-4" />
            JSON
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1"
          >
            <Download className="h-4 w-4" />
            CSV
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPage(0);
              fetchPermissions();
            }}
            className="flex items-center gap-1"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Action Feedback */}
      {actionFeedback && (
        <div
          className={cn(
            'px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2',
            actionFeedback.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
          )}
        >
          {actionFeedback.type === 'success' ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          {actionFeedback.message}
        </div>
      )}

      {/* Module Overview Button */}
      <Button
        variant="outline"
        onClick={handleViewModules}
        className="flex items-center gap-2"
      >
        <Sliders className="h-4 w-4" />
        {showModules ? 'Hide Module Overview' : 'Show Module Overview'}
      </Button>

      {/* Module Statistics Panel */}
      {showModules && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="overflow-hidden"
        >
          <Card className="border border-slate-200 dark:border-slate-800">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                Permission Modules
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {moduleStats.length === 0 ? (
                  <div className="col-span-full text-center py-8 text-slate-500">
                    <Spinner size="sm" className="mx-auto mb-2" />
                    Loading module statistics...
                  </div>
                ) : (
                  moduleStats.map((mod) => (
                    <div
                      key={mod.module}
                      className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-slate-900 dark:text-white capitalize">
                          {mod.module.replace(/_/g, ' ')}
                        </span>
                        <Badge variant={mod.active > 0 ? 'success' : 'default'}>
                          {mod.total} permissions
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          <CheckCircle className="h-3 w-3 text-emerald-500" />
                          {mod.active} active
                        </span>
                        {mod.inactive > 0 && (
                          <span className="flex items-center gap-1">
                            <XCircle className="h-3 w-3 text-red-400" />
                            {mod.inactive} inactive
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search permissions by name or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all shadow-sm"
          />
        </form>
        <select
          value={moduleFilter}
          onChange={(e) => {
            setModuleFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 outline-none min-w-[140px]"
        >
          <option value="">All Modules</option>
          {modules.map((mod) => (
            <option key={mod.module} value={mod.module}>
              {mod.module.replace(/_/g, ' ')} ({mod.active}/{mod.total})
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 outline-none min-w-[140px]"
        >
          <option value="">All Status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {/* Permissions Table */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="overflow-hidden border-0 shadow-xl shadow-slate-200/50 dark:shadow-none">
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-32">
                <Spinner size="xl" className="text-indigo-500" />
              </div>
            ) : permissions.length === 0 ? (
              <EmptyState
                icon={Shield}
                title="No permissions found"
                description="Try adjusting your filters or search terms."
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Permission
                        </th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Module
                        </th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Description
                        </th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider text-right">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 bg-white dark:bg-transparent">
                      {permissions.map((perm) => (
                        <tr
                          key={perm.id}
                          className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors group cursor-pointer"
                          onClick={() => setSelectedPermission(
                            selectedPermission?.id === perm.id ? null : perm
                          )}
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/20">
                                <Lock className="h-4 w-4 text-indigo-500" />
                              </div>
                              <div>
                                <code className="text-sm font-mono font-semibold text-slate-900 dark:text-white">
                                  {perm.name}
                                </code>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <Badge variant="primary" className="text-xs capitalize">
                              {perm.module?.replace(/_/g, ' ')}
                            </Badge>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400 max-w-xs truncate">
                            {perm.description || '—'}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  'h-2.5 w-2.5 rounded-full shadow-sm',
                                  perm.is_active
                                    ? 'bg-emerald-500 shadow-emerald-500/20'
                                    : 'bg-slate-300 dark:bg-slate-600'
                                )}
                              />
                              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                {perm.is_active ? 'Active' : 'Inactive'}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleToggleStatus(perm);
                                }}
                                className={cn(
                                  'text-xs',
                                  perm.is_active
                                    ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10'
                                    : 'text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-500/10'
                                )}
                              >
                                {perm.is_active ? 'Deactivate' : 'Activate'}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 dark:border-slate-800">
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        disabled={page === 0}
                        onClick={() => setPage(page - 1)}
                        className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300 px-2">
                        {page + 1} / {totalPages}
                      </span>
                      <button
                        disabled={page >= totalPages - 1}
                        onClick={() => setPage(page + 1)}
                        className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Permission Detail Panel */}
      {selectedPermission && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4"
        >
          <Card className="border border-indigo-200 dark:border-indigo-800">
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                    <Lock className="h-5 w-5 text-indigo-500" />
                    {selectedPermission.name}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {selectedPermission.description || 'No description'}
                  </p>
                </div>
                <Badge
                  variant={selectedPermission.is_active ? 'success' : 'default'}
                >
                  {selectedPermission.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Module</p>
                  <p className="font-medium text-slate-900 dark:text-white capitalize mt-1">
                    {selectedPermission.module?.replace(/_/g, ' ') || '—'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Group</p>
                  <p className="font-medium text-slate-900 dark:text-white capitalize mt-1">
                    {selectedPermission.group || '—'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Permission ID</p>
                  <p className="font-medium text-slate-900 dark:text-white mt-1 font-mono">
                    #{selectedPermission.id}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Status</p>
                  <p className="font-medium mt-1 flex items-center gap-1">
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full',
                        selectedPermission.is_active ? 'bg-emerald-500' : 'bg-slate-400'
                      )}
                    />
                    {selectedPermission.is_active ? 'Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <div className="flex gap-2 mt-6 pt-4 border-t border-slate-100 dark:border-slate-800">
                <Button
                  size="sm"
                  variant={selectedPermission.is_active ? 'danger' : 'primary'}
                  onClick={() => handleToggleStatus(selectedPermission)}
                >
                  {selectedPermission.is_active ? 'Deactivate' : 'Activate'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setSelectedPermission(null)}
                >
                  Close
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </motion.div>
  );
}

