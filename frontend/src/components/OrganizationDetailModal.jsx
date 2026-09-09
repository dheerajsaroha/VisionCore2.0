import React, { useState, useEffect } from 'react';
import { X, Building2, ShieldCheck, Users, Calendar, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { orgService } from '../services/orgService';
import { Badge } from './ui/Badge';

export function OrganizationDetailModal({ isOpen, onClose }) {
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoading(true);
    setError('');

    orgService.getCurrentOrganization()
      .then((res) => {
        if (!isMounted) return;
        setOrg(res.data || res);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.response?.data?.detail || 'Failed to load organization details.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-950/50">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-indigo-400" />
            <h3 className="text-lg font-semibold text-white">Organization Details</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto hide-scrollbar">
          {loading && (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && org && (
            <>
              <div className="flex items-center gap-4 p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                <div className="h-12 w-12 rounded-xl bg-indigo-600 flex items-center justify-center text-white text-xl font-bold">
                  {org.name ? org.name[0].toUpperCase() : 'O'}
                </div>
                <div>
                  <h4 className="text-lg font-bold text-white">{org.name}</h4>
                  <p className="text-sm text-gray-400 font-mono">Tenant ID: {org.id}</p>
                  <Badge variant="primary" className="mt-1">
                    {org.subscription_tier || 'Enterprise Plan'}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Domain</span>
                  <span className="font-semibold text-gray-200">{org.domain || 'internal.local'}</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">ZKP Threshold</span>
                  <span className="font-semibold text-indigo-400 font-mono">{org.zkp_threshold ?? 0.98}</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Status</span>
                  <span className="font-semibold text-emerald-400">Active Tenant</span>
                </div>
                <div className="p-3 rounded-xl bg-gray-800/20 border border-gray-800">
                  <span className="text-xs text-gray-500 block uppercase font-medium">Created</span>
                  <span className="font-semibold text-gray-200">
                    {org.created_at ? new Date(org.created_at).toLocaleDateString() : 'N/A'}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 bg-gray-950/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-xl bg-gray-800 text-gray-200 hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
