import React, { useState, useEffect, useCallback } from 'react';
import {
  Calendar, Plus, RefreshCw, CheckCircle2, XCircle, Clock,
  User, Check, X, AlertTriangle, FileText
} from 'lucide-react';
import { leaveService } from '../services/leaveService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { usePermission } from '../hooks/usePermission';

// The API returns lowercase statuses; normalise on the way in so these
// uppercase-keyed maps stay correct.
const normalizeStatus = (value) => String(value ?? '').toUpperCase();

const STATUS_STYLES = {
  PENDING: { color: '#f59e0b', label: 'Pending' },
  APPROVED: { color: '#22c55e', label: 'Approved' },
  REJECTED: { color: '#ef4444', label: 'Rejected' },
  CANCELLED: { color: '#64748b', label: 'Cancelled' },
};

function ApplyLeaveModal({ isOpen, onClose, onSuccess, leaveTypes = [] }) {
  const [form, setForm] = useState({
    leave_type_id: '',
    start_date: '',
    end_date: '',
    reason: '',
    is_half_day: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await leaveService.submitRequest({
        leave_type_id: parseInt(form.leave_type_id) || 1,
        start_date: form.start_date,
        end_date: form.end_date,
        reason: form.reason,
        is_half_day: form.is_half_day,
      });
      onSuccess();
      onClose();
      setForm({ leave_type_id: '', start_date: '', end_date: '', reason: '', is_half_day: false });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit leave request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Apply for Leave">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Leave Type *</label>
          <select
            value={form.leave_type_id}
            onChange={e => setForm(f => ({ ...f, leave_type_id: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
          >
            <option value="">Select Leave Type...</option>
            {leaveTypes.length > 0 ? (
              leaveTypes.map(t => <option key={t.id} value={t.id}>{t.name || t.code}</option>)
            ) : (
              <>
                <option value="1">Annual Leave</option>
                <option value="2">Sick Leave</option>
                <option value="3">Casual Leave</option>
              </>
            )}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Start Date *"
            type="date"
            value={form.start_date}
            onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
            required
          />
          <Input
            label="End Date *"
            type="date"
            value={form.end_date}
            onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Reason</label>
          <textarea
            value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            rows={3}
            placeholder="Specify reason for leave..."
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_half_day"
            checked={form.is_half_day}
            onChange={e => setForm(f => ({ ...f, is_half_day: e.target.checked }))}
            className="h-4 w-4 rounded accent-indigo-600"
          />
          <label htmlFor="is_half_day" className="text-sm text-gray-300">Half Day Leave</label>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Submit Request</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function LeaveRequestsPage() {
  const [requests, setRequests] = useState([]);
  const [balances, setBalances] = useState([]);
  const [leaveTypes, setLeaveTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [applyOpen, setApplyOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const { hasPermission } = usePermission();

  const canApprove = hasPermission('leave.approve');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [reqRes, balRes, typesRes] = await Promise.all([
        leaveService.getRequests({ limit: 100 }),
        leaveService.getBalances().catch(() => ({ data: [] })),
        leaveService.getLeaveTypes().catch(() => ({ data: [] })),
      ]);
      setRequests(Array.isArray(reqRes.data) ? reqRes.data : (reqRes.data?.items || []));
      setBalances(Array.isArray(balRes.data) ? balRes.data : []);
      setLeaveTypes(Array.isArray(typesRes.data) ? typesRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load leave data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleApprove = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await leaveService.approveRequest(id, 'approved', 'Approved via dashboard');
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve request');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleReject = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: true }));
    try {
      await leaveService.approveRequest(id, 'rejected', 'Rejected via dashboard');
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject request');
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const pendingCount = requests.filter(r => normalizeStatus(r.status) === 'PENDING').length;
  const approvedCount = requests.filter(r => normalizeStatus(r.status) === 'APPROVED').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Calendar className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Leave Requests</h1>
              <p className="mt-1 text-sm text-gray-400">Manage employee leave requests, approvals, and balance tracking</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setApplyOpen(true)}>
              <Plus className="h-4 w-4" /> Apply Leave
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Total Requests</p>
          <p className="text-3xl font-bold text-white mt-2">{requests.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Pending Approval</p>
          <p className="text-3xl font-bold text-amber-400 mt-2">{pendingCount}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Approved</p>
          <p className="text-3xl font-bold text-green-400 mt-2">{approvedCount}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Active Entitlements</p>
          <p className="text-3xl font-bold text-indigo-400 mt-2">{balances.length || leaveTypes.length || 3}</p>
        </Card>
      </div>

      {/* Requests Table */}
      <Card className="overflow-hidden p-0">
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <CardTitle>Leave Requests ({requests.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-10 text-center text-sm text-gray-500">Loading leave requests…</div>
          ) : requests.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="h-12 w-12 text-gray-700 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No leave requests found.</p>
              <Button className="mt-4" onClick={() => setApplyOpen(true)}>
                <Plus className="h-4 w-4" /> Apply for Leave
              </Button>
            </div>
          ) : (
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3">Employee</th>
                  <th className="px-6 py-3">Start Date</th>
                  <th className="px-6 py-3">End Date</th>
                  <th className="px-6 py-3">Reason</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {requests.map(r => {
                  const style = STATUS_STYLES[normalizeStatus(r.status)] || STATUS_STYLES.PENDING;
                  return (
                    <tr key={r.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-gray-500" />
                          #{r.user_id}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-gray-300 font-mono text-xs">{r.start_date}</td>
                      <td className="px-6 py-4 text-gray-300 font-mono text-xs">{r.end_date}</td>
                      <td className="px-6 py-4 text-gray-400 text-xs max-w-xs truncate">{r.reason || '—'}</td>
                      <td className="px-6 py-4">
                        <span
                          className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                          style={{ background: `${style.color}1a`, color: style.color }}
                        >
                          {style.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {normalizeStatus(r.status) === 'PENDING' && canApprove && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleApprove(r.id)}
                              disabled={actionLoading[r.id]}
                              className="inline-flex items-center gap-1 rounded-lg bg-green-500/10 px-2.5 py-1.5 text-xs font-medium text-green-400 hover:bg-green-500/20 transition-colors disabled:opacity-50"
                            >
                              <Check className="h-3 w-3" /> Approve
                            </button>
                            <button
                              onClick={() => handleReject(r.id)}
                              disabled={actionLoading[r.id]}
                              className="inline-flex items-center gap-1 rounded-lg bg-red-500/10 px-2.5 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                            >
                              <X className="h-3 w-3" /> Reject
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <ApplyLeaveModal
        isOpen={applyOpen}
        onClose={() => setApplyOpen(false)}
        onSuccess={refresh}
        leaveTypes={leaveTypes}
      />
    </div>
  );
}
