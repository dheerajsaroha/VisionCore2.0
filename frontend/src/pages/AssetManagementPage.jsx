import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Package, Shield, Wrench, ClipboardCheck, BarChart3,
  RefreshCw, AlertCircle, ArrowUpRight,
  Search, Filter, Download, Upload,
  HardDrive, Key, Truck, Users
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { assetService } from '../services/assetService';

const TABS = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'inventory', label: 'Inventory', icon: Package },
  { id: 'assignments', label: 'Assignments', icon: Users },
  { id: 'maintenance', label: 'Maintenance', icon: Wrench },
  { id: 'licenses', label: 'Licenses', icon: Key },
  { id: 'audits', label: 'Audits', icon: ClipboardCheck },
  { id: 'vendors', label: 'Vendors', icon: Truck },
  { id: 'consumables', label: 'Consumables', icon: HardDrive },
];

const STATUS_BADGES = {
  available: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  assigned: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  under_maintenance: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  disposed: 'bg-slate-500/15 text-slate-400 border-slate-500/25',
  retired: 'bg-red-500/15 text-red-400 border-red-500/25',
};

export default function AssetManagementPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [metrics, setMetrics] = useState(null);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      switch (activeTab) {
        case 'overview':
          const analytics = await assetService.getAnalytics();
          setMetrics(analytics);
          break;
        case 'inventory':
          const assetList = await assetService.getAssets({ search: search || undefined });
          setAssets(assetList);
          break;
        default:
          break;
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [activeTab, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 p-1 sm:p-2"
    >
      {/* Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-emerald-950 p-8 text-white shadow-2xl border border-emerald-500/20">
        <div className="absolute -top-20 -right-20 w-96 h-96 rounded-full bg-emerald-600/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-10 -left-10 w-72 h-72 rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-500/30 to-teal-600/20 border border-emerald-400/30 backdrop-blur-md shadow-xl">
              <Package className="h-8 w-8 text-emerald-300" />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-white via-emerald-100 to-emerald-300 bg-clip-text text-transparent">
                  Asset & Device Management
                </h1>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 text-xs font-semibold text-emerald-400">
                  <Shield className="h-3 w-3" /> EAAC Protected
                </div>
              </div>
              <p className="text-sm text-emerald-200/70">
                Sprint 5 — Enterprise Asset & Device Management System
              </p>
            </div>
          </div>
          <Button
            onClick={fetchData}
            variant="secondary"
            className="bg-white/10 hover:bg-white/20 text-white border-white/10 backdrop-blur"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Tabs */}
        <div className="mt-6 flex flex-wrap gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-emerald-500/20 text-white border border-emerald-400/30 shadow-lg'
                    : 'text-emerald-200/60 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-3"
        >
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{error}</span>
        </motion.div>
      )}

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Spinner size="xl" className="text-emerald-500" />
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >
          {/* OVERVIEW TAB */}
          {activeTab === 'overview' && metrics && (
            <>
              {/* Executive Metrics */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div className="rounded-2xl bg-slate-900/90 border border-emerald-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Total Assets</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.total_assets || 0}</p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-blue-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Assigned</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.assigned_count || 0}</p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-emerald-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Available</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.available_count || 0}</p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-amber-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Under Maintenance</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.maintenance_count || 0}</p>
                </div>
              </div>

              {/* Secondary Metrics */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div className="rounded-2xl bg-slate-900/90 border border-slate-700 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Total Value</p>
                  <p className="text-2xl font-black text-emerald-400 mt-2">
                    ₹{new Intl.NumberFormat('en-IN').format(metrics.total_value || 0)}
                  </p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-orange-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Warranty Expiring</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.warranty_expiring_30_days || 0}</p>
                  <p className="text-xs text-slate-500 mt-1">Next 30 days</p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-purple-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Licenses Expiring</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.license_expiring_30_days || 0}</p>
                  <p className="text-xs text-slate-500 mt-1">Next 30 days</p>
                </div>
                <div className="rounded-2xl bg-slate-900/90 border border-cyan-500/20 p-5 shadow-xl">
                  <p className="text-xs font-bold text-slate-400 uppercase">Vendors</p>
                  <p className="text-3xl font-black text-white mt-2">{metrics.total_vendors || 0}</p>
                </div>
              </div>

              {/* Asset Distribution & Status Breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <Package className="h-5 w-5 text-emerald-400" />
                    Assets by Status
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(metrics.assets_by_status || {}).map(([status, count]) => (
                      <div key={status} className="flex items-center justify-between">
                        <span className="text-sm text-slate-300 capitalize">{status.replace('_', ' ')}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-32 h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full"
                              style={{ width: `${(count / Math.max(1, metrics.total_assets)) * 100}%` }}
                            />
                          </div>
                          <span className="text-sm font-bold text-white w-8 text-right">{count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-emerald-400" />
                    Purchase Orders & Consumables
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-slate-500">Total POs</p>
                      <p className="text-xl font-bold text-white">{metrics.total_purchase_orders || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Pending POs</p>
                      <p className="text-xl font-bold text-amber-400">{metrics.pending_po_count || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Consumables</p>
                      <p className="text-xl font-bold text-white">{metrics.total_consumables || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Low Stock</p>
                      <p className="text-xl font-bold text-rose-400">{metrics.low_stock_count || 0}</p>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* INVENTORY TAB */}
          {activeTab === 'inventory' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search assets by name, tag, serial number..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 text-sm"
                  />
                </div>
                <Button variant="secondary" className="bg-slate-800 border-slate-700 text-white hover:bg-slate-700">
                  <Filter className="h-4 w-4 mr-2" /> Filter
                </Button>
                <Button variant="secondary" className="bg-slate-800 border-slate-700 text-white hover:bg-slate-700">
                  <Upload className="h-4 w-4 mr-2" /> Import
                </Button>
                <Button variant="secondary" className="bg-slate-800 border-slate-700 text-white hover:bg-slate-700">
                  <Download className="h-4 w-4 mr-2" /> Export
                </Button>
              </div>

              {assets.length === 0 ? (
                <div className="text-center py-16 text-slate-500">
                  <Package className="h-12 w-12 mx-auto mb-4 opacity-30" />
                  <p className="text-lg font-semibold">No assets found</p>
                  <p className="text-sm">Create your first asset to get started</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {assets.map((asset) => (
                    <div
                      key={asset.id}
                      className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 shadow-xl hover:border-slate-600 transition-all cursor-pointer"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <p className="text-sm font-bold text-white">{asset.name}</p>
                          <p className="text-xs text-slate-500 font-mono mt-0.5">{asset.asset_tag}</p>
                        </div>
                        <Badge className={STATUS_BADGES[asset.status] || 'bg-slate-700 text-slate-300'}>
                          {asset.status?.replace('_', ' ')}
                        </Badge>
                      </div>
                      {asset.serial_no && (
                        <p className="text-xs text-slate-500 mb-2">S/N: {asset.serial_no}</p>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs text-slate-400">
                        {asset.category_name && (
                          <span className="px-2 py-1 bg-slate-800 rounded-lg">{asset.category_name}</span>
                        )}
                        {asset.assigned_to_name && (
                          <span className="px-2 py-1 bg-blue-500/10 text-blue-400 rounded-lg">
                            {asset.assigned_to_name}
                          </span>
                        )}
                      </div>
                      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                        <span>₹{new Intl.NumberFormat('en-IN').format(asset.purchase_cost || 0)}</span>
                        <div className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer">
                          <span>View</span>
                          <ArrowUpRight className="h-3 w-3" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Placeholder for other tabs */}
          {activeTab !== 'overview' && activeTab !== 'inventory' && (
            <div className="text-center py-24 text-slate-500">
              <div className={`p-4 rounded-2xl inline-flex mb-4 bg-gradient-to-br from-emerald-500/10 to-teal-600/10 border border-emerald-500/20`}>
                {activeTab === 'assignments' && <Users className="h-8 w-8 text-emerald-400" />}
                {activeTab === 'maintenance' && <Wrench className="h-8 w-8 text-emerald-400" />}
                {activeTab === 'licenses' && <Key className="h-8 w-8 text-emerald-400" />}
                {activeTab === 'audits' && <ClipboardCheck className="h-8 w-8 text-emerald-400" />}
                {activeTab === 'vendors' && <Truck className="h-8 w-8 text-emerald-400" />}
                {activeTab === 'consumables' && <HardDrive className="h-8 w-8 text-emerald-400" />}
              </div>
              <p className="text-lg font-semibold capitalize">{activeTab} Center</p>
              <p className="text-sm mt-1">Use the API endpoints to manage {activeTab}</p>
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

