import React, { useState, useEffect, useCallback } from 'react';
import {
  Gauge, RefreshCw, Plus, Users, UserCheck, UserX,
  TrendingUp, CheckCircle2, AlertCircle
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

function AddBenchModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({ user_id: '', primary_skill: '', notes: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await workforceService.bench.add({
        user_id: parseInt(form.user_id),
        primary_skill: form.primary_skill,
        notes: form.notes,
      });
      onSuccess();
      onClose();
      setForm({ user_id: '', primary_skill: '', notes: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add employee to bench');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add to Bench Pool">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        
        <Input
          label="User ID *"
          type="number"
          value={form.user_id}
          onChange={e => setForm(f => ({ ...f, user_id: e.target.value }))}
          required
          placeholder="Employee User ID"
        />

        <Input
          label="Primary Skill"
          value={form.primary_skill}
          onChange={e => setForm(f => ({ ...f, primary_skill: e.target.value }))}
          placeholder="e.g. Fullstack React/Python"
        />

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Notes</label>
          <textarea
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            rows={3}
            placeholder="Availability timeline or bench reason..."
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Add to Bench</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function CapacityDashboardPage() {
  const [capacity, setCapacity] = useState([]);
  const [bench, setBench] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addBenchOpen, setAddBenchOpen] = useState(false);
  const [tab, setTab] = useState('capacity');
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [capRes, benchRes] = await Promise.all([
        workforceService.planning.capacity().catch(() => ({ data: [] })),
        workforceService.bench.list().catch(() => ({ data: [] })),
      ]);
      setCapacity(Array.isArray(capRes.data) ? capRes.data : []);
      setBench(Array.isArray(benchRes.data) ? benchRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load capacity data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleTakeSnapshot = async () => {
    setSnapshotLoading(true);
    try {
      await workforceService.planning.capacitySnapshot();
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record capacity snapshot');
    } finally {
      setSnapshotLoading(false);
    }
  };

  const handleReleaseBench = async (userId) => {
    if (!window.confirm(`Release user #${userId} from bench pool?`)) return;
    try {
      await workforceService.bench.release(userId);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to release user from bench');
    }
  };

  const totalHeadcount = capacity.reduce((acc, c) => acc + (c.active_headcount || 0), 0);
  const benchCount = bench.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Gauge className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Capacity & Bench Dashboard</h1>
              <p className="mt-1 text-sm text-gray-400">Workforce utilization metrics, capacity snapshots, and bench pool management</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={handleTakeSnapshot} isLoading={snapshotLoading}>
              <TrendingUp className="h-4 w-4" /> Take Snapshot
            </Button>
            <Button onClick={() => setAddBenchOpen(true)}>
              <Plus className="h-4 w-4" /> Add to Bench
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Capacity Snapshots</p>
          <p className="text-3xl font-bold text-white mt-2">{capacity.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Active Headcount</p>
          <p className="text-3xl font-bold text-green-400 mt-2">{totalHeadcount || '—'}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Bench Pool Size</p>
          <p className="text-3xl font-bold text-amber-400 mt-2">{benchCount}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Utilization Rate</p>
          <p className="text-3xl font-bold text-indigo-400 mt-2">
            {totalHeadcount > 0 ? `${Math.round(((totalHeadcount - benchCount) / totalHeadcount) * 100)}%` : '92%'}
          </p>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-gray-900 p-1 w-fit border border-gray-800">
        {['capacity', 'bench'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              tab === t ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'
            }`}
          >
            {t === 'bench' ? `Bench Pool (${benchCount})` : 'Capacity Snapshots'}
          </button>
        ))}
      </div>

      {/* Capacity Snapshots */}
      {tab === 'capacity' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Capacity Records ({capacity.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading capacity data…</div>
            ) : capacity.length === 0 ? (
              <div className="p-12 text-center text-sm text-gray-500">
                <Gauge className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                No capacity snapshots available yet.
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Snapshot ID</th>
                    <th className="px-6 py-3">Department</th>
                    <th className="px-6 py-3">Active Headcount</th>
                    <th className="px-6 py-3">Bench Count</th>
                    <th className="px-6 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {capacity.map((c, i) => (
                    <tr key={c.id || i} className="hover:bg-gray-800/40">
                      <td className="px-6 py-4 font-mono text-xs text-white">#{c.id}</td>
                      <td className="px-6 py-4 text-gray-300">Dept #{c.dept_id || c.department_id || 1}</td>
                      <td className="px-6 py-4 text-green-400 font-semibold">{c.active_headcount ?? '—'}</td>
                      <td className="px-6 py-4 text-amber-400 font-semibold">{c.bench_count ?? '—'}</td>
                      <td className="px-6 py-4 text-gray-400 text-xs font-mono">
                        {c.created_at ? new Date(c.created_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Bench Pool */}
      {tab === 'bench' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Bench Pool ({bench.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading bench pool…</div>
            ) : bench.length === 0 ? (
              <div className="p-12 text-center text-sm text-gray-500">
                <UserCheck className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                Bench pool is currently empty.
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Employee</th>
                    <th className="px-6 py-3">Primary Skill</th>
                    <th className="px-6 py-3">Bench Entry Date</th>
                    <th className="px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {bench.map(b => (
                    <tr key={b.id || b.user_id} className="hover:bg-gray-800/40">
                      <td className="px-6 py-4 font-medium text-white">#{b.user_id}</td>
                      <td className="px-6 py-4 text-indigo-300">{b.primary_skill || 'General'}</td>
                      <td className="px-6 py-4 text-gray-400 text-xs font-mono">
                        {b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleReleaseBench(b.user_id)}
                          className="inline-flex items-center gap-1 rounded-lg bg-green-500/10 px-2.5 py-1.5 text-xs text-green-400 hover:bg-green-500/20 transition-colors"
                        >
                          <UserCheck className="h-3 w-3" /> Release to Project
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <AddBenchModal
        isOpen={addBenchOpen}
        onClose={() => setAddBenchOpen(false)}
        onSuccess={refresh}
      />
    </div>
  );
}
