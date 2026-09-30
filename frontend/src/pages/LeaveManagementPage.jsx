import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar, Clock, CheckCircle2, XCircle, AlertCircle, Plus, Filter,
  FileText, User, ChevronRight, RefreshCw, Shield, Sparkles, Layers, Check, X
} from 'lucide-react';
import { leaveService } from '../services/leaveService';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { LeaveTemplatePicker } from '../components/leave/LeaveTemplatePicker';
import { LeavePolicyEditor } from '../components/leave/LeavePolicyEditor';
import { formatDate, titleCase } from '../lib/utils';

export default function LeaveManagementPage() {
  const [activeTab, setActiveTab] = useState('balances'); // balances | apply | requests | config
  const [balances, setBalances] = useState([]);
  const [leaveTypes, setLeaveTypes] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const { user } = useAuthStore();
  const { hasPermission } = usePermission();

  // Apply Form State
  const [applyForm, setApplyForm] = useState({
    leave_type_id: '',
    start_date: '',
    end_date: '',
    total_days: 1,
    is_half_day: false,
    half_day_period: 'morning',
    reason: '',
  });

  // Config Form State
  const [configForm, setConfigForm] = useState({
    name: '',
    code: '',
    description: '',
    max_days_per_year: 12,
    max_days_per_request: 30,
    is_paid: true,
  });

  const canApprove = hasPermission('leave.approve');
  const canManage = hasPermission('leave.manage');
  const canViewTeam = hasPermission('leave.view_team') || hasPermission('leave.view_org');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [balRes, typeRes, reqRes] = await Promise.all([
        leaveService.getBalances(),
        leaveService.getLeaveTypes(),
        leaveService.getRequests({ status: statusFilter || undefined }),
      ]);
      setBalances(balRes.data || []);
      setLeaveTypes(typeRes.data || []);
      setRequests(reqRes.data || []);

      if (typeRes.data?.length > 0 && !applyForm.leave_type_id) {
        setApplyForm((prev) => ({ ...prev, leave_type_id: typeRes.data[0].id }));
      }
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load leave management data');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  const refreshLeaveTypes = useCallback(async () => {
    try {
      const typeRes = await leaveService.getLeaveTypes();
      setLeaveTypes(typeRes.data || []);
    } catch {
      // The list stays as-is; the tab will surface its own error state.
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleApplySubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setActionSuccess('');

    try {
      await leaveService.submitRequest({
        ...applyForm,
        leave_type_id: parseInt(applyForm.leave_type_id, 10),
        total_days: parseFloat(applyForm.total_days),
        start_date: new Date(applyForm.start_date).toISOString(),
        end_date: new Date(applyForm.end_date).toISOString(),
      });
      setActionSuccess('Leave request submitted successfully!');
      setActiveTab('requests');
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to submit leave request');
    }
  };

  const handleApprove = async (requestId, status, note = '') => {
    setErrorMsg('');
    try {
      await leaveService.approveRequest(requestId, status, note);
      setActionSuccess(`Request ${status} successfully!`);
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || `Failed to ${status} request`);
    }
  };

  const handleCancel = async (requestId) => {
    setErrorMsg('');
    try {
      await leaveService.cancelRequest(requestId);
      setActionSuccess('Request cancelled successfully!');
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to cancel request');
    }
  };

  const handleCreateType = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await leaveService.createLeaveType(configForm);
      setActionSuccess('New leave type created!');
      setConfigForm({ name: '', code: '', description: '', max_days_per_year: 12, max_days_per_request: 30, is_paid: true });
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create leave type');
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="space-y-8 p-1 sm:p-2">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900 via-slate-900 to-purple-950 p-8 text-white shadow-2xl border border-indigo-500/20">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-2xl bg-indigo-500/20 border border-indigo-400/30 backdrop-blur-md">
                <Calendar className="h-7 w-7 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
                  Leave Management
                </h1>
                <p className="text-sm text-indigo-200/80 mt-0.5">
                  Enterprise leave policy enforcement, balances, and automated workflow gating
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={fetchData} variant="secondary" className="bg-white/10 hover:bg-white/20 text-white border-white/10">
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-8 flex items-center gap-2 border-b border-indigo-500/20 pb-0 overflow-x-auto">
          {[
            { id: 'balances', label: 'My Balances', icon: Clock },
            { id: 'apply', label: 'Apply Leave', icon: Plus },
            { id: 'requests', label: 'Requests & Approvals', icon: FileText },
            ...(canManage ? [{ id: 'config', label: 'Leave Types (Admin)', icon: Layers }] : []),
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-5 py-3 font-semibold text-sm transition-all border-b-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-indigo-400 text-indigo-300 bg-white/5 rounded-t-xl'
                    : 'border-transparent text-indigo-200/60 hover:text-white hover:bg-white/5 rounded-t-xl'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Notifications */}
      {actionSuccess && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{actionSuccess}</span>
        </motion.div>
      )}
      {errorMsg && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{errorMsg}</span>
        </motion.div>
      )}

      {/* TAB 1: MY BALANCES */}
      {activeTab === 'balances' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {balances.length === 0 ? (
            <Card className="col-span-full p-12 text-center text-slate-400">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p>No leave balances found. Contact HR to initialize your quota.</p>
            </Card>
          ) : (
            balances.map((bal) => (
              <motion.div key={bal.id} whileHover={{ y: -4 }} transition={{ duration: 0.2 }}>
                <Card className="relative overflow-hidden border border-slate-800 bg-slate-900/90 shadow-xl backdrop-blur-xl hover:border-indigo-500/40">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-2xl pointer-events-none" />
                  <CardHeader className="pb-3 border-b border-slate-800/80">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg font-bold text-white">
                        {bal.leave_type_name || bal.leave_type_code}
                      </CardTitle>
                      <Badge className="bg-indigo-500/20 text-indigo-300 border-indigo-500/30">
                        {bal.leave_type_code}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-6 space-y-4">
                    <div className="flex items-baseline justify-between">
                      <span className="text-3xl font-black text-white">{bal.available_days}</span>
                      <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Days Available</span>
                    </div>

                    <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full transition-all duration-500"
                        style={{
                          width: `${Math.min(100, (bal.used_days / Math.max(1, bal.entitled_days)) * 100)}%`,
                        }}
                      />
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center pt-2 border-t border-slate-800/60 text-xs">
                      <div>
                        <p className="text-slate-400">Quota</p>
                        <p className="font-bold text-slate-200 mt-0.5">{bal.entitled_days}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">Used</p>
                        <p className="font-bold text-amber-400 mt-0.5">{bal.used_days}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">Pending</p>
                        <p className="font-bold text-indigo-400 mt-0.5">{bal.pending_days}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))
          )}
        </div>
      )}

      {/* TAB 2: APPLY LEAVE */}
      {activeTab === 'apply' && (
        <Card className="max-w-2xl mx-auto border border-slate-800 bg-slate-900/90 shadow-2xl">
          <CardHeader className="border-b border-slate-800">
            <CardTitle className="text-xl font-bold text-white flex items-center gap-2">
              <Plus className="h-5 w-5 text-indigo-400" /> Submit Leave Application
            </CardTitle>
            <CardDescription className="text-slate-400">
              Applications are automatically routed through the approval pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleApplySubmit} className="space-y-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Leave Type</label>
                <select
                  value={applyForm.leave_type_id}
                  onChange={(e) => setApplyForm({ ...applyForm, leave_type_id: e.target.value })}
                  className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  required
                >
                  {leaveTypes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.code}) — Max {t.max_days_per_year} days/yr
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Start Date</label>
                  <input
                    type="date"
                    value={applyForm.start_date}
                    onChange={(e) => setApplyForm({ ...applyForm, start_date: e.target.value })}
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">End Date</label>
                  <input
                    type="date"
                    value={applyForm.end_date}
                    onChange={(e) => setApplyForm({ ...applyForm, end_date: e.target.value })}
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Total Days Requested</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={applyForm.total_days}
                  onChange={(e) => setApplyForm({ ...applyForm, total_days: e.target.value })}
                  className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Reason for Leave</label>
                <textarea
                  rows={3}
                  value={applyForm.reason}
                  onChange={(e) => setApplyForm({ ...applyForm, reason: e.target.value })}
                  placeholder="Provide brief details for your leave request..."
                  className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3 text-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <Button type="submit" className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/30">
                Submit Application
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* TAB 3: REQUESTS & APPROVALS */}
      {activeTab === 'requests' && (
        <Card className="border border-slate-800 bg-slate-900/90 shadow-2xl">
          <CardHeader className="border-b border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-lg font-bold text-white">Leave Requests Ledger</CardTitle>
              <CardDescription className="text-slate-400">All submitted leave applications and approval states</CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg p-2 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {requests.length === 0 ? (
              <div className="p-12 text-center text-slate-400">
                <FileText className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p>No leave requests match your filter.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60 overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-800/40 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    <tr>
                      <th className="p-4">Applicant</th>
                      <th className="p-4">Type</th>
                      <th className="p-4">Dates</th>
                      <th className="p-4">Days</th>
                      <th className="p-4">Status</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40">
                    {requests.map((req) => (
                      <tr key={req.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="p-4 font-semibold text-white">
                          <div>{req.user_name || `User #${req.user_id}`}</div>
                          {req.user_email && <div className="text-xs font-normal text-slate-400">{req.user_email}</div>}
                        </td>
                        <td className="p-4">
                          <Badge variant="outline" className="border-indigo-500/30 text-indigo-300">
                            {req.leave_type_code || req.leave_type_name}
                          </Badge>
                        </td>
                        <td className="p-4 text-xs font-mono">
                          {formatDate(req.start_date)} → {formatDate(req.end_date)}
                        </td>
                        <td className="p-4 font-bold text-white">{req.total_days}</td>
                        <td className="p-4">
                          <Badge
                            className={
                              req.status === 'approved'
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                : req.status === 'rejected'
                                ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                                : req.status === 'pending'
                                ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                : 'bg-slate-700 text-slate-300'
                            }
                          >
                            {titleCase(req.status)}
                          </Badge>
                        </td>
                        <td className="p-4 text-right space-x-2">
                          {req.status === 'pending' && canApprove && req.user_id !== user?.id && (
                            <>
                              <Button size="xs" onClick={() => handleApprove(req.id, 'approved')} className="bg-emerald-600 hover:bg-emerald-500 text-white">
                                <Check className="h-3.5 w-3.5 mr-1" /> Approve
                              </Button>
                              <Button size="xs" onClick={() => handleApprove(req.id, 'rejected')} className="bg-rose-600 hover:bg-rose-500 text-white">
                                <X className="h-3.5 w-3.5 mr-1" /> Reject
                              </Button>
                            </>
                          )}
                          {['pending', 'approved'].includes(req.status) && (req.user_id === user?.id || canApprove) && (
                            <Button size="xs" variant="secondary" onClick={() => handleCancel(req.id)} className="bg-slate-800 hover:bg-slate-700 text-slate-300">
                              Cancel
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* TAB 4: CONFIG (ADMIN ONLY) */}
      {activeTab === 'config' && canManage && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Card className="lg:col-span-1 border border-slate-800 bg-slate-900/90 shadow-xl h-fit">
            <CardHeader className="border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <Layers className="h-5 w-5 text-indigo-400" /> Add Leave Type
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleCreateType} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Name</label>
                  <input
                    type="text"
                    value={configForm.name}
                    onChange={(e) => setConfigForm({ ...configForm, name: e.target.value })}
                    placeholder="e.g. Sabbatical Leave"
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Code</label>
                  <input
                    type="text"
                    value={configForm.code}
                    onChange={(e) => setConfigForm({ ...configForm, code: e.target.value })}
                    placeholder="e.g. SABBATICAL"
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm uppercase focus:outline-none"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Max Days / Year</label>
                  <input
                    type="number"
                    value={configForm.max_days_per_year}
                    onChange={(e) => setConfigForm({ ...configForm, max_days_per_year: parseInt(e.target.value, 10) })}
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                    required
                  />
                </div>
                <Button type="submit" className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl">
                  Create Type
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="lg:col-span-2 space-y-8">
            <LeaveTemplatePicker onApplied={refreshLeaveTypes} />
            <LeavePolicyEditor />
          </div>

          <Card className="lg:col-span-2 border border-slate-800 bg-slate-900/90 shadow-xl">
            <CardHeader className="border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white">Configured Leave Types</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800">
                {leaveTypes.map((t) => (
                  <div key={t.id} className="p-4 flex items-center justify-between hover:bg-slate-800/30">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{t.name}</span>
                        <Badge className="bg-indigo-500/20 text-indigo-300 border-indigo-500/30">{t.code}</Badge>
                        {t.is_paid && <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">Paid</Badge>}
                      </div>
                      <p className="text-xs text-slate-400 mt-1">{t.description || 'No description provided.'}</p>
                    </div>
                    <div className="text-right text-xs">
                      <p className="font-bold text-white">{t.max_days_per_year} days/yr</p>
                      <p className="text-slate-400">
                        Max per request:{' '}
                        {t.max_days_per_request === null || t.max_days_per_request === undefined
                          ? 'No limit'
                          : t.max_days_per_request}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </motion.div>
  );
}
