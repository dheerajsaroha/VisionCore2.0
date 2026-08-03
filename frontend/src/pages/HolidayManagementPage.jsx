import React, { useState, useEffect, useCallback } from 'react';
import {
  SunMedium, Plus, RefreshCw, Calendar, Tag, CheckCircle2
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

function AddHolidayModal({ isOpen, onClose, calendars = [], onSuccess }) {
  const [form, setForm] = useState({
    calendar_id: '',
    name: '',
    holiday_date: '',
    holiday_type: 'NATIONAL',
    is_optional: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    const calId = form.calendar_id || (calendars[0]?.id ? String(calendars[0].id) : '1');
    try {
      await workforceService.holidays.addEntry(calId, {
        name: form.name,
        holiday_date: form.holiday_date,
        holiday_type: form.holiday_type,
        is_optional: form.is_optional,
      });
      onSuccess();
      onClose();
      setForm({ calendar_id: '', name: '', holiday_date: '', holiday_type: 'NATIONAL', is_optional: false });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add holiday entry');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Holiday Entry">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{error}</div>}
        
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Holiday Calendar</label>
          <select
            value={form.calendar_id}
            onChange={e => setForm(f => ({ ...f, calendar_id: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {calendars.map(c => <option key={c.id} value={c.id}>{c.name} ({c.year})</option>)}
            {calendars.length === 0 && <option value="1">Default Corporate Calendar</option>}
          </select>
        </div>

        <Input
          label="Holiday Name *"
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          required
          placeholder="e.g. Independence Day"
        />

        <Input
          label="Holiday Date *"
          type="date"
          value={form.holiday_date}
          onChange={e => setForm(f => ({ ...f, holiday_date: e.target.value }))}
          required
        />

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">Holiday Type</label>
          <select
            value={form.holiday_type}
            onChange={e => setForm(f => ({ ...f, holiday_type: e.target.value }))}
            className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="NATIONAL">National Holiday</option>
            <option value="REGIONAL">Regional Holiday</option>
            <option value="COMPANY">Company Holiday</option>
            <option value="OPTIONAL">Optional / Floating</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_optional"
            checked={form.is_optional}
            onChange={e => setForm(f => ({ ...f, is_optional: e.target.checked }))}
            className="h-4 w-4 rounded accent-indigo-600"
          />
          <label htmlFor="is_optional" className="text-sm text-gray-300">Optional / Floating Holiday</label>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Add Holiday</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function HolidayManagementPage() {
  const [calendars, setCalendars] = useState([]);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [calRes, entryRes] = await Promise.all([
        workforceService.holidays.calendars().catch(() => ({ data: [] })),
        workforceService.holidays.entries().catch(() => ({ data: [] })),
      ]);
      setCalendars(Array.isArray(calRes.data) ? calRes.data : []);
      setEntries(Array.isArray(entryRes.data) ? entryRes.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load holiday calendars');
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
              <SunMedium className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Holiday Management</h1>
              <p className="mt-1 text-sm text-gray-400">Configure corporate holiday calendars, regional observances, and floating holidays</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add Holiday
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Active Calendars</p>
          <p className="text-3xl font-bold text-white mt-2">{calendars.length || 1}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Total Holidays</p>
          <p className="text-3xl font-bold text-indigo-400 mt-2">{entries.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">Optional / Floating</p>
          <p className="text-3xl font-bold text-amber-400 mt-2">{entries.filter(e => e.is_optional).length}</p>
        </Card>
      </div>

      {/* Entries Table */}
      <Card className="overflow-hidden p-0">
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <CardTitle>Holiday Entries ({entries.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-10 text-center text-sm text-gray-500">Loading holiday entries…</div>
          ) : entries.length === 0 ? (
            <div className="p-12 text-center text-sm text-gray-500">
              <SunMedium className="h-12 w-12 text-gray-700 mx-auto mb-3" />
              No holiday entries defined.
              <div className="mt-4">
                <Button onClick={() => setAddOpen(true)}>
                  <Plus className="h-4 w-4" /> Add First Holiday
                </Button>
              </div>
            </div>
          ) : (
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3">Holiday Name</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Floating</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {entries.map(e => (
                  <tr key={e.id} className="hover:bg-gray-800/40">
                    <td className="px-6 py-4 font-medium text-white">{e.name}</td>
                    <td className="px-6 py-4 text-gray-300 font-mono text-xs">{e.holiday_date}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-semibold text-indigo-400">
                        {e.holiday_type || 'NATIONAL'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {e.is_optional ? (
                        <span className="inline-flex rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-400">
                          Optional
                        </span>
                      ) : (
                        <span className="inline-flex rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-semibold text-green-400">
                          Mandatory
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <AddHolidayModal
        isOpen={addOpen}
        onClose={() => setAddOpen(false)}
        calendars={calendars}
        onSuccess={refresh}
      />
    </div>
  );
}
