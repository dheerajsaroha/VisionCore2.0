import React, { useState, useEffect, useCallback } from 'react';
import {
  SunMedium, Plus, RefreshCw, Calendar, Tag, CheckCircle2
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';

function CreateCalendarModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({ name: '', country_code: '', region: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await workforceService.holidays.createCalendar({
        name: form.name,
        country_code: form.country_code.trim() ? form.country_code.trim().toUpperCase() : null,
        region: form.region.trim() || null,
      });
      onSuccess();
      onClose();
      setForm({ name: '', country_code: '', region: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create calendar');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="New Holiday Calendar">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-300">Calendar Name</label>
          <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. India — Karnataka Public Holidays" required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Country Code</label>
            <Input value={form.country_code} onChange={e => setForm(f => ({ ...f, country_code: e.target.value }))} placeholder="IN" maxLength={3} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Region / State</label>
            <Input value={form.region} onChange={e => setForm(f => ({ ...f, region: e.target.value }))} placeholder="Karnataka" />
          </div>
        </div>
        <p className="text-xs text-gray-500">
          Setting a country and region scopes which pre-configured public holidays apply to this organisation.
        </p>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={loading}>Create Calendar</Button>
        </div>
      </form>
    </Modal>
  );
}

function AddHolidayModal({ isOpen, onClose, calendars = [], onSuccess }) {
  const [form, setForm] = useState({
    calendar_id: '',
    name: '',
    holiday_date: '',
    holiday_type: 'NATIONAL',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    const calId = form.calendar_id || (calendars[0]?.id ? String(calendars[0].id) : null);
    try {
      await workforceService.holidays.addEntry({
        name: form.name,
        holiday_date: form.holiday_date,
        holiday_type: form.holiday_type,
        calendar_id: calId ? Number(calId) : null,
      });
      onSuccess();
      onClose();
      setForm({ calendar_id: '', name: '', holiday_date: '', holiday_type: 'NATIONAL' });
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
            {calendars.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}{c.region ? ` — ${c.region}` : ''}
              </option>
            ))}
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
            <option value="RESTRICTED">Restricted Holiday</option>
            <option value="ORG_SPECIFIC">Company Holiday</option>
            <option value="OPTIONAL">Optional / Floating</option>
          </select>
          <p className="text-xs text-gray-500">
            Optional holidays are excluded from loss of pay; the other types are mandatory.
          </p>
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
  const [calOpen, setCalOpen] = useState(false);

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
            <Button variant="secondary" onClick={() => setCalOpen(true)}>
              <Plus className="h-4 w-4" /> New Calendar
            </Button>
            <Button onClick={() => setAddOpen(true)} disabled={!calendars.length}>
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
          <p className="text-3xl font-bold text-amber-400 mt-2">{entries.filter(e => e.holiday_type === 'OPTIONAL').length}</p>
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
                      {e.holiday_type === 'OPTIONAL' ? (
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

      <CreateCalendarModal
        isOpen={calOpen}
        onClose={() => setCalOpen(false)}
        onSuccess={refresh}
      />

      <AddHolidayModal
        isOpen={addOpen}
        onClose={() => setAddOpen(false)}
        calendars={calendars}
        onSuccess={refresh}
      />
    </div>
  );
}
