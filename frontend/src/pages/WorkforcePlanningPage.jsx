import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, Plus, RefreshCw, Briefcase, TrendingUp, Building2,
  CheckCircle2, AlertCircle, FileText
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

function CreateHeadcountModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({
    dept_id: '',
    period_year: new Date().getFullYear(),
    period_month: new Date().getMonth() + 1,
    planned_headcount: 10,
    approved_headcount: 10,
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await workforceService.planning.createHeadcount({
        dept_id: parseInt(form.dept_id) || 1,
        period_year: parseInt(form.period_year),
        period_month: parseInt(form.period_month),
        planned_headcount: parseInt(form.planned_headcount),
        approved_headcount: parseInt(form.approved_headcount),
        notes: form.notes,
      });
      onSuccess();
      onClose();
      setForm({
        dept_id: '',
        period_year: new Date().getFullYear(),
        period_month: new Date().getMonth() + 1,
        planned_headcount: 10,
        approved_headcount: 10,
        notes: '',
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create headcount plan');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Headcount Plan">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        
        <Input
          label="Department ID *"
          type="number"
          value={form.dept_id}
          onChange={e => setForm(f => ({ ...f, dept_id: e.target.value }))}
          required
          placeholder="e.g. 1"
        />

        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Year *"
            type="number"
            value={form.period_year}
            onChange={e => setForm(f => ({ ...f, period_year: e.target.value }))}
            required
          />
          <Input
            label="Month (1-12) *"
            type="number"
            min={1}
            max={12}
            value={form.period_month}
            onChange={e => setForm(f => ({ ...f, period_month: e.target.value }))}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Planned Headcount *"
            type="number"
            value={form.planned_headcount}
            onChange={e => setForm(f => ({ ...f, planned_headcount: e.target.value }))}
            required
          />
          <Input
            label="Approved Headcount *"
            type="number"
            value={form.approved_headcount}
            onChange={e => setForm(f => ({ ...f, approved_headcount: e.target.value }))}
            required
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Notes</label>
          <textarea
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            rows={3}
            placeholder="Plan justification or budget reference..."
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Create Plan</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function WorkforcePlanningPage() {
  const [plans, setPlans] = useState([]);
  const [vacancies, setVacancies] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [tab, setTab] = useState('plans');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [plansRes, vacanciesRes, forecastsRes] = await Promise.all([
        workforceService.planning.headcount().catch(() => ({ data: [] })),
        workforceService.planning.vacancies().catch(() => ({ data: [] })),
        workforceService.planning.forecasts().catch(() => ({ data: [] })),
      ]);
      setPlans(Array.isArray(plansRes.data) ? plansRes.data : (plansRes.data?.items || []));
      setVacancies(Array.isArray(vacanciesRes.data) ? vacanciesRes.data : []);
      setForecasts(Array.isArray(forecastsRes.data) ? forecastsRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load workforce planning data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const totalPlanned = plans.reduce((acc, p) => acc + (p.planned_headcount || 0), 0);
  const totalApproved = plans.reduce((acc, p) => acc + (p.approved_headcount || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Users className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Workforce Planning</h1>
              <p className="mt-1 text-sm text-gray-400">Manage departmental headcount plans, vacancies, and growth forecasts</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Create Plan
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Total Headcount Plans</p>
          <p className="text-3xl font-bold text-white mt-2">{plans.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Planned Headcount</p>
          <p className="text-3xl font-bold text-indigo-400 mt-2">{totalPlanned}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Approved Headcount</p>
          <p className="text-3xl font-bold text-green-400 mt-2">{totalApproved}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Open Vacancies</p>
          <p className="text-3xl font-bold text-amber-400 mt-2">{vacancies.length}</p>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-gray-900 p-1 w-fit border border-gray-800">
        {['plans', 'vacancies', 'forecasts'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              tab === t ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Plans Tab */}
      {tab === 'plans' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Headcount Plans ({plans.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading headcount plans…</div>
            ) : plans.length === 0 ? (
              <div className="p-12 text-center">
                <Building2 className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No headcount plans created yet.</p>
                <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4" /> Create First Plan
                </Button>
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Department ID</th>
                    <th className="px-6 py-3">Period</th>
                    <th className="px-6 py-3">Planned</th>
                    <th className="px-6 py-3">Approved</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {plans.map(p => (
                    <tr key={p.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">Dept #{p.dept_id}</td>
                      <td className="px-6 py-4 text-gray-300 font-mono text-xs">{p.period_year}-{String(p.period_month).padStart(2, '0')}</td>
                      <td className="px-6 py-4 text-indigo-300 font-semibold">{p.planned_headcount}</td>
                      <td className="px-6 py-4 text-green-400 font-semibold">{p.approved_headcount}</td>
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-semibold text-green-400">
                          {p.status || 'APPROVED'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Vacancies Tab */}
      {tab === 'vacancies' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Open Vacancies ({vacancies.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {vacancies.length === 0 ? (
              <div className="p-12 text-center text-sm text-gray-500">
                <Briefcase className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                No active vacancy records tracked.
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Title</th>
                    <th className="px-6 py-3">Department</th>
                    <th className="px-6 py-3">Target Date</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {vacancies.map((v, i) => (
                    <tr key={v.id || i} className="hover:bg-gray-800/40">
                      <td className="px-6 py-4 font-medium text-white">{v.title || v.position_title}</td>
                      <td className="px-6 py-4 text-gray-300">{v.department || `Dept #${v.dept_id}`}</td>
                      <td className="px-6 py-4 text-gray-300 text-xs font-mono">{v.target_date || '—'}</td>
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-400">
                          {v.status || 'OPEN'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Forecasts Tab */}
      {tab === 'forecasts' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Growth Forecasts ({forecasts.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {forecasts.length === 0 ? (
              <div className="p-12 text-center text-sm text-gray-500">
                <TrendingUp className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                No growth forecasts generated.
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Forecast Name</th>
                    <th className="px-6 py-3">Target Headcount</th>
                    <th className="px-6 py-3">Horizon</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {forecasts.map((f, i) => (
                    <tr key={f.id || i} className="hover:bg-gray-800/40">
                      <td className="px-6 py-4 font-medium text-white">{f.name || `Forecast #${f.id}`}</td>
                      <td className="px-6 py-4 text-indigo-300 font-semibold">{f.target_headcount}</td>
                      <td className="px-6 py-4 text-gray-300 text-xs">{f.horizon_months ? `${f.horizon_months} Months` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <CreateHeadcountModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={refresh}
      />
    </div>
  );
}
