/**
 * ApprovalWorkflowPage.jsx — Enterprise Approval Workflow Center
 * Sprint 2 — Entity 4
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  GitPullRequest, CheckCircle2, XCircle, RotateCcw, Clock,
  Zap, UserCheck, Layers, BarChart3, RefreshCw
} from 'lucide-react';
import workflowService from '../services/workflowService';

export default function ApprovalWorkflowPage() {
  const [activeTab, setActiveTab] = useState('pending');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  // State
  const [pendingQueue, setPendingQueue] = useState([]);
  const [myRequests, setMyRequests] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [delegations, setDelegations] = useState([]);
  const [analytics, setAnalytics] = useState(null);

  // Selected action modal state
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [actionComments, setActionComments] = useState('');
  const [actionType, setActionType] = useState('approve');

  const loadData = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      if (activeTab === 'pending') {
        const res = await workflowService.getPendingQueue();
        setPendingQueue(res.requests || []);
      } else if (activeTab === 'my-requests') {
        const res = await workflowService.getMyRequests();
        setMyRequests(res.requests || []);
      } else if (activeTab === 'designer') {
        const wfRes = await workflowService.getWorkflows();
        setWorkflows(wfRes.workflows || []);
      } else if (activeTab === 'delegations') {
        const res = await workflowService.getDelegations();
        setDelegations(res || []);
      } else if (activeTab === 'analytics') {
        const res = await workflowService.getAnalytics();
        setAnalytics(res);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to load workflow data' });
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExecuteAction = async () => {
    if (!selectedRequest) return;
    try {
      await workflowService.executeAction(selectedRequest.id, {
        action: actionType,
        comments: actionComments
      });
      setMessage({ type: 'success', text: `Successfully processed action '${actionType}'` });
      setSelectedRequest(null);
      setActionComments('');
      loadData();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to process action' });
    }
  };

  const handleSeedWorkflows = async () => {
    try {
      await workflowService.seedWorkflows();
      setMessage({ type: 'success', text: 'Workflows & blueprint templates seeded successfully!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Seeding failed' });
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 text-slate-100">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/80 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-600/20 text-blue-400 rounded-xl border border-blue-500/30">
              <GitPullRequest className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Enterprise Approval Workflow Center</h1>
              <p className="text-slate-400 text-sm">Centralized multi-stage approval engine across all HR modules</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSeedWorkflows}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-xl border border-slate-700 transition"
          >
            <Zap className="w-4 h-4 text-amber-400" /> Seed Workflows
          </button>
          <button
            onClick={loadData}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-xl transition shadow-lg shadow-blue-600/20"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {/* Alert Message */}
      {message && (
        <div className={`p-4 rounded-xl border flex items-center justify-between ${
          message.type === 'error' ? 'bg-red-950/50 border-red-800/50 text-red-200' : 'bg-emerald-950/50 border-emerald-800/50 text-emerald-200'
        }`}>
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="text-xs opacity-70 hover:opacity-100">Dismiss</button>
        </div>
      )}

      {/* Tabs Bar */}
      <div className="flex border-b border-slate-800 gap-2 overflow-x-auto pb-1">
        {[
          { id: 'pending', label: 'Pending Approvals Queue', icon: Clock },
          { id: 'my-requests', label: 'My Requests Tracker', icon: CheckCircle2 },
          { id: 'designer', label: 'Workflow Designer', icon: Layers },
          { id: 'delegations', label: 'Delegations & SLA', icon: UserCheck },
          { id: 'analytics', label: 'Analytics & Audit', icon: BarChart3 }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 font-medium text-sm rounded-t-xl transition whitespace-nowrap ${
                isActive
                  ? 'bg-slate-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: PENDING APPROVALS QUEUE */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Requests Requiring Your Decision</h2>
          {pendingQueue.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/40 rounded-2xl border border-slate-800">
              <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3 opacity-60" />
              <h3 className="text-lg font-medium text-white">All Clear!</h3>
              <p className="text-slate-400 text-sm mt-1">You have no pending approval requests in your queue.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {pendingQueue.map((req) => (
                <div key={req.id} className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800 space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="inline-block px-2.5 py-1 text-xs font-semibold uppercase bg-blue-500/10 text-blue-400 rounded-md border border-blue-500/20 mb-2">
                        {req.entity_type}
                      </span>
                      <h3 className="text-base font-semibold text-white">{req.title || `Request #${req.id}`}</h3>
                      <p className="text-xs text-slate-400">Entity ID: {req.entity_id} • Priority: <span className="text-amber-400 capitalize">{req.priority}</span></p>
                    </div>
                    <span className="px-3 py-1 text-xs font-medium bg-amber-500/10 text-amber-400 rounded-full border border-amber-500/20">
                      Stage {req.current_stage_order}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto">
                    {JSON.stringify(req.request_payload, null, 2)}
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-slate-500">Submitted: {new Date(req.submitted_at).toLocaleString()}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => { setSelectedRequest(req); setActionType('reject'); }}
                        className="px-3 py-1.5 bg-red-950/80 hover:bg-red-900 text-red-300 text-xs font-medium rounded-lg border border-red-800/50 flex items-center gap-1"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Reject
                      </button>
                      <button
                        onClick={() => { setSelectedRequest(req); setActionType('return'); }}
                        className="px-3 py-1.5 bg-amber-950/80 hover:bg-amber-900 text-amber-300 text-xs font-medium rounded-lg border border-amber-800/50 flex items-center gap-1"
                      >
                        <RotateCcw className="w-3.5 h-3.5" /> Return
                      </button>
                      <button
                        onClick={() => { setSelectedRequest(req); setActionType('approve'); }}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg flex items-center gap-1 shadow-md shadow-emerald-600/20"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MY REQUESTS TRACKER */}
      {activeTab === 'my-requests' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Your Submitted Requests</h2>
          <div className="bg-slate-900/90 rounded-2xl border border-slate-800 overflow-hidden">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/80 text-xs uppercase text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-4">ID</th>
                  <th className="p-4">Module</th>
                  <th className="p-4">Entity ID</th>
                  <th className="p-4">Current Stage</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Submitted At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {myRequests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-800/30 transition">
                    <td className="p-4 font-mono font-medium text-white">#{req.id}</td>
                    <td className="p-4 uppercase font-semibold text-blue-400">{req.entity_type}</td>
                    <td className="p-4 font-mono">{req.entity_id}</td>
                    <td className="p-4">Stage {req.current_stage_order}</td>
                    <td className="p-4">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${
                        req.status === 'approved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                        req.status === 'rejected' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                        req.status === 'returned' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                        'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      }`}>
                        {req.status}
                      </span>
                    </td>
                    <td className="p-4 text-xs text-slate-400">{new Date(req.submitted_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: WORKFLOW DESIGNER */}
      {activeTab === 'designer' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-white">Configured Approval Workflows</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workflows.map((wf) => (
              <div key={wf.id} className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800 space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="px-2.5 py-1 text-xs font-mono bg-blue-500/10 text-blue-400 rounded-md border border-blue-500/20">
                      {wf.code}
                    </span>
                    <h3 className="text-base font-semibold text-white mt-1">{wf.name}</h3>
                    <p className="text-xs text-slate-400 mt-1">{wf.description}</p>
                  </div>
                  <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20 uppercase">
                    {wf.entity_type}
                  </span>
                </div>

                <div className="space-y-2 pt-2">
                  <span className="text-xs font-semibold text-slate-400 uppercase">Workflow Stages ({wf.stages?.length || 0})</span>
                  {wf.stages?.map((stg) => (
                    <div key={stg.id} className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-semibold text-white">Stage {stg.stage_order}: {stg.name}</span>
                        <p className="text-slate-400 mt-0.5">Type: <span className="text-blue-400 capitalize">{stg.approval_type}</span> • SLA: {stg.sla_hours || 'N/A'} hrs</p>
                      </div>
                      <span className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded font-mono">
                        {stg.approvers?.length || 0} Approver(s)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: DELEGATIONS & SLA */}
      {activeTab === 'delegations' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Active Authority Delegations</h2>
          <div className="bg-slate-900/90 rounded-2xl border border-slate-800 overflow-hidden">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/80 text-xs uppercase text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-4">Delegator User</th>
                  <th className="p-4">Delegatee User</th>
                  <th className="p-4">Entity Type</th>
                  <th className="p-4">Start Date</th>
                  <th className="p-4">End Date</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {delegations.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-800/30 transition">
                    <td className="p-4 font-semibold text-white">User #{d.delegator_user_id}</td>
                    <td className="p-4 font-semibold text-blue-400">User #{d.delegatee_user_id}</td>
                    <td className="p-4 font-mono">{d.entity_type || 'All Entities'}</td>
                    <td className="p-4 text-xs text-slate-400">{new Date(d.start_date).toLocaleDateString()}</td>
                    <td className="p-4 text-xs text-slate-400">{new Date(d.end_date).toLocaleDateString()}</td>
                    <td className="p-4">
                      <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: ANALYTICS */}
      {activeTab === 'analytics' && analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800">
            <p className="text-xs uppercase text-slate-400 font-semibold">Total Requests</p>
            <h3 className="text-3xl font-bold text-white mt-1">{analytics.total_requests}</h3>
          </div>
          <div className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800">
            <p className="text-xs uppercase text-slate-400 font-semibold">Pending Approval</p>
            <h3 className="text-3xl font-bold text-amber-400 mt-1">{analytics.pending_requests}</h3>
          </div>
          <div className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800">
            <p className="text-xs uppercase text-slate-400 font-semibold">Approved</p>
            <h3 className="text-3xl font-bold text-emerald-400 mt-1">{analytics.approved_requests}</h3>
          </div>
          <div className="p-5 bg-slate-900/90 rounded-2xl border border-slate-800">
            <p className="text-xs uppercase text-slate-400 font-semibold">SLA Compliance</p>
            <h3 className="text-3xl font-bold text-blue-400 mt-1">{analytics.sla_compliance_rate}%</h3>
          </div>
        </div>
      )}

      {/* ACTION MODAL */}
      {selectedRequest && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 rounded-2xl border border-slate-800 max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white capitalize">Execute Action: {actionType}</h3>
            <p className="text-xs text-slate-400">Request #{selectedRequest.id} • {selectedRequest.title}</p>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase mb-1">Decision Comments / Remarks</label>
              <textarea
                value={actionComments}
                onChange={(e) => setActionComments(e.target.value)}
                placeholder="Enter justification or instructions..."
                className="w-full h-24 p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedRequest(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteAction}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-xl shadow-lg shadow-blue-600/20"
              >
                Submit Action
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
