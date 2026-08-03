import React, { useState, useEffect } from 'react';
import {
  Building2,
  GitBranch,
  MapPin,
  Briefcase,
  Users,
  ShieldCheck,
  Zap,
  CheckCircle2,
  RefreshCw,
  Plus,
  Layers,
  DollarSign
} from 'lucide-react';
import api from '../services/apiClient';

export default function OrganizationDashboard() {
  const [hierarchy, setHierarchy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [provisionModal, setProvisionModal] = useState(false);
  const [provForm, setProvForm] = useState({
    org_name: '',
    legal_id: '',
    admin_email: '',
    admin_name: '',
    primary_color: '#4F46E5'
  });
  const [provStatus, setProvStatus] = useState(null);

  const fetchHierarchy = async () => {
    try {
      setLoading(true);
      const res = await api.get('/organizations/hierarchy');
      setHierarchy(res.data);
    } catch (err) {
      console.error('Failed to load hierarchy:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHierarchy();
  }, []);

  const handleProvision = async (e) => {
    e.preventDefault();
    try {
      const res = await api.post('/organizations/provision', provForm);
      setProvStatus(res.data);
      setProvisionModal(false);
      fetchHierarchy();
    } catch (err) {
      alert(err.response?.data?.detail || 'Provisioning failed');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Building2 className="h-7 w-7 text-indigo-400" />
            Organization & Identity Domain
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Enterprise multi-tenant hierarchy, workflow-driven provisioning, legal entities, and identity lifecycles.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchHierarchy}
            className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setProvisionModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-lg shadow-indigo-600/30 transition"
          >
            <Zap className="h-4 w-4" />
            Provision Workspace
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass p-5 rounded-2xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Organization Status</p>
            <p className="text-xl font-bold text-emerald-400 mt-1">
              {hierarchy?.status || 'ACTIVE'}
            </p>
          </div>
          <div className="h-11 w-11 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
            <CheckCircle2 className="h-6 w-6" />
          </div>
        </div>

        <div className="glass p-5 rounded-2xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Legal Entities</p>
            <p className="text-2xl font-bold text-white mt-1">
              {hierarchy?.legal_entities?.length || 1}
            </p>
          </div>
          <div className="h-11 w-11 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <ShieldCheck className="h-6 w-6" />
          </div>
        </div>

        <div className="glass p-5 rounded-2xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Business Units</p>
            <p className="text-2xl font-bold text-white mt-1">
              {hierarchy?.business_units?.length || 1}
            </p>
          </div>
          <div className="h-11 w-11 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center">
            <GitBranch className="h-6 w-6" />
          </div>
        </div>

        <div className="glass p-5 rounded-2xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Departments</p>
            <p className="text-2xl font-bold text-white mt-1">
              {hierarchy?.departments?.length || 4}
            </p>
          </div>
          <div className="h-11 w-11 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center">
            <Layers className="h-6 w-6" />
          </div>
        </div>
      </div>

      {/* Structural Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass p-6 rounded-2xl border border-gray-800 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Building2 className="h-5 w-5 text-indigo-400" />
            Legal Corporate Entities
          </h2>
          {hierarchy?.legal_entities?.length > 0 ? (
            <div className="space-y-3">
              {hierarchy.legal_entities.map((le) => (
                <div key={le.id} className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">{le.name}</p>
                    <p className="text-xs text-gray-400">{le.legal_name} • {le.country}</p>
                  </div>
                  <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    Active Entity
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No legal entities configured yet.</p>
          )}
        </div>

        <div className="glass p-6 rounded-2xl border border-gray-800 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-purple-400" />
            Strategic Business Units
          </h2>
          {hierarchy?.business_units?.length > 0 ? (
            <div className="space-y-3">
              {hierarchy.business_units.map((bu) => (
                <div key={bu.id} className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">{bu.name}</p>
                    <p className="text-xs text-gray-400">Code: {bu.code}</p>
                  </div>
                  <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                    Operating Unit
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No business units configured yet.</p>
          )}
        </div>
      </div>

      {/* Provisioning Modal */}
      {provisionModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-lg rounded-2xl border border-gray-800 p-6 space-y-5 animate-fade-in">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Zap className="h-5 w-5 text-indigo-400" />
              Provision New Workspace
            </h3>

            <form onSubmit={handleProvision} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Organization Name</label>
                <input
                  type="text"
                  required
                  value={provForm.org_name}
                  onChange={(e) => setProvForm({ ...provForm, org_name: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  placeholder="Acme Enterprise Corp"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">Registration / Tax ID</label>
                <input
                  type="text"
                  required
                  value={provForm.legal_id}
                  onChange={(e) => setProvForm({ ...provForm, legal_id: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  placeholder="REG-2026-9900"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Admin Email</label>
                  <input
                    type="email"
                    required
                    value={provForm.admin_email}
                    onChange={(e) => setProvForm({ ...provForm, admin_email: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                    placeholder="admin@acme.com"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Admin Full Name</label>
                  <input
                    type="text"
                    required
                    value={provForm.admin_name}
                    onChange={(e) => setProvForm({ ...provForm, admin_name: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                    placeholder="John Doe"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setProvisionModal(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30"
                >
                  Start Provisioning
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
