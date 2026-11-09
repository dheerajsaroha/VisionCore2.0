import React, { useState, useEffect, useCallback } from 'react';
import {
  Monitor, Plus, Edit2, PowerOff, Wifi, Smartphone, MapPin,
  Activity, RefreshCw, CheckCircle2, XCircle, Shield
} from 'lucide-react';
import { workforceService } from '../services/workforceService';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import '../components/ui/Input';

const CHANNELS = ['FACE', 'QR', 'GPS', 'BLE', 'NFC', 'WiFi', 'KIOSK', 'MANUAL'];

const CHANNEL_STYLES = {
  FACE: { color: '#6366f1', icon: Activity },
  QR: { color: '#3b82f6', icon: Smartphone },
  GPS: { color: '#22c55e', icon: MapPin },
  BLE: { color: '#a855f7', icon: Wifi },
  NFC: { color: '#14b8a6', icon: Shield },
  WiFi: { color: '#f59e0b', icon: Wifi },
  KIOSK: { color: '#f97316', icon: Monitor },
  MANUAL: { color: '#64748b', icon: Activity },
};

function DeviceForm({ initial = {}, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState({
    name: initial.device_name || '',
    device_type: initial.device_type || 'FACE',
    serial_number: initial.serial_number || '',
    model: initial.model || '',
    location: initial.location || '',
    is_trusted: initial.is_trusted ?? true,
    is_active: initial.is_active ?? true,
    description: initial.description || '',
  });

  const handleSubmit = (e) => { e.preventDefault(); onSubmit(form); };

  const field = (key, label, type = 'text', placeholder = '') => (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1.5">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {field('name', 'Device Name *', 'text', 'e.g. Main Entrance Kiosk')}
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1.5">Channel / Type</label>
        <select
          value={form.device_type}
          onChange={e => setForm(f => ({ ...f, device_type: e.target.value }))}
          className="w-full rounded-xl bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {CHANNELS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      {field('serial_number', 'Serial Number', 'text', 'SN-XXXX')}
      {field('model', 'Model', 'text', 'e.g. ZKTeco F22')}
      {field('location', 'Location', 'text', 'e.g. Building A - Ground Floor')}
      <div className="flex gap-6">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={form.is_trusted} onChange={e => setForm(f => ({ ...f, is_trusted: e.target.checked }))}
            className="h-4 w-4 rounded accent-indigo-600" />
          <span className="text-sm text-gray-300">Trusted Device</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
            className="h-4 w-4 rounded accent-indigo-600" />
          <span className="text-sm text-gray-300">Active</span>
        </label>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" isLoading={loading}>{initial.id ? 'Update Device' : 'Register Device'}</Button>
      </div>
    </form>
  );
}

export default function AttendanceDevicesPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editDevice, setEditDevice] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await workforceService.devices.list();
      setDevices(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load devices');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleCreate = async (data) => {
    setSubmitting(true); setActionError('');
    try {
      await workforceService.devices.create(data);
      setCreateOpen(false);
      refresh();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to register device');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async (data) => {
    setSubmitting(true); setActionError('');
    try {
      await workforceService.devices.update(editDevice.id, data);
      setEditDevice(null);
      refresh();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to update device');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (device) => {
    if (!window.confirm(`Deactivate "${device.device_name}"?`)) return;
    try {
      await workforceService.devices.deactivate(device.id);
      refresh();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to deactivate device');
    }
  };

  const activeCount = devices.filter(d => d.is_active).length;
  const trustedCount = devices.filter(d => d.is_trusted).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950 via-gray-900 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-indigo-500/15 p-3">
              <Monitor className="h-7 w-7 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Attendance Devices</h1>
              <p className="mt-1 text-sm text-gray-400">Manage your attendance device registry across all channels</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={refresh} isLoading={loading}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Register Device
            </Button>
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Total Devices</p>
          <p className="text-3xl font-bold text-white mt-2">{devices.length}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Active</p>
          <div className="flex items-center gap-2 mt-2">
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            <p className="text-3xl font-bold text-white">{activeCount}</p>
          </div>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Trusted</p>
          <div className="flex items-center gap-2 mt-2">
            <Shield className="h-5 w-5 text-indigo-400" />
            <p className="text-3xl font-bold text-white">{trustedCount}</p>
          </div>
        </Card>
      </div>

      {/* Device Table */}
      <Card className="overflow-hidden p-0">
        <CardHeader className="border-b border-gray-800 px-6 py-5">
          <CardTitle>Device Registry</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-10 text-center text-sm text-gray-500">Loading devices…</div>
          ) : devices.length === 0 ? (
            <div className="p-12 text-center">
              <Monitor className="h-12 w-12 text-gray-700 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No attendance devices registered yet.</p>
              <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" /> Register First Device
              </Button>
            </div>
          ) : (
            <table className="min-w-full text-left text-sm">
              <thead className="bg-gray-950/60 text-xs uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-6 py-3">Device</th>
                  <th className="px-6 py-3">Type / Channel</th>
                  <th className="px-6 py-3">Serial</th>
                  <th className="px-6 py-3">Location</th>
                  <th className="px-6 py-3">Trust</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {devices.map(d => {
                  const ch = CHANNEL_STYLES[d.device_type] || CHANNEL_STYLES.MANUAL;
                  const ChIcon = ch.icon;
                  return (
                    <tr key={d.id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4">
                        <p className="font-medium text-white">{d.device_name}</p>
                        {d.model && <p className="text-xs text-gray-500">{d.model}</p>}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
                          style={{ background: `${ch.color}1a`, color: ch.color }}>
                          <ChIcon className="h-3 w-3" />
                          {d.device_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-400">{d.serial_number || '—'}</td>
                      <td className="px-6 py-4 text-gray-300 text-xs">{d.location || '—'}</td>
                      <td className="px-6 py-4">
                        {d.is_trusted ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-400">
                            <Shield className="h-3 w-3" /> Trusted
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                            <Shield className="h-3 w-3" /> Unverified
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {d.is_active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-400">
                            <CheckCircle2 className="h-3 w-3" /> Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-gray-700/50 px-2.5 py-1 text-xs font-medium text-gray-400">
                            <XCircle className="h-3 w-3" /> Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          <button
                            onClick={() => setEditDevice(d)}
                            className="inline-flex items-center gap-1 rounded-lg bg-indigo-500/10 px-2.5 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-500/20 transition-colors"
                          >
                            <Edit2 className="h-3 w-3" /> Edit
                          </button>
                          {d.is_active && (
                            <button
                              onClick={() => handleDeactivate(d)}
                              className="inline-flex items-center gap-1 rounded-lg bg-red-500/10 px-2.5 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
                            >
                              <PowerOff className="h-3 w-3" /> Deactivate
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Create Modal */}
      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Register Attendance Device">
        {actionError && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300 mb-4">{actionError}</div>}
        <DeviceForm onSubmit={handleCreate} onCancel={() => setCreateOpen(false)} loading={submitting} />
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={!!editDevice} onClose={() => setEditDevice(null)} title="Edit Device">
        {actionError && <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300 mb-4">{actionError}</div>}
        {editDevice && (
          <DeviceForm initial={editDevice} onSubmit={handleUpdate} onCancel={() => setEditDevice(null)} loading={submitting} />
        )}
      </Modal>
    </div>
  );
}
