import React, { useState, useEffect, useCallback } from 'react';
import {
  FileSpreadsheet, Plus, RefreshCw, CheckCircle2, ArrowLeftRight, Check, X, AlertCircle
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

const ROSTER_STATUS = {
  DRAFT: { color: '#f59e0b', label: 'Draft' },
  PUBLISHED: { color: '#22c55e', label: 'Published' },
  ARCHIVED: { color: '#64748b', label: 'Archived' },
};

const SWAP_STATUS = {
  PENDING: { color: '#f59e0b' },
  APPROVED: { color: '#22c55e' },
  REJECTED: { color: '#ef4444' },
  CANCELLED: { color: '#64748b' },
};

function CreateRosterModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({ dept_id: '', title: '', start_date: '', end_date: '', roster_type: 'WEEKLY', notes: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await workforceService.rosters.create({ ...form, dept_id: parseInt(form.dept_id) || undefined });
      onSuccess();
      onClose();
      setForm({ dept_id: '', title: '', start_date: '', end_date: '', roster_type: 'WEEKLY', notes: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create roster');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Roster">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        <Input label="Roster Title *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} required placeholder="e.g. Engineering Week 32" />
        <Input label="Department ID" type="number" value={form.dept_id} onChange={e => setForm(f => ({ ...f, dept_id: e.target.value }))} placeholder="Optional department" />
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Roster Type</label>
          <select value={form.roster_type} onChange={e => setForm(f => ({ ...f, roster_type: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="CUSTOM">Custom</option>
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date *" type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} required />
          <Input label="End Date *" type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} required />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Create Roster</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function RosterPlannerPage() {
  const [rosters, setRosters] = useState([]);
  const [swaps, setSwaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [tab, setTab] = useState('rosters');
  const [publishing, setPublishing] = useState({});

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [rosterRes, swapRes] = await Promise.all([
        workforceService.rosters.list({ limit: 50 }),
        workforceService.shifts.swaps({ limit: 50 }),
      ]);
      setRosters(Array.isArray(rosterRes.data) ? rosterRes.data : []);
      setSwaps(Array.isArray(swapRes.data) ? swapRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load roster data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handlePublish = async (roster) => {
    if (!window.confirm(`Publish roster "${roster.title}"?`)) return;
    setPublishing(p => ({ ...p, [roster.id]: true }));
    try {
      await workforceService.rosters.publish(roster.id);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to publish roster');
    } finally {
      setPublishing(p => ({ ...p, [roster.id]: false }));
    }
  };

  const handleSwapAction = async (swapId, action) => {
    try {
      await workforceService.shifts.resolveSwap(swapId, { action, note: '' });
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to ${action} swap`);
    }
  };

  const draftCount = rosters.filter(r => r.status === 'DRAFT').length;
  const publishedCount = rosters.filter(r => r.status === 'PUBLISHED').length;
  const pendingSwaps = swaps.filter(s => s.status === 'PENDING').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <FileSpreadsheet className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Roster Planner</h1>
              <p className="mt-1 text-sm text-gray-400">Plan and publish departmental rosters, manage shift swaps</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Create Roster
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Total Rosters</p>
          <p className="text-3xl font-bold text-white mt-2">{rosters.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Draft</p>
          <p className="text-3xl font-bold text-amber-400 mt-2">{draftCount}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Published</p>
          <p className="text-3xl font-bold text-green-400 mt-2">{publishedCount}</p>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Pending Swaps</p>
              <p className="text-3xl font-bold text-white mt-2">{pendingSwaps}</p>
            </div>
            {pendingSwaps > 0 && <AlertCircle className="h-5 w-5 text-amber-400" />}
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-gray-900 p-1 w-fit border border-gray-800">
        {['rosters', 'swaps'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>
            {t === 'swaps' && pendingSwaps > 0 ? `Shift Swaps (${pendingSwaps})` : t === 'swaps' ? 'Shift Swaps' : 'Rosters'}
          </button>
        ))}
      </div>

      {tab === 'rosters' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Roster List ({rosters.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading…</div>
            ) : rosters.length === 0 ? (
              <div className="p-12 text-center">
                <FileSpreadsheet className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No rosters created yet.</p>
                <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4" /> Create First Roster
                </Button>
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Title</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Period</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Published</th>
                    <th className="px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {rosters.map(r => {
                    const statusStyle = ROSTER_STATUS[r.status] || ROSTER_STATUS.DRAFT;
                    return (
                      <tr key={r.id} className="hover:bg-gray-800/40 transition-colors">
                        <td className="px-6 py-4 font-medium text-white">{r.title}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-400">{r.roster_type}</span>
                        </td>
                        <td className="px-6 py-4 text-gray-300 text-xs font-mono">{r.start_date} → {r.end_date}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                            style={{ background: `${statusStyle.color}1a`, color: statusStyle.color }}>
                            {statusStyle.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-400 text-xs">
                          {r.published_at ? new Date(r.published_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-6 py-4">
                          {r.status === 'DRAFT' && (
                            <button
                              onClick={() => handlePublish(r)}
                              disabled={publishing[r.id]}
                              className="inline-flex items-center gap-1 rounded-lg bg-green-500/10 px-2.5 py-1.5 text-xs font-medium text-green-400 hover:bg-green-500/20 transition-colors disabled:opacity-50"
                            >
                              <CheckCircle2 className="h-3 w-3" /> {publishing[r.id] ? 'Publishing…' : 'Publish'}
                            </button>
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
      )}

      {tab === 'swaps' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Shift Swap Requests</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading…</div>
            ) : swaps.length === 0 ? (
              <div className="p-12 text-center">
                <ArrowLeftRight className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No shift swap requests found.</p>
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Requester</th>
                    <th className="px-6 py-3">Target</th>
                    <th className="px-6 py-3">Swap Date</th>
                    <th className="px-6 py-3">Reason</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {swaps.map(s => {
                    const swapStyle = SWAP_STATUS[s.status] || SWAP_STATUS.PENDING;
                    return (
                      <tr key={s.id} className="hover:bg-gray-800/40 transition-colors">
                        <td className="px-6 py-4 font-medium text-white">#{s.requester_user_id}</td>
                        <td className="px-6 py-4 text-gray-300">{s.target_user_id ? `#${s.target_user_id}` : 'Open'}</td>
                        <td className="px-6 py-4 text-gray-300 font-mono text-xs">{s.swap_date}</td>
                        <td className="px-6 py-4 text-gray-400 text-xs max-w-xs truncate">{s.reason || '—'}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                            style={{ background: `${swapStyle.color}1a`, color: swapStyle.color }}>
                            {s.status}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {s.status === 'PENDING' && (
                            <div className="flex gap-2">
                              <button onClick={() => handleSwapAction(s.id, 'approve')}
                                className="inline-flex items-center gap-1 rounded-lg bg-green-500/10 px-2.5 py-1.5 text-xs text-green-400 hover:bg-green-500/20 transition-colors">
                                <Check className="h-3 w-3" /> Approve
                              </button>
                              <button onClick={() => handleSwapAction(s.id, 'reject')}
                                className="inline-flex items-center gap-1 rounded-lg bg-red-500/10 px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-500/20 transition-colors">
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
      )}

      <CreateRosterModal isOpen={createOpen} onClose={() => setCreateOpen(false)} onSuccess={refresh} />
    </div>
  );
}
