import React, { useState, useEffect, useCallback } from 'react';
import { Spinner } from '../components/ui/Spinner';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Tabs } from '../components/ui/Tabs';
import {
  getPlatformHealth,
  getOperationsDashboard,
  listJobs,
  getJobDefinitions,
  getConfigurations,
  getConfigCategories,
  getFeatureFlags,
  getAnomalies,
  getInsights,
  getRiskAssessment,
  getExecutiveDashboard,
  getReportTemplates,
  getEventStats,
  startScheduler,
  stopScheduler,
  seedDefaultJobs,
  cancelJob,
  globalSearch,
  updateConfiguration,
  generateReport,
} from '../services/operationsService';

const OperationsDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [health, setHealth] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [jobDefs, setJobDefs] = useState([]);
  const [configs, setConfigs] = useState({});
  const [configCategories, setConfigCategories] = useState([]);
  const [featureFlags, setFeatureFlags] = useState({});
  const [anomalies, setAnomalies] = useState([]);
  const [insights, setInsights] = useState([]);
  const [riskAssessment, setRiskAssessment] = useState(null);
  const [execDashboard, setExecDashboard] = useState(null);
  const [reportTemplates, setReportTemplates] = useState([]);
  const [eventStats, setEventStats] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [error, setError] = useState(null);
  const [schedulerRunning, setSchedulerRunning] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
