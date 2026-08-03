import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  DollarSign,
  Plus,
  RefreshCw,
  Search,
  Building2
} from 'lucide-react';
import api from '../services/apiClient';

export default function BusinessUnitsPage() {
  const [businessUnits, setBusinessUnits] = useState([]);
  const [costCenters, setCostCenters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('units');

  const [buModal, setBuModal] = useState(false);
  const [buForm, setBuForm] = useState({ code: '', name: '', description: '' });

  const [ccModal, setCcModal] = useState(false);
  const [ccForm, setCcForm] = useState({ code: '', name: '', annual_budget: 0.0 });

  const fetchData = async () => {
    try {
      setLoading(true);
      const [buRes, ccRes] = await Promise.all([
        api.get('/business-units'),
        api.get('/cost-centers')
      ]);
      setBusinessUnits(buRes.data);
      setCostCenters(ccRes.data);
    } catch (err) {
      console.error('Failed to load BU/CC data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateBU = async (e) => {
    e.preventDefault();
    try {
      await api.post('/business-units', buForm);
      setBuModal(false);
      setBuForm({ code: '', name: '', description: '' });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create business unit');
    }
  };

  const handleCreateCC = async (e) => {
    e.preventDefault();
    try {
      await api.post('/cost-centers', ccForm);
      setCcModal(false);
      setCcForm({ code: '', name: '', annual_budget: 0.0 });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create cost center');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <GitBranch className="h-7 w-7 text-purple-400" />
            Business Units & Cost Centers
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Manage strategic corporate divisions and financial budget cost center allocations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {activeTab === 'units' ? (
            <button
              onClick={() => setBuModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium shadow-lg shadow-purple-600/30 transition"
            >
              <Plus className="h-4 w-4" />
              Add Business Unit
            </button>
          ) : (
            <button
              onClick={() => setCcModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-lg shadow-emerald-600/30 transition"
            >
              <Plus className="h-4 w-4" />
              Add Cost Center
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-800 pb-3">
        <button
          onClick={() => setActiveTab('units')}
          className={`px-4 py-2 rounded-xl font-medium text-sm transition ${
            activeTab === 'units'
              ? 'bg-purple-600/20 text-purple-400 border border-purple-500/30'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Business Units ({businessUnits.length})
        </button>
        <button
          onClick={() => setActiveTab('centers')}
          className={`px-4 py-2 rounded-xl font-medium text-sm transition ${
            activeTab === 'centers'
              ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Cost Centers ({costCenters.length})
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'units' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {businessUnits.map((bu) => (
            <div key={bu.id} className="glass p-5 rounded-2xl border border-gray-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-md bg-purple-500/10 text-purple-400 text-xs font-mono font-semibold">
                  {bu.code}
                </span>
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
              </div>
              <h3 className="text-lg font-bold text-white">{bu.name}</h3>
              <p className="text-xs text-gray-400">{bu.description || 'No description provided.'}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {costCenters.map((cc) => (
            <div key={cc.id} className="glass p-5 rounded-2xl border border-gray-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono font-semibold">
                  {cc.code}
                </span>
                <DollarSign className="h-4 w-4 text-emerald-400" />
              </div>
              <h3 className="text-lg font-bold text-white">{cc.name}</h3>
              <p className="text-sm font-semibold text-emerald-400">
                Annual Budget: ₹{Number(cc.annual_budget || 0).toLocaleString('en-IN')}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      {buModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-md rounded-2xl border border-gray-800 p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Create Business Unit</h3>
            <form onSubmit={handleCreateBU} className="space-y-3">
              <input
                type="text"
                placeholder="Code (e.g. BU-DIGITAL)"
                required
                value={buForm.code}
                onChange={(e) => setBuForm({ ...buForm, code: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
              />
              <input
                type="text"
                placeholder="Name (e.g. Digital Transformation)"
                required
                value={buForm.name}
                onChange={(e) => setBuForm({ ...buForm, name: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
              />
              <textarea
                placeholder="Description"
                value={buForm.description}
                onChange={(e) => setBuForm({ ...buForm, description: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setBuModal(false)} className="px-4 py-2 text-xs text-gray-400">
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-xs bg-purple-600 text-white rounded-xl font-medium">
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {ccModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-md rounded-2xl border border-gray-800 p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Create Cost Center</h3>
            <form onSubmit={handleCreateCC} className="space-y-3">
              <input
                type="text"
                placeholder="Code (e.g. CC-ENG-101)"
                required
                value={ccForm.code}
                onChange={(e) => setCcForm({ ...ccForm, code: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <input
                type="text"
                placeholder="Name (e.g. R&D Infrastructure)"
                required
                value={ccForm.name}
                onChange={(e) => setCcForm({ ...ccForm, name: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <input
                type="number"
                placeholder="Annual Budget"
                value={ccForm.annual_budget}
                onChange={(e) => setCcForm({ ...ccForm, annual_budget: parseFloat(e.target.value) || 0 })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setCcModal(false)} className="px-4 py-2 text-xs text-gray-400">
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
