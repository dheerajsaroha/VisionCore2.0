import React, { useState, useEffect } from 'react';
import aiService from '../services/aiService';
import { Card } from '../components/ui/Card';
import { Spinner } from '../components/ui/Spinner';
import { Tabs } from '../components/ui/Tabs';

const AIUsageDashboardPage = () => {
  const [usage, setUsage] = useState(null);
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [usageData, statsData] = await Promise.all([
        aiService.getUsageSummary(), aiService.getAIStats(),
      ]);
      setUsage(usageData);
      setStats(statsData);
    } catch (err) { setError(err.message); }
    finally { setIsLoading(false); }
  };

  if (isLoading) return <div className="flex items-center justify-center h-64"><Spinner size="xl" /></div>;
  if (error) return <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Usage Dashboard</h1>
        <p className="text-gray-400 mt-1">Detailed usage and cost tracking for AI operations</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <p className="text-gray-400 text-sm">Total Requests</p>
          <p className="text-3xl font-bold text-white">{usage?.total_requests || 0}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Total Tokens</p>
          <p className="text-3xl font-bold text-white">{(usage?.total_tokens || 0).toLocaleString()}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Total Cost</p>
          <p className="text-3xl font-bold text-white">${(usage?.total_cost_usd || 0).toFixed(4)}</p>
        </Card>
        <Card>
          <p className="text-gray-400 text-sm">Avg Latency</p>
          <p className="text-3xl font-bold text-white">{usage?.avg_latency_ms || 0}ms</p>
        </Card>
      </div>

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Requests by Provider</h3>
        <div className="space-y-2">
          {usage?.requests_by_provider && Object.entries(usage.requests_by_provider).length > 0
            ? Object.entries(usage.requests_by_provider).map(([provider, count]) => (
                <div key={provider} className="flex items-center justify-between p-2 bg-gray-800 rounded">
                  <span className="text-white text-sm">{provider}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-700 rounded-full h-2">
                      <div className="bg-indigo-500 rounded-full h-2" style={{ width: `${(count / usage.total_requests) * 100}%` }} />
                    </div>
                    <span className="text-gray-400 text-sm">{count}</span>
                  </div>
                </div>
              ))
            : <p className="text-gray-500 text-center py-4">No data</p>}
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Tokens by Model</h3>
        <div className="space-y-2">
          {usage?.tokens_by_model && Object.entries(usage.tokens_by_model).length > 0
            ? Object.entries(usage.tokens_by_model).map(([model, tokens]) => (
                <div key={model} className="flex items-center justify-between p-2 bg-gray-800 rounded">
                  <span className="text-white text-sm">{model}</span>
                  <span className="text-gray-400 text-sm">{tokens.toLocaleString()} tokens</span>
                </div>
              ))
            : <p className="text-gray-500 text-center py-4">No data</p>}
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Cost by Organization</h3>
        <div className="space-y-2">
          {usage?.cost_by_organization && Object.entries(usage.cost_by_organization).length > 0
            ? Object.entries(usage.cost_by_organization).map(([org, cost]) => (
                <div key={org} className="flex items-center justify-between p-2 bg-gray-800 rounded">
                  <span className="text-white text-sm">Org: {org}</span>
                  <span className="text-gray-400 text-sm">${cost.toFixed(4)}</span>
                </div>
              ))
            : <p className="text-gray-500 text-center py-4">No data</p>}
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Platform Stats</h3>
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div><p className="text-gray-400 text-sm">Providers</p><p className="text-xl font-bold text-white">{stats.total_providers}</p><p className="text-xs text-green-400">{stats.active_providers} active</p></div>
            <div><p className="text-gray-400 text-sm">Models</p><p className="text-xl font-bold text-white">{stats.total_models}</p></div>
            <div><p className="text-gray-400 text-sm">Prompts</p><p className="text-xl font-bold text-white">{stats.total_prompts}</p></div>
            <div><p className="text-gray-400 text-sm">Usage Records</p><p className="text-xl font-bold text-white">{stats.usage_history_count}</p></div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default AIUsageDashboardPage;

