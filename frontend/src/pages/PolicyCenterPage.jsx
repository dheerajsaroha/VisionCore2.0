import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  FileText, Shield, CheckCircle2, AlertTriangle, Search,
  RefreshCw, Plus, BookOpen, Download, BarChart3,
  Layers, Eye, MessageSquare,
  PenSquare, TrendingUp, Percent, AlertCircle
} from 'lucide-react';
import { policyService } from '../services/policyService';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import '../components/ui/Spinner';
import { formatDate } from '../lib/utils';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'library', label: 'Policy Library', icon: BookOpen },
  { id: 'editor', label: 'Policy Editor', icon: PenSquare },
  { id: 'compliance', label: 'Compliance Center', icon: Shield },
  { id: 'signatures', label: 'Signatures', icon: CheckCircle2 },
  { id: 'reports', label: 'Reports', icon: TrendingUp },
];

export default function PolicyCenterPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [analytics, setAnalytics] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [complianceSummary, setComplianceSummary] = useState(null);
  const [complianceBreaches, setComplianceBreaches] = useState([]);
  const [pendingAcks, setPendingAcks] = useState([]);
const [signatures] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { user } = useAuthStore();
  const isAdmin = ['Admin', 'SuperAdmin', 'OrgAdmin', 'HR', 'Manager'].includes(user?.role?.name || '');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [analyticsRes, docsRes, catRes, compSumRes, breachesRes, pendingAckRes, notifRes, templateRes] = await Promise.all([
        policyService.getAnalytics().catch(() => ({ data: null })),
        policyService.searchDocuments({ limit: 100 }).catch(() => ({ data: [] })),
        policyService.getCategories().catch(() => ({ data: [] })),
        policyService.getComplianceSummary().catch(() => ({ data: null })),
        policyService.getComplianceBreaches().catch(() => ({ data: [] })),
        policyService.getPendingAcknowledgements().catch(() => ({ data: [] })),
        policyService.getNotifications().catch(() => ({ data: [] })),
        policyService.getTemplates().catch(() => ({ data: [] })),
      ]);

      setAnalytics(analyticsRes.data || analyticsRes);
      const docs = Array.isArray(docsRes) ? docsRes : (docsRes.data || docsRes?.items || []);
      setDocuments(docs);
      const cats = Array.isArray(catRes) ? catRes : (catRes.data || []);
      setCategories(cats);
      setComplianceSummary(compSumRes.data || compSumRes);
      const breaches = Array.isArray(breachesRes) ? breachesRes : (breachesRes.data || []);
      setComplianceBreaches(breaches);
      const acks = Array.isArray(pendingAckRes) ? pendingAckRes : (pendingAckRes.data || []);
      setPendingAcks(acks);
      const notifs = Array.isArray(notifRes) ? notifRes : (notifRes.data || []);
      setNotifications(notifs);
      const tpl = Array.isArray(templateRes) ? templateRes : (templateRes.data || []);
      setTemplates(tpl);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load Policy Center data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await policyService.searchDocuments({ search: searchQuery, limit: 50 });
      const docs = Array.isArray(res) ? res : (res.data || res?.items || []);
      setDocuments(docs);
    } catch {
      setErrorMsg('Search failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (docId, status) => {
    try {
      await policyService.acknowledgePolicy(docId, { status });
      setActionSuccess(`Policy ${status === 'accepted' ? 'acknowledged' : 'rejected'} successfully.`);
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to acknowledge policy.');
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="space-y-8 p-1 sm:p-2">
      {/* ── HEADER BANNER ── */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-950 via-slate-900 to-teal-950 p-8 text-white shadow-2xl border border-indigo-500/20">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-3.5 rounded-2xl bg-indigo-500/20 border border-indigo-400/30 backdrop-blur-md">
              <Shield className="h-8 w-8 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-white via-indigo-100 to-indigo-300 bg-clip-text text-transparent">
                Policy Center
              </h1>
              <p className="text-sm text-indigo-200/80 mt-0.5">
                Sprint 4 · Enterprise Policy &amp; Compliance Management
              </p>
            </div>
          </div>
          <Button onClick={fetchData} variant="secondary" className="bg-white/10 hover:bg-white/20 text-white border-white/10">
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-8 flex items-center gap-1 border-b border-indigo-500/20 pb-0 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 font-semibold text-sm transition-all border-b-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-indigo-400 text-indigo-300 bg-white/5 rounded-t-xl'
                    : 'border-transparent text-indigo-200/60 hover:text-white hover:bg-white/5 rounded-t-xl'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Notifications */}
      {actionSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{actionSuccess}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">{errorMsg}</span>
        </div>
      )}

      {/* ── TAB 1: EXECUTIVE DASHBOARD ── */}
      {activeTab === 'dashboard' && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Active Policies</p>
                <FileText className="h-5 w-5 text-indigo-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{analytics?.active_policies ?? documents.filter(d => d.status === 'published').length}</p>
              <p className="text-xs text-slate-500 mt-1">Currently in effect</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Pending Acknowledgements</p>
                <MessageSquare className="h-5 w-5 text-amber-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{pendingAcks.length}</p>
              <p className="text-xs text-slate-500 mt-1">Awaiting employee response</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Compliance %</p>
                <Percent className="h-5 w-5 text-emerald-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{complianceSummary?.overall_compliance_pct ?? 0}%</p>
              <p className="text-xs text-slate-500 mt-1">Org-wide compliance score</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Active Violations</p>
                <AlertTriangle className="h-5 w-5 text-rose-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{complianceBreaches.length}</p>
              <p className="text-xs text-slate-500 mt-1">Requires attention</p>
            </Card>
          </div>

          {/* Pending Acknowledgements */}
          <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-2xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-amber-400" /> Pending Acknowledgements
              </CardTitle>
              <CardDescription className="text-slate-400">Policies awaiting your review</CardDescription>
            </CardHeader>
            <CardContent className="p-0 pt-4">
              {pendingAcks.length === 0 ? (
                <p className="text-slate-400 py-6 text-center text-sm">No pending acknowledgements.</p>
              ) : (
                <div className="divide-y divide-slate-800">
                  {pendingAcks.map((p, i) => (
                    <div key={i} className="py-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold text-white">{p.policy_title || `Policy #${p.policy_id}`}</p>
                        <p className="text-xs text-slate-400">Due: {p.due_date ? formatDate(p.due_date) : 'Urgent'}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleAcknowledge(p.policy_id, 'accepted')}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1 rounded-lg">
                          Accept
                        </Button>
                        <Button size="sm" onClick={() => handleAcknowledge(p.policy_id, 'rejected')}
                          className="bg-rose-600 hover:bg-rose-500 text-white text-xs px-3 py-1 rounded-lg">
                          Reject
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 2: POLICY LIBRARY ── */}
      {activeTab === 'library' && (
        <div className="space-y-6">
          {/* Search & Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search policies by title, tags, or content..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
            </div>
            {isAdmin && (
              <Button onClick={() => setActiveTab('editor')} className="bg-indigo-600 hover:bg-indigo-500 text-white">
                <Plus className="h-4 w-4 mr-2" /> New Policy
              </Button>
            )}
          </div>

          {/* Policy Cards */}
          <Card className="border border-slate-800 bg-slate-900/90 shadow-xl">
            <CardContent className="p-0">
              {documents.length === 0 ? (
                <p className="text-slate-400 py-12 text-center text-sm">No policies published yet.</p>
              ) : (
                <div className="divide-y divide-slate-800">
                  {documents.map((doc) => (
                    <div key={doc.id} className="p-5 hover:bg-slate-800/40 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-bold text-white text-sm truncate">{doc.title || doc.name}</h3>
                            <Badge className={`text-xs ${
                              doc.status === 'published' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                              doc.status === 'draft' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                              'bg-slate-500/20 text-slate-300 border-slate-500/30'
                            }`}>{doc.status || 'draft'}</Badge>
                          </div>
                          <p className="text-xs text-slate-400 line-clamp-1">{doc.description || doc.content?.substring(0, 120) || 'No description'}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                            {doc.version && <span>v{doc.version}</span>}
                            {doc.category_name && <span>{doc.category_name}</span>}
                            {doc.effective_date && <span>Effective: {formatDate(doc.effective_date)}</span>}
                            {doc.published_at && <span>Published: {formatDate(doc.published_at)}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          {isAdmin && doc.status === 'draft' && (
                            <Button size="sm" className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded-lg"
                              onClick={() => policyService.publishDocument(doc.id).then(fetchData).catch(e => setErrorMsg(e.message))}>
                              Publish
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" className="text-slate-400 hover:text-white">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 3: POLICY EDITOR ── */}
      {activeTab === 'editor' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
              <PenSquare className="h-5 w-5 text-indigo-400" /> Policy Editor
            </CardTitle>
            <CardDescription className="text-slate-400">Use admin panel to create and manage policies</CardDescription>
          </CardHeader>
          <CardContent className="p-0 pt-6 text-center py-12">
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 inline-block">
              <p className="text-slate-400 text-sm">
                Full rich-text policy editor is available in the backend API.
                <br />Use <code className="text-indigo-400">POST /api/v1/policy/documents</code> to create policies programmatically.
              </p>
            </div>
            {categories.length > 0 && (
              <div className="mt-8 text-left">
                <h4 className="text-sm font-bold text-white mb-3">Available Categories</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.map((cat) => (
                    <div key={cat.id} className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                      <span className="font-bold text-white text-sm">{cat.name}</span>
                      <p className="text-xs text-slate-400 mt-0.5">{cat.description || ''}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {templates.length > 0 && (
              <div className="mt-8 text-left">
                <h4 className="text-sm font-bold text-white mb-3">Available Templates</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {templates.map((tpl) => (
                    <div key={tpl.id} className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60">
                      <span className="font-bold text-white text-sm">{tpl.name}</span>
                      <p className="text-xs text-slate-400 mt-0.5">{tpl.description || ''}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── TAB 4: COMPLIANCE CENTER ── */}
      {activeTab === 'compliance' && (
        <div className="space-y-6">
          {complianceSummary && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
                <p className="text-xs font-bold text-slate-400 uppercase">Org Compliance</p>
                <p className="text-3xl font-black text-white mt-2">{complianceSummary.overall_compliance_pct || 0}%</p>
              </Card>
              <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
                <p className="text-xs font-bold text-slate-400 uppercase">Department Avg</p>
                <p className="text-3xl font-black text-white mt-2">{complianceSummary.dept_avg_compliance || 0}%</p>
              </Card>
              <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
                <p className="text-xs font-bold text-slate-400 uppercase">Total Violations</p>
                <p className="text-3xl font-black text-white mt-2">{complianceBreaches.length}</p>
              </Card>
              <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
                <p className="text-xs font-bold text-slate-400 uppercase">Critical Breaches</p>
                <p className="text-3xl font-black text-white mt-2">{complianceBreaches.filter(b => b.severity === 'critical' || b.severity === 'high').length}</p>
              </Card>
            </div>
          )}

          <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-rose-400" /> Active Breaches & Violations
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4">
              {complianceBreaches.length === 0 ? (
                <p className="text-slate-400 py-6 text-center text-sm">No active compliance violations.</p>
              ) : (
                <div className="divide-y divide-slate-800">
                  {complianceBreaches.slice(0, 10).map((b, i) => (
                    <div key={i} className="py-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold text-white">{b.rule_name || b.rule_title || `Rule #${b.compliance_rule_id}`}</p>
                        <p className="text-xs text-slate-400">{b.description || b.violation_details || ''}</p>
                      </div>
                      <Badge className={`text-xs ${
                        b.severity === 'critical' ? 'bg-rose-500/20 text-rose-300 border-rose-500/30' :
                        b.severity === 'high' ? 'bg-orange-500/20 text-orange-300 border-orange-500/30' :
                        'bg-amber-500/20 text-amber-300 border-amber-500/30'
                      }`}>{b.severity || 'medium'}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 5: SIGNATURES ── */}
      {activeTab === 'signatures' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-400" /> Digital Signature Center
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            {signatures.length === 0 ? (
              <p className="text-slate-400 py-6 text-center text-sm">No signed documents yet. Signatures are recorded upon policy acknowledgement.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {signatures.map((sig, i) => (
                  <div key={i} className="py-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-bold text-white">{sig.document_title || `Policy #${sig.policy_id}`}</p>
                      <p className="text-xs text-slate-400">Signed: {formatDate(sig.created_at)}</p>
                    </div>
                    <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">Verified</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── TAB 6: REPORTS ── */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-emerald-400" /> Policy Center Reports
              </CardTitle>
              <CardDescription className="text-slate-400">Export and analyze policy data</CardDescription>
            </CardHeader>
            <CardContent className="p-0 pt-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 hover:bg-slate-700/50 cursor-pointer transition-colors">
                  <div className="flex items-center gap-3 mb-2">
                    <FileText className="h-5 w-5 text-indigo-400" />
                    <h3 className="font-bold text-white text-sm">Compliance Report</h3>
                  </div>
                  <p className="text-xs text-slate-400">Organization-wide compliance status & trends</p>
                  <Button size="sm" className="mt-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded-lg">
                    <Download className="h-3 w-3 mr-1" /> Export
                  </Button>
                </div>
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 hover:bg-slate-700/50 cursor-pointer transition-colors">
                  <div className="flex items-center gap-3 mb-2">
                    <Layers className="h-5 w-5 text-amber-400" />
                    <h3 className="font-bold text-white text-sm">Distribution Report</h3>
                  </div>
                  <p className="text-xs text-slate-400">Policy distribution by department & group</p>
                  <Button size="sm" className="mt-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded-lg">
                    <Download className="h-3 w-3 mr-1" /> Export
                  </Button>
                </div>
                <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 hover:bg-slate-700/50 cursor-pointer transition-colors">
                  <div className="flex items-center gap-3 mb-2">
                    <MessageSquare className="h-5 w-5 text-purple-400" />
                    <h3 className="font-bold text-white text-sm">Acknowledgement Report</h3>
                  </div>
                  <p className="text-xs text-slate-400">Employee acknowledgement status by policy</p>
                  <Button size="sm" className="mt-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded-lg">
                    <Download className="h-3 w-3 mr-1" /> Export
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-indigo-400" /> Recent Notifications
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4">
              {notifications.length === 0 ? (
                <p className="text-slate-400 py-6 text-center text-sm">No notifications yet.</p>
              ) : (
                <div className="divide-y divide-slate-800">
                  {notifications.slice(0, 5).map((n, i) => (
                    <div key={i} className="py-3 flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${n.is_read ? 'bg-slate-600' : 'bg-indigo-400'}`} />
                      <div>
                        <p className="text-sm text-white">{n.message || n.title}</p>
                        <p className="text-xs text-slate-500">{formatDate(n.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </motion.div>
  );
}
