import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Plus,
  RefreshCw,
  Clock,
  Navigation
} from 'lucide-react';
import api from '../services/apiClient';

export default function BranchManagementPage() {
  const [branches, setBranches] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({
    code: '',
    name: '',
    branch_type: 'HQ',
    address: '',
    city: '',
    timezone: 'Asia/Kolkata'
  });

  const fetchBranches = async () => {
    try {
      const res = await api.get('/branches');
      setBranches(res.data);
    } catch (err) {
      console.error('Failed to load branches:', err);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Fetch remote branches after mount.
    fetchBranches();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post('/branches', form);
      setModal(false);
      setForm({ code: '', name: '', branch_type: 'HQ', address: '', city: '', timezone: 'Asia/Kolkata' });
      fetchBranches();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create branch');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <MapPin className="h-7 w-7 text-emerald-400" />
            Branch & Office Locations
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Physical facilities, office locations, regional hubs, timezones, and geofencing configurations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchBranches}
            className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-lg shadow-emerald-600/30 transition"
          >
            <Plus className="h-4 w-4" />
            Add Branch
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {branches.map((b) => (
          <div key={b.id} className="glass p-5 rounded-2xl border border-gray-800 space-y-4">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono font-semibold">
                {b.code}
              </span>
              <span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-300">
                {b.branch_type}
              </span>
            </div>

            <div>
              <h3 className="text-lg font-bold text-white">{b.name}</h3>
              <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                <MapPin className="h-3.5 w-3.5 text-gray-500" />
                {b.city ? `${b.city}, ${b.country}` : b.country}
              </p>
            </div>

            <div className="pt-3 border-t border-gray-800/80 grid grid-cols-2 gap-2 text-xs text-gray-400">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-gray-500" />
                <span>{b.timezone}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Navigation className="h-3.5 w-3.5 text-gray-500" />
                <span>{b.geofence_radius_meters}m radius</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {modal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-md rounded-2xl border border-gray-800 p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Create Office Branch</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <input
                type="text"
                placeholder="Branch Code (e.g. BR-BLR-01)"
                required
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <input
                type="text"
                placeholder="Branch Name (e.g. Innovation Hub)"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <select
                value={form.branch_type}
                onChange={(e) => setForm({ ...form, branch_type: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="HQ">Headquarters (HQ)</option>
                <option value="REGIONAL">Regional Office</option>
                <option value="SITE">On-Site Facility</option>
                <option value="REMOTE">Remote Hub</option>
              </select>
              <input
                type="text"
                placeholder="City"
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModal(false)} className="px-4 py-2 text-xs text-gray-400">
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-xs bg-emerald-600 text-white rounded-xl font-medium">
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
