import React, { useState, useEffect, useCallback } from 'react';
import {
  CalendarDays, Plus, Edit2, RefreshCw, Clock, Users,
  SunMedium, Moon, Repeat, GitBranch, CheckCircle2
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

const SHIFT_TYPE_STYLES = {
  FIXED: { color: '#6366f1', icon: Clock },
  FLEXIBLE: { color: '#22c55e', icon: SunMedium },
  ROTATIONAL: { color: '#f59e0b', icon: Repeat },
  NIGHT: { color: '#a855f7', icon: Moon },
  SPLIT: { color: '#3b82f6', icon: GitBranch },
};

function ShiftTypeTag({ type }) {
  const style = SHIFT_TYPE_STYLES[type] || SHIFT_TYPE_STYLES.FIXED;
  const Icon = style.icon;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
      style={{ background: `${style.color}1a`, color: style.color }}>
      <Icon className="h-3 w-3" /> {type}
    </span>
  );
}

function TemplateModal({ isOpen, onClose, initial, onSuccess }) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    shift_type: initial?.shift_type || 'FIXED',
    start_time: initial?.start_time?.slice(0, 5) || '09:00',
    end_time: initial?.end_time?.slice(0, 5) || '18:00',
    description: initial?.description || '',
    is_active: initial?.is_active ?? true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      if (initial?.id) {
        await workforceService.shifts.updateTemplate(initial.id, form);
      } else {
        await workforceService.shifts.createTemplate(form);
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save shift template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={initial?.id ? 'Edit Shift Template' : 'Create Shift Template'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        <Input label="Template Name *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required placeholder="e.g. Morning Shift" />
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Shift Type</label>
          <select value={form.shift_type} onChange={e => setForm(f => ({ ...f, shift_type: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
            {Object.keys(SHIFT_TYPE_STYLES).map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Time" type="time" value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} />
          <Input label="End Time" type="time" value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} />
        </div>
        <div className="flex items-center gap-2">
          <input type="checkbox" id="is_active_tpl" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} className="h-4 w-4 rounded accent-indigo-600" />
          <label htmlFor="is_active_tpl" className="text-sm text-gray-300">Active</label>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>{initial?.id ? 'Update' : 'Create'} Template</Button>
        </div>
      </form>
    </Modal>
  );
}

function AssignmentModal({ isOpen, onClose, templates, onSuccess }) {
  const [form, setForm] = useState({ user_id: '', shift_template_id: '', start_date: '', end_date: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await workforceService.shifts.assign({
        user_id: parseInt(form.user_id),
        shift_template_id: parseInt(form.shift_template_id) || undefined,
        start_date: form.start_date,
        end_date: form.end_date,
      });
      onSuccess();
      onClose();
      setForm({ user_id: '', shift_template_id: '', start_date: '', end_date: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to assign shift');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Assign Shift">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        <Input label="User ID *" type="number" value={form.user_id} onChange={e => setForm(f => ({ ...f, user_id: e.target.value }))} required placeholder="Employee user ID" />
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Shift Template</label>
          <select value={form.shift_template_id} onChange={e => setForm(f => ({ ...f, shift_template_id: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
            <option value="">Select template…</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name} ({t.shift_type})</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Start Date" type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} required />
          <Input label="End Date" type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} required />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Assign Shift</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function ShiftCalendarPage() {
  const [templates, setTemplates] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [templateModal, setTemplateModal] = useState(null); // null | 'create' | editObj
  const [assignModal, setAssignModal] = useState(false);
  const [tab, setTab] = useState('templates');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [tplRes, assignRes] = await Promise.all([
        workforceService.shifts.templates(false),
        workforceService.shifts.assignments({ limit: 50 }),
      ]);
      setTemplates(Array.isArray(tplRes.data) ? tplRes.data : []);
      setAssignments(Array.isArray(assignRes.data) ? assignRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load shift data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <CalendarDays className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Shift Management</h1>
              <p className="mt-1 text-sm text-gray-400">Configure shift templates and manage employee shift assignments</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            {tab === 'templates' ? (
              <Button onClick={() => setTemplateModal('create')}>
                <Plus className="h-4 w-4" /> New Template
              </Button>
            ) : (
              <Button onClick={() => setAssignModal(true)}>
                <Plus className="h-4 w-4" /> Assign Shift
              </Button>
            )}
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Templates</p>
          <p className="text-3xl font-bold text-white mt-2">{templates.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Active Templates</p>
          <p className="text-3xl font-bold text-white mt-2">{templates.filter(t => t.is_active).length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Assignments</p>
          <p className="text-3xl font-bold text-white mt-2">{assignments.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Active Assignments</p>
          <p className="text-3xl font-bold text-white mt-2">{assignments.filter(a => a.is_active).length}</p>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-gray-900 p-1 w-fit border border-gray-800">
        {['templates', 'assignments'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Templates Tab */}
      {tab === 'templates' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Shift Templates ({templates.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading…</div>
            ) : templates.length === 0 ? (
              <div className="p-12 text-center">
                <Clock className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No shift templates yet.</p>
                <Button className="mt-4" onClick={() => setTemplateModal('create')}>
                  <Plus className="h-4 w-4" /> Create First Template
                </Button>
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">Name</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Start</th>
                    <th className="px-6 py-3">End</th>
                    <th className="px-6 py-3">Hours</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {templates.map(t => (
                    <tr key={t.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{t.name}</td>
                      <td className="px-6 py-4"><ShiftTypeTag type={t.shift_type} /></td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-300">{t.start_time?.slice(0, 5)}</td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-300">{t.end_time?.slice(0, 5)}</td>
                      <td className="px-6 py-4 text-gray-300">{t.total_hours ? `${t.total_hours}h` : '—'}</td>
                      <td className="px-6 py-4">
                        {t.is_active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2.5 py-1 text-xs text-green-400">
                            <CheckCircle2 className="h-3 w-3" /> Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-gray-700/50 px-2.5 py-1 text-xs text-gray-500">Inactive</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <button onClick={() => setTemplateModal(t)}
                          className="inline-flex items-center gap-1 rounded-lg bg-indigo-500/10 px-2.5 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-500/20 transition-colors">
                          <Edit2 className="h-3 w-3" /> Edit
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

      {/* Assignments Tab */}
      {tab === 'assignments' && (
        <Card className="overflow-hidden p-0">
          <CardHeader className="border-b border-gray-800 px-6 py-5">
            <CardTitle>Shift Assignments ({assignments.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            {loading ? (
              <div className="p-10 text-center text-sm text-gray-500">Loading…</div>
            ) : assignments.length === 0 ? (
              <div className="p-12 text-center">
                <Users className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                <p className="text-sm text-gray-500">No shift assignments yet.</p>
                <Button className="mt-4" onClick={() => setAssignModal(true)}>
                  <Plus className="h-4 w-4" /> Assign Shift
                </Button>
              </div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3">User ID</th>
                    <th className="px-6 py-3">Shift / Template</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Start Date</th>
                    <th className="px-6 py-3">End Date</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {assignments.map(a => (
                    <tr key={a.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">#{a.user_id}</td>
                      <td className="px-6 py-4 text-gray-300">
                        {a.shift_template_id ? `Template #${a.shift_template_id}` : a.shift_id ? `Shift #${a.shift_id}` : '—'}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-medium text-indigo-400">
                          {a.assignment_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-300 font-mono text-xs">{a.start_date}</td>
                      <td className="px-6 py-4 text-gray-300 font-mono text-xs">{a.end_date}</td>
                      <td className="px-6 py-4">
                        {a.is_active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2.5 py-1 text-xs text-green-400">
                            <CheckCircle2 className="h-3 w-3" /> Active
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-gray-700/50 px-2.5 py-1 text-xs text-gray-500">Ended</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <TemplateModal
        isOpen={!!templateModal}
        onClose={() => setTemplateModal(null)}
        initial={templateModal === 'create' ? undefined : templateModal}
        onSuccess={refresh}
      />
      <AssignmentModal isOpen={assignModal} onClose={() => setAssignModal(false)} templates={templates} onSuccess={refresh} />
    </div>
  );
}
