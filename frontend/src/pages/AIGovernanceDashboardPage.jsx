import React, { useState, useEffect } from 'react';
import aiService from '../services/aiService';
import { Card } from '../components/ui/Card';
import { Spinner } from '../components/ui/Spinner';
import { Badge } from '../components/ui/Badge';

const AIGovernanceDashboardPage = () => {
  const [dashboard, setDashboard] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [dashData, compData, auditData] = await Promise.all([
        aiService.getGovernanceDashboard(),
        aiService.getComplianceReport(),
        aiService.searchAuditTrail({ limit: 20 }),
      ]);
      setDashboard(dashData);
      setCompliance(compData);
      setAuditLog(auditData || []);
    } catch (err) { setError(err.message); }
    finally { setIsLoading(false); }
  };

  if (isLoading) return <div className="flex items-center justify-center h-64"><Spinner size="xl" /></div>;
  if (error) return <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Governance Dashboard</h1>
        <p className="text-gray-400 mt-1">Governance controls, compliance, and audit for AI operations</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <p className="text-gray-400 text-sm">Prompt Versions</p>
          <p className="text-3xl font-bold text-white">{dashboard?.prompt_versions || 0}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Model Versions</p>
          <p className="text-3xl font-bold text-white">{dashboard?.model_versions || 0}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Audit Entries</p>
          <p className="text-3xl font-bold text-white">{dashboard?.audit_entries || compliance?.total_decisions || 0}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Safety Policy</p>
          <p className="text-lg font-bold text-white">{dashboard?.safety_policy || 'moderate'}</p>
        </Card>
      </div>

      {compliance && (
        <Card>
          <h3 className="text-lg font-semibold text-white mb-4">Compliance Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-gray-400 text-sm">Total Decisions</p>
              <p className="text-xl font-bold text-white">{compliance.total_decisions || 0}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Safety Flagged</p>
              <p className="text-xl font-bold text-white">{compliance.safety_flagged || 0}</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Safety Rate</p>
              <p className="text-xl font-bold text-white">{compliance.safety_rate || 0}%</p>
            </div>
            <div>
              <p className="text-gray-400 text-sm">Failed Requests</p>
              <p className="text-xl font-bold text-white">{compliance.failed_requests || 0}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div>
              <p className="text-gray-400 text-sm mb-2">By Event Type</p>
              {compliance.by_event_type && Object.entries(compliance.by_event_type).length > 0 ? (
                Object.entries(compliance.by_event_type).map(([event, count]) => (
                  <div key={event} className="flex justify-between text-sm text-gray-300">
                    <span>{event}</span><span>{count}</span>
                  </div>
                ))
              ) : <p className="text-gray-500 text-sm">No data</p>}
            </div>
            <div>
              <p className="text-gray-400 text-sm mb-2">By Provider</p>
              {compliance.by_provider && Object.entries(compliance.by_provider).length > 0 ? (
                Object.entries(compliance.by_provider).map(([provider, count]) => (
                  <div key={provider} className="flex justify-between text-sm text-gray-300">
                    <span>{provider}</span><span>{count}</span>
                  </div>
                ))
              ) : <p className="text-gray-500 text-sm">No data</p>}
            </div>
          </div>
        </Card>
      )}

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Recent Audit Trail</h3>
        <div className="space-y-2">
          {auditLog.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No audit entries yet</p>
          ) : (
            auditLog.map((entry, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-gray-800 rounded-lg">
                <Badge variant={entry.status === 'completed' ? 'success' : entry.status === 'failed' ? 'error' : 'warning'}>
                  {entry.status || 'unknown'}
                </Badge>
                <div className="flex-1">
                  <p className="text-white text-sm font-medium">{entry.event_type}</p>
                  <p className="text-gray-500 text-xs">
                    {entry.provider_id && `Provider: ${entry.provider_id}`}
                    {entry.model_id && ` • Model: ${entry.model_id}`}
                    {entry.safety_flagged && ' • 🚩 Safety Flagged'}
                  </p>
                  <div className="flex gap-3 mt-1 text-xs text-gray-600">
                    {entry.tokens_used > 0 && <span>{entry.tokens_used} tokens</span>}
                    {entry.cost_usd > 0 && <span>${entry.cost_usd.toFixed(6)}</span>}
                    {entry.latency_ms > 0 && <span>{entry.latency_ms}ms</span>}
                  </div>
                </div>
                <span className="text-gray-600 text-xs">{new Date(entry.timestamp).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Governance Settings</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><p className="text-gray-400 text-sm">Prompt Versions</p><p className="text-white">{dashboard?.prompt_versions || 0}</p></div>
          <div><p className="text-gray-400 text-sm">Model Versions</p><p className="text-white">{dashboard?.model_versions || 0}</p></div>
          <div><p className="text-gray-400 text-sm">Safety Policies</p><p className="text-white">{dashboard?.safety_policies_configured || 0}</p></div>
          <div><p className="text-gray-400 text-sm">Tenant Configs</p><p className="text-white">{dashboard?.tenant_configs || 0}</p></div>
        </div>
      </Card>
    </div>
  );
};

export default AIGovernanceDashboardPage;

