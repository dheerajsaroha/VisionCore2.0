import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  Plus,
  RefreshCw
} from 'lucide-react';
import api from '../services/apiClient';

export default function PositionManagementPage() {
  const [positions, setPositions] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({
    code: '',
    title: '',
    grade: 'L3',
    band: 'Engineering',
    headcount_capacity: 1
  });

  const fetchPositions = async () => {
    try {
      const res = await api.get('/positions');
      setPositions(res.data);
    } catch (err) {
      console.error('Failed to load positions:', err);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Fetch remote positions after mount.
    fetchPositions();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post('/positions', form);
      setModal(false);
      setForm({ code: '', title: '', grade: 'L3', band: 'Engineering', headcount_capacity: 1 });
      fetchPositions();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create position');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Briefcase className="h-7 w-7 text-indigo-400" />
            Job Positions & Grades
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Enterprise position catalog, job grades, bands, salary brackets, and reporting structures.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchPositions}
            className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-lg shadow-indigo-600/30 transition"
          >
            <Plus className="h-4 w-4" />
            Create Position
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {positions.map((p) => (
          <div key={p.id} className="glass p-5 rounded-2xl border border-gray-800 space-y-4">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-400 text-xs font-mono font-semibold">
                {p.code}
              </span>
              <span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-300">
                Grade: {p.grade || 'N/A'}
              </span>
            </div>

            <div>
              <h3 className="text-lg font-bold text-white">{p.title}</h3>
              <p className="text-xs text-gray-400 mt-1">Band: {p.band || 'General'}</p>
            </div>

            <div className="pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs text-gray-400">
              <span>Capacity: {p.headcount_capacity} headcount</span>
              <span className="text-emerald-400">Active</span>
            </div>
          </div>
        ))}
      </div>

      {modal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-md rounded-2xl border border-gray-800 p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Create Position</h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <input
                type="text"
                placeholder="Code (e.g. POS-ENG-SR)"
                required
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
              <input
                type="text"
                placeholder="Title (e.g. Principal Software Engineer)"
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="Grade (e.g. L5)"
                  value={form.grade}
                  onChange={(e) => setForm({ ...form, grade: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <input
                  type="text"
                  placeholder="Band (e.g. Engineering)"
                  value={form.band}
                  onChange={(e) => setForm({ ...form, band: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModal(false)} className="px-4 py-2 text-xs text-gray-400">
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-xs bg-indigo-600 text-white rounded-xl font-medium">
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
