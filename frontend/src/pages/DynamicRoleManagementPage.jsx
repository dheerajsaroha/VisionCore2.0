import React, { useState, useEffect } from 'react';
import {
  ShieldCheck, Copy, GitMerge, History, UserCheck, Layout, Plus,
  RefreshCw, CheckCircle, AlertTriangle
} from 'lucide-react';
import dynamicRoleService from '../services/dynamicRoleService';

export default function DynamicRoleManagementPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [roles, setRoles] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [effectiveAuth, setEffectiveAuth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  // Form states
  const [newRole, setNewRole] = useState({ code: '', name: '', description: '', permissions: '' });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rData, tData, effData] = await Promise.all([
        dynamicRoleService.getRoles(),
        dynamicRoleService.getTemplates(),
        dynamicRoleService.getEffectiveAuthorization()
      ]);
      setRoles(rData.roles || []);
      setTemplates(tData || []);
      setEffectiveAuth(effData);
    } catch {
      setMsg({ type: 'error', text: 'Failed to load dynamic roles infrastructure.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSeed = async () => {
    try {
      await dynamicRoleService.seedTemplates();
      setMsg({ type: 'success', text: 'Seeded default enterprise role templates.' });
      loadData();
    } catch {
      setMsg({ type: 'error', text: 'Failed to seed templates.' });
    }
  };

  const handleCreateFromTemplate = async (code, name) => {
    try {
      await dynamicRoleService.createRoleFromTemplate(code, `${name} Custom`);
      setMsg({ type: 'success', text: `Created dynamic role from template '${code}'.` });
      loadData();
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Template creation failed.' });
    }
  };

  const handleCreateRole = async (e) => {
    e.preventDefault();
    try {
      const perms = newRole.permissions.split(',').map(s => s.trim()).filter(Boolean);
      await dynamicRoleService.createRole({
        code: newRole.code,
        name: newRole.name,
        description: newRole.description,
        permissions_json: perms
      });
      setMsg({ type: 'success', text: `Dynamic role '${newRole.name}' created successfully.` });
      setNewRole({ code: '', name: '', description: '', permissions: '' });
      loadData();
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to create role.' });
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-slate-900 text-white p-6 rounded-2xl shadow-xl">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-indigo-600 rounded-xl">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Dynamic Role Management Center</h1>
            <p className="text-slate-400 text-sm">Sprint 2 — Entity 5 • EAAC Dynamic Role & Template Hierarchy Engine</p>
          </div>
        </div>
        <button
          onClick={loadData}
          className="flex items-center px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {msg.text && (
        <div className={`p-4 rounded-xl flex items-center ${msg.type === 'error' ? 'bg-red-900/40 text-red-200 border border-red-700' : 'bg-emerald-900/40 text-emerald-200 border border-emerald-700'}`}>
          {msg.type === 'error' ? <AlertTriangle className="w-5 h-5 mr-3" /> : <CheckCircle className="w-5 h-5 mr-3" />}
          {msg.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-700 pb-2">
        {[
          { id: 'dashboard', label: 'Role Dashboard', icon: Layout },
          { id: 'templates', label: 'Template Library', icon: Copy },
          { id: 'designer', label: 'Role Designer', icon: Plus },
          { id: 'inheritance', label: 'Inheritance Visualizer', icon: GitMerge },
          { id: 'versions', label: 'Version History', icon: History },
          { id: 'assignments', label: 'User Assignments', icon: UserCheck }
        ].map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center px-4 py-2.5 rounded-lg font-medium text-sm transition ${activeTab === t.id ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30' : 'text-slate-400 hover:bg-slate-800'}`}
            >
              <Icon className="w-4 h-4 mr-2" /> {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Contents */}
      {activeTab === 'dashboard' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl col-span-2">
            <h2 className="text-lg font-bold text-white mb-4">Active Dynamic Roles ({roles.length})</h2>
            <div className="space-y-3">
              {roles.map(r => (
                <div key={r.id} className="p-4 bg-slate-800/60 border border-slate-700/50 rounded-xl flex justify-between items-center">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-indigo-400">{r.name}</span>
                      <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded-full font-mono">{r.code}</span>
                      <span className="text-xs px-2 py-0.5 bg-indigo-900/60 text-indigo-300 rounded font-mono">v{r.version}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{r.description || 'No description'}</p>
                    <div className="flex space-x-2 mt-2">
                      <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-1 rounded">Permissions: {r.permissions_json?.length || 0}</span>
                      <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-1 rounded">Approvals: {r.approval_rights_json?.length || 0}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-4">
            <h2 className="text-lg font-bold text-white">Effective Authorization</h2>
            {effectiveAuth && (
              <div className="space-y-3 text-xs">
                <div className="bg-slate-800 p-3 rounded-lg">
                  <span className="text-slate-400">Primary Role:</span>
                  <p className="font-mono text-indigo-300 text-sm">{effectiveAuth.primary_role_code || 'None'}</p>
                </div>
                <div className="bg-slate-800 p-3 rounded-lg">
                  <span className="text-slate-400">Effective Permissions ({effectiveAuth.effective_permissions?.length || 0}):</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {effectiveAuth.effective_permissions?.map(p => (
                      <span key={p} className="bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded font-mono text-[10px]">{p}</span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'templates' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-white">Built-in Blueprint Templates ({templates.length})</h2>
            <button onClick={handleSeed} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm">Seed Templates</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map(t => (
              <div key={t.id} className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-950 px-2 py-1 rounded">{t.category}</span>
                  <h3 className="text-base font-bold text-white mt-2">{t.name}</h3>
                  <p className="text-xs text-slate-400 mt-1">{t.description}</p>
                </div>
                <button
                  onClick={() => handleCreateFromTemplate(t.code, t.name)}
                  className="w-full py-2 bg-slate-800 hover:bg-indigo-600 text-white text-xs rounded-lg transition"
                >
                  Create Custom Role from Template
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'designer' && (
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl max-w-2xl">
          <h2 className="text-xl font-bold text-white mb-4">Create New Dynamic Role</h2>
          <form onSubmit={handleCreateRole} className="space-y-4">
            <div>
              <label className="text-xs text-slate-300 block mb-1">Role Code</label>
              <input
                type="text"
                placeholder="e.g. payroll_auditor_v1"
                value={newRole.code}
                onChange={e => setNewRole({ ...newRole, code: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white px-3 py-2 rounded-lg text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs text-slate-300 block mb-1">Role Name</label>
              <input
                type="text"
                placeholder="e.g. Payroll Auditor"
                value={newRole.name}
                onChange={e => setNewRole({ ...newRole, name: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white px-3 py-2 rounded-lg text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs text-slate-300 block mb-1">Description</label>
              <textarea
                placeholder="Role responsibility summary"
                value={newRole.description}
                onChange={e => setNewRole({ ...newRole, description: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white px-3 py-2 rounded-lg text-sm h-20"
              />
            </div>
            <div>
              <label className="text-xs text-slate-300 block mb-1">Permissions (comma separated)</label>
              <input
                type="text"
                placeholder="e.g. payroll.read, reimbursement.audit"
                value={newRole.permissions}
                onChange={e => setNewRole({ ...newRole, permissions: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white px-3 py-2 rounded-lg text-sm"
              />
            </div>
            <button type="submit" className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg text-sm transition">
              Create Dynamic Role
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
