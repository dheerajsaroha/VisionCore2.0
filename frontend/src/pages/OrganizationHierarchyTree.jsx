import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  Building2,
  ChevronRight,
  ChevronDown,
  Layers,
  Briefcase,
  RefreshCw,
  Shield
} from 'lucide-react';
import api from '../services/apiClient';

export default function OrganizationHierarchyTree() {
  const [tree, setTree] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({
    root: true,
    legal: true,
    bu: true,
    depts: true,
  });

  const fetchTree = async () => {
    try {
      setLoading(true);
      const res = await api.get('/organizations/hierarchy');
      setTree(res.data);
    } catch (err) {
      console.error('Failed to load hierarchy tree:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTree();
  }, []);

  const toggle = (key) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <GitBranch className="h-7 w-7 text-indigo-400" />
            Organization Hierarchy Tree
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Visual tree structure representing Legal Entities, Business Units, Departments, Teams, and Positions.
          </p>
        </div>
        <button
          onClick={fetchTree}
          className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 transition"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Tree Visualization Container */}
      <div className="glass p-6 rounded-2xl border border-gray-800 min-h-[500px]">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-gray-500">
            Loading organization tree...
          </div>
        ) : !tree ? (
          <div className="flex items-center justify-center h-64 text-gray-500">
            No hierarchy data found.
          </div>
        ) : (
          <div className="space-y-4">
            {/* Root Organization Node */}
            <div className="border border-indigo-500/30 bg-indigo-500/10 p-4 rounded-xl">
              <div
                onClick={() => toggle('root')}
                className="flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-base font-bold text-white">{tree.name}</p>
                    <p className="text-xs text-gray-400">Legal ID: {tree.legal_id} • Status: {tree.status}</p>
                  </div>
                </div>
                {expanded.root ? <ChevronDown className="h-5 w-5 text-gray-400" /> : <ChevronRight className="h-5 w-5 text-gray-400" />}
              </div>

              {expanded.root && (
                <div className="mt-4 pl-6 border-l-2 border-indigo-500/20 space-y-4">
                  {/* Legal Entities Level */}
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Legal Entities</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {tree.legal_entities?.map((le) => (
                        <div key={le.id} className="p-3 bg-gray-900/80 rounded-xl border border-gray-800 flex items-center gap-3">
                          <Shield className="h-5 w-5 text-indigo-400 shrink-0" />
                          <div>
                            <p className="text-sm font-semibold text-white">{le.name}</p>
                            <p className="text-xs text-gray-400">{le.legal_name} ({le.country})</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Business Units Level */}
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Business Units</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {tree.business_units?.map((bu) => (
                        <div key={bu.id} className="p-3 bg-gray-900/80 rounded-xl border border-gray-800 flex items-center gap-3">
                          <GitBranch className="h-5 w-5 text-purple-400 shrink-0" />
                          <div>
                            <p className="text-sm font-semibold text-white">{bu.name}</p>
                            <p className="text-xs text-gray-400">Code: {bu.code}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Departments Level */}
                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Departments & Teams</p>
                    <div className="space-y-3">
                      {tree.departments?.map((d) => (
                        <div key={d.id} className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Layers className="h-5 w-5 text-amber-400" />
                              <span className="text-sm font-bold text-white">{d.name}</span>
                            </div>
                            <span className="text-xs text-gray-400">
                              {d.teams?.length || 0} Teams • {d.positions?.length || 0} Positions
                            </span>
                          </div>

                          {/* Nested Positions & Teams */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pl-4 border-l border-gray-800">
                            {d.positions?.map((p) => (
                              <div key={p.id} className="p-2 bg-gray-950/80 rounded-lg text-xs flex items-center gap-2 text-gray-300">
                                <Briefcase className="h-3.5 w-3.5 text-indigo-400" />
                                <span>{p.title} ({p.code})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
