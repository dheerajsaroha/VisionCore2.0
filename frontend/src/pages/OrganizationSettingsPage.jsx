import React, { useState, useEffect } from 'react';
import {
  Settings,
  Palette,
  ShieldAlert,
  RefreshCw
} from 'lucide-react';
import api from '../services/apiClient';

export default function OrganizationSettingsPage() {
  const [hierarchy, setHierarchy] = useState(null);
  const [primaryColor, setPrimaryColor] = useState('#4F46E5');

  const fetchSettings = async () => {
    try {
      const res = await api.get('/organizations/hierarchy');
      setHierarchy(res.data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Fetch organization settings after mount.
    fetchSettings();
  }, []);

  const handleStateTransition = async (newState) => {
    if (!confirm(`Are you sure you want to transition organization state to ${newState}?`)) return;
    try {
      await api.post('/organizations/state-transition', { new_state: newState });
      fetchSettings();
    } catch (err) {
      alert(err.response?.data?.detail || 'State transition failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Settings className="h-7 w-7 text-indigo-400" />
            Organization & Workspace Settings
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Enterprise organization branding, workspace customization, and lifecycle state management.
          </p>
        </div>
        <button
          onClick={fetchSettings}
          className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white transition self-start sm:self-auto"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Branding & Theme */}
        <div className="glass p-6 rounded-2xl border border-gray-800 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Palette className="h-5 w-5 text-indigo-400" />
            Tenant Branding & Customization
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Primary Theme Color</label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="h-10 w-16 bg-transparent border-none cursor-pointer rounded-lg"
                />
                <span className="text-sm font-mono text-gray-300">{primaryColor}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Organization Display Name</label>
              <input
                type="text"
                disabled
                value={hierarchy?.name || 'Loading...'}
                className="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-sm text-gray-400 cursor-not-allowed"
              />
            </div>
          </div>
        </div>

        {/* Lifecycle State Controls */}
        <div className="glass p-6 rounded-2xl border border-gray-800 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-400" />
            Lifecycle State Management
          </h2>

          <div className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Current Lifecycle State:</span>
              <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {hierarchy?.status || 'ACTIVE'}
              </span>
            </div>

            <div className="pt-3 border-t border-gray-800 flex flex-wrap gap-2">
              <button
                onClick={() => handleStateTransition('SUSPENDED')}
                className="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-xs font-medium"
              >
                Suspend Organization
              </button>
              <button
                onClick={() => handleStateTransition('ARCHIVED')}
                className="px-3 py-1.5 rounded-lg bg-gray-800 text-gray-400 hover:bg-gray-700 text-xs font-medium"
              >
                Archive Organization
              </button>
              <button
                onClick={() => handleStateTransition('ACTIVE')}
                className="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-medium"
              >
                Re-Activate Organization
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