const [healthData, dashboardData, jobsData, jobDefsData, configData, catData, flagsData, anomaliesData, insightsData, riskData, execData, templatesData, eventsData] = await Promise.allSettled([
        getPlatformHealth(),
        getOperationsDashboard(),
        listJobs({ limit: 20 }),
        getJobDefinitions(),
        getConfigurations(),
        getConfigCategories(),
        getFeatureFlags(),
        getAnomalies(),
        getInsights(),
        getRiskAssessment(),
        getExecutiveDashboard(),
        getReportTemplates(),
        getEventStats(),
      ]);

      if (healthData.status === 'fulfilled') setHealth(healthData.value);
      if (dashboardData.status === 'fulfilled') setDashboard(dashboardData.value);
      if (jobsData.status === 'fulfilled') setJobs(jobsData.value.jobs || []);
      if (jobDefsData.status === 'fulfilled') setJobDefs(jobDefsData.value.definitions || []);
      if (configData.status === 'fulfilled') setConfigs(configData.value);
      if (catData.status === 'fulfilled') setConfigCategories(catData.value.categories || []);
      if (flagsData.status === 'fulfilled') setFeatureFlags(flagsData.value);
      if (anomaliesData.status === 'fulfilled') setAnomalies(anomaliesData.value.anomalies || []);
      if (insightsData.status === 'fulfilled') setInsights(insightsData.value.insights || []);
      if (riskData.status === 'fulfilled') setRiskAssessment(riskData.value);
      if (execData.status === 'fulfilled') setExecDashboard(execData.value);
      if (templatesData.status === 'fulfilled') setReportTemplates(templatesData.value.templates || []);
      if (eventsData.status === 'fulfilled') setEventStats(eventsData.value);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const results = await globalSearch(searchQuery, { limit: 10 });
      setSearchResults(results);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleConfigUpdate = async (key, value) => {
    try {
      await updateConfiguration(key, value);
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReportGenerate = async (template) => {
    try {
      await generateReport({ template, format: 'json' });
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleScheduler = async (action) => {
    try {
      if (action === 'start') {
        await startScheduler();
        setSchedulerRunning(true);
      } else {
        await stopScheduler();
        setSchedulerRunning(false);
      }
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSeedJobs = async () => {
    try {
      await seedDefaultJobs();
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCancelJob = async (jobId) => {
    try {
      await cancelJob(jobId);
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 p-6">
        <Card className="border-red-500/30 bg-red-500/10">
          <div className="text-red-400">
            <h3 className="text-lg font-semibold mb-2">Error Loading Operations Dashboard</h3>
            <p>{error}</p>
            <button
              onClick={fetchData}
              className="mt-4 px-4 py-2 bg-red-500/20 text-red-300 rounded hover:bg-red-500/30"
            >
              Retry
            </button>
          </div>
        </Card>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'health', label: 'Health & Monitoring' },
    { id: 'jobs', label: 'Jobs & Scheduler' },
    { id: 'analytics', label: 'Analytics' },
    { id: 'search', label: 'Search' },
    { id: 'config', label: 'Configuration' },
    { id: 'intelligence', label: 'Intelligence' },
    { id: 'reports', label: 'Reports' },
    { id: 'events', label: 'Events' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Platform Operations</h1>
          <p className="text-gray-400 mt-1">Enterprise platform operations dashboard</p>
        </div>
        {health && (
          <Badge variant={health.status === 'healthy' ? 'success' : 'warning'}>
            {health.status === 'healthy' ? 'Healthy' : 'Degraded'}
          </Badge>
        )}
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Health Score */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Health Score</h3>
              <p className={`text-3xl font-bold mt-2 ${
                dashboard?.health?.score >= 0.7 ? 'text-green-400' : 'text-yellow-400'
              }`}>
                {dashboard?.health?.score ? `${Math.round(dashboard.health.score * 100)}%` : 'N/A'}
              </p>
            </Card>

            {/* Scheduler Stats */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Scheduler</h3>
              <p className="text-3xl font-bold mt-2 text-indigo-400">
                {dashboard?.scheduler?.total || 0}
              </p>
              <div className="flex gap-2 mt-2 text-xs">
                <span className="text-green-400">Active: {dashboard?.scheduler?.active || 0}</span>
                <span className="text-red-400">Failed: {dashboard?.scheduler?.failed || 0}</span>
              </div>
            </Card>

            {/* Config Center */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Config Center</h3>
              <p className="text-3xl font-bold mt-2 text-blue-400">
                {dashboard?.config_center?.total_configs || 0}
              </p>
              <p className="text-xs text-gray-500 mt-2">Configurations</p>
            </Card>

            {/* Anomalies */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Anomalies</h3>
              <p className={`text-3xl font-bold mt-2 ${
                anomalies.length > 0 ? 'text-red-400' : 'text-green-400'
              }`}>
                {anomalies.length}
              </p>
              <p className="text-xs text-gray-500 mt-2">Recent anomalies detected</p>
            </Card>

            {/* Risk Assessment */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Risk Level</h3>
              <p className={`text-3xl font-bold mt-2 ${
                riskAssessment?.risk_level === 'low' ? 'text-green-400' :
                riskAssessment?.risk_level === 'medium' ? 'text-yellow-400' :
                riskAssessment?.risk_level === 'high' ? 'text-orange-400' : 'text-red-400'
              }`}>
                {riskAssessment?.risk_level?.toUpperCase() || 'N/A'}
              </p>
              <p className="text-xs text-gray-500 mt-2">Score: {riskAssessment?.risk_score || 0}</p>
            </Card>

            {/* Insights */}
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-sm font-medium text-gray-400">Insights</h3>
              <p className="text-3xl font-bold mt-2 text-purple-400">{insights.length}</p>
              <p className="text-xs text-gray-500 mt-2">Actionable insights</p>
            </Card>
          </div>
        )}

        {activeTab === 'health' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">System Health Checks</h3>
              {health?.checks?.map((check, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                  <div>
                    <p className="text-white font-medium">{check.component}</p>
                    <p className="text-gray-400 text-sm">{check.message}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {check.latency_ms && (
                      <span className="text-xs text-gray-500">{check.latency_ms}ms</span>
                    )}
                    <Badge variant={check.status === 'healthy' ? 'success' : 'danger'}>
                      {check.status}
                    </Badge>
                  </div>
                </div>
              ))}
              {(!health?.checks || health.checks.length === 0) && (
                <p className="text-gray-400">No health checks available</p>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <button
                onClick={() => handleScheduler(schedulerRunning ? 'stop' : 'start')}
                className={`px-4 py-2 rounded ${
                  schedulerRunning
                    ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30'
                    : 'bg-green-500/20 text-green-300 hover:bg-green-500/30'
                }`}
              >
                {schedulerRunning ? 'Stop Scheduler' : 'Start Scheduler'}
              </button>
              <button
                onClick={handleSeedJobs}
                className="px-4 py-2 bg-indigo-500/20 text-indigo-300 rounded hover:bg-indigo-500/30"
              >
                Seed Default Jobs
              </button>
            </div>

            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Recent Jobs</h3>
              {jobs.length > 0 ? (
                <div className="space-y-2">
                  {jobs.map((job, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                      <div>
                        <p className="text-white font-medium">{job.name}</p>
                        <p className="text-gray-400 text-sm">{job.module} - {job.task}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={
                          job.status === 'completed' ? 'success' :
                          job.status === 'failed' ? 'danger' :
                          job.status === 'running' ? 'warning' : 'default'
                        }>
                          {job.status}
                        </Badge>
                        {job.status === 'running' && (
                          <button
                            onClick={() => handleCancelJob(job.id)}
                            className="px-2 py-1 bg-red-500/20 text-red-300 text-xs rounded"
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No jobs found. Seed default jobs to get started.</p>
              )}
            </Card>

            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Job Definitions</h3>
              {jobDefs.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {jobDefs.map((def, i) => (
                    <div key={i} className="p-3 bg-gray-800/50 rounded border border-gray-700/50">
                      <p className="text-white font-medium">{def.name}</p>
                      <p className="text-gray-400 text-xs">{def.module} - {def.task}</p>
                      <p className="text-gray-500 text-xs mt-1">{def.description}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No job definitions available</p>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Executive Dashboard</h3>
              {execDashboard ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(execDashboard).map(([key, value]) => (
                    <div key={key} className="p-3 bg-gray-800/50 rounded">
                      <p className="text-gray-400 text-sm capitalize">{key.replace(/_/g, ' ')}</p>
                      <p className="text-white text-lg font-bold mt-1">
                        {typeof value === 'object' ? JSON.stringify(value).substring(0, 30) : String(value)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No analytics data available</p>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'search' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <form onSubmit={handleSearch} className="flex gap-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search across all modules..."
                  className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button
                  type="submit"
                  className="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
                >
                  Search
                </button>
              </form>
            </Card>

            {searchResults && (
              <Card className="p-4 bg-gray-900/50 border-gray-700/50">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Search Results ({searchResults.total || 0})
                </h3>
                {searchResults.results?.length > 0 ? (
                  <div className="space-y-2">
                    {searchResults.results.map((result, i) => (
                      <div key={i} className="p-3 bg-gray-800/50 rounded border border-gray-700/50">
                        <div className="flex items-center gap-2">
                          <Badge>{result.module}</Badge>
                          <span className="text-white font-medium">{result.title}</span>
                        </div>
                        <p className="text-gray-400 text-sm mt-1">{result.summary}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400">No results found</p>
                )}
              </Card>
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Configuration Categories</h3>
              <div className="flex flex-wrap gap-2">
                {configCategories.map((cat) => (
                  <Badge key={cat} variant="info">{cat}</Badge>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Feature Flags</h3>
              <div className="space-y-2">
                {Object.entries(featureFlags).map(([key, config]) => (
                  <div key={key} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                    <div>
                      <p className="text-white font-medium">{key}</p>
                      <p className="text-gray-400 text-xs">{config.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={config.value ? 'success' : 'default'}>
                        {config.value ? 'Enabled' : 'Disabled'}
                      </Badge>
                      <button
                        onClick={() => handleConfigUpdate(key, !config.value)}
                        className="px-2 py-1 text-xs bg-indigo-500/20 text-indigo-300 rounded hover:bg-indigo-500/30"
                      >
                        Toggle
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">All Configurations</h3>
              <div className="space-y-2">
                {Object.entries(configs).map(([key, config]) => (
                  <div key={key} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                    <div>
                      <p className="text-white font-medium">{key}</p>
                      <p className="text-gray-400 text-xs">{config.description}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-white">{String(config.value)}</p>
                      <p className="text-gray-500 text-xs">{config.data_type}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'intelligence' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Anomalies</h3>
              {anomalies.length > 0 ? (
                <div className="space-y-2">
                  {anomalies.map((anomaly, i) => (
                    <div key={i} className="p-3 bg-gray-800/50 rounded border border-gray-700/50">
                      <div className="flex items-center gap-2">
                        <Badge variant={
                          anomaly.risk_level === 'critical' ? 'danger' :
                          anomaly.risk_level === 'high' ? 'warning' : 'info'
                        }>
                          {anomaly.risk_level}
                        </Badge>
                        <span className="text-white font-medium">{anomaly.type}</span>
                      </div>
                      <p className="text-gray-400 text-sm mt-1">{anomaly.description}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No anomalies detected</p>
              )}
            </Card>

            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Insights</h3>
              {insights.length > 0 ? (
                <div className="space-y-2">
                  {insights.map((insight, i) => (
                    <div key={i} className="p-3 bg-gray-800/50 rounded border border-gray-700/50">
                      <div className="flex items-center gap-2">
                        <Badge variant={
                          insight.priority === 'high' ? 'danger' :
                          insight.priority === 'medium' ? 'warning' : 'info'
                        }>
                          {insight.priority}
                        </Badge>
                        <span className="text-white">{insight.message}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No insights available</p>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Report Templates</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {reportTemplates.map((template, i) => (
                  <div key={i} className="p-4 bg-gray-800/50 rounded border border-gray-700/50">
                    <h4 className="text-white font-medium">{template.name}</h4>
                    <p className="text-gray-400 text-sm mt-1">{template.description}</p>
                    <div className="flex gap-2 mt-3">
                      <Badge>{template.category}</Badge>
                      <Badge>{template.format}</Badge>
                    </div>
                    <button
                      onClick={() => handleReportGenerate(template.code)}
                      className="mt-3 px-3 py-1.5 bg-indigo-500/20 text-indigo-300 text-sm rounded hover:bg-indigo-500/30"
                    >
                      Generate
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'events' && (
          <div className="space-y-4">
            <Card className="p-4 bg-gray-900/50 border-gray-700/50">
              <h3 className="text-lg font-semibold text-white mb-4">Event Bus Statistics</h3>
              {eventStats ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(eventStats).map(([key, value]) => (
                    <div key={key} className="p-3 bg-gray-800/50 rounded">
                      <p className="text-gray-400 text-sm capitalize">{key.replace(/_/g, ' ')}</p>
                      <p className="text-white text-lg font-bold mt-1">{String(value)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No event stats available</p>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default OperationsDashboard;
