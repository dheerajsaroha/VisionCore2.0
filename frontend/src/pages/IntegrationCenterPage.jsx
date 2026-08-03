import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Tabs } from '../components/ui/Tabs';
import integrationService from '../services/integrationService';

const IntegrationCenterPage = () => {
  const [activeTab, setActiveTab] = useState('webhooks');
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [webhooks, setWebhooks] = useState([]);
  const [oauthClients, setOauthClients] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [connectors, setConnectors] = useState([]);
  const [deadLetter, setDeadLetter] = useState([]);
  const [error, setError] = useState(null);

  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [showConnectorModal, setShowConnectorModal] = useState(false);
  const [newApiKey, setNewApiKey] = useState(null);
  const [webhookForm, setWebhookForm] = useState({
    name: '', url: '', method: 'POST', events: [],
    retry_count: 3, retry_delay_seconds: 60, timeout_seconds: 30, description: ''
  });
  const [apiKeyForm, setApiKeyForm] = useState({
    name: '', permissions: [], expires_at: ''
  });
  const [connectorForm, setConnectorForm] = useState({
    name: '', connector_type: 'webhook', config: {}, is_active: true
  });

  const tabs = [
    { id: 'webhooks', label: 'Webhooks' },
    { id: 'oauth2', label: 'OAuth2' },
    { id: 'api-keys', label: 'API Keys' },
    { id: 'connectors', label: 'Connectors' },
    { id: 'dead-letter', label: 'Dead Letter Queue' },
  ];

  const StatusBadge = ({ status }) => {
    const colors = {
      active: 'bg-green-500/20 text-green-400',
      inactive: 'bg-gray-500/20 text-gray-400',
      error: 'bg-red-500/20 text-red-400',
      pending: 'bg-yellow-500/20 text-yellow-400',
      disconnected: 'bg-orange-500/20 text-orange-400',
    };
    return (
      <Badge className={colors[status] || 'bg-gray-500/20 text-gray-400'}>
        {status}
      </Badge>
    );
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData] = await Promise.all([
        integrationService.getSummary(),
        integrationService.getAvailableEvents(),
      ]);
      setSummary(summaryData.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const loadTabData = useCallback(async (tab) => {
    try {
      switch (tab) {
        case 'webhooks': {
          const data = await integrationService.getWebhooks();
          setWebhooks(data.webhooks || []);
          break;
        }
        case 'oauth2': {
          const data = await integrationService.getOAuth2Clients();
          setOauthClients(data.clients || []);
          break;
        }
        case 'api-keys': {
          const data = await integrationService.getApiKeys();
          setApiKeys(data.api_keys || []);
          break;
        }
        case 'connectors': {
          const data = await integrationService.getConnectors();
          setConnectors(data.connectors || []);
          break;
        }
        case 'dead-letter': {
          const data = await integrationService.getDeadLetterQueue();
          setDeadLetter(data.entries || []);
          break;
        }
      }
    } catch (err) {
      console.error(`Error loading ${tab}:`, err);
    }
  }, []);

  useEffect(() => { loadTabData(activeTab); }, [activeTab, loadTabData]);

  const handleCreateWebhook = async () => {
    try {
      await integrationService.createWebhook(webhookForm);
      setShowWebhookModal(false);
      setWebhookForm({ name: '', url: '', method: 'POST', events: [], retry_count: 3, retry_delay_seconds: 60, timeout_seconds: 30, description: '' });
      loadTabData('webhooks');
      loadData();
    } catch (err) {
      setError(`Failed to create webhook: ${err.message}`);
    }
  };

  const handleDeleteWebhook = async (id) => {
    if (!window.confirm('Delete this webhook?')) return;
    try {
      await integrationService.deleteWebhook(id);
      loadTabData('webhooks');
      loadData();
    } catch (err) {
      setError(`Failed to delete webhook: ${err.message}`);
    }
  };

  const handleCreateApiKey = async () => {
    try {
      const result = await integrationService.createApiKey(apiKeyForm);
      setNewApiKey(result.api_key);
      setShowApiKeyModal(false);
      setApiKeyForm({ name: '', permissions: [], expires_at: '' });
      loadTabData('api-keys');
      loadData();
    } catch (err) {
      setError(`Failed to create API key: ${err.message}`);
    }
  };

  const handleRevokeApiKey = async (id) => {
    if (!window.confirm('Revoke this API key?')) return;
    try {
      await integrationService.revokeApiKey(id);
      loadTabData('api-keys');
      loadData();
    } catch (err) {
      setError(`Failed to revoke API key: ${err.message}`);
    }
  };

  const handleCreateConnector = async () => {
    try {
      await integrationService.createConnector(connectorForm);
      setShowConnectorModal(false);
      setConnectorForm({ name: '', connector_type: 'webhook', config: {}, is_active: true });
      loadTabData('connectors');
      loadData();
    } catch (err) {
      setError(`Failed to create connector: ${err.message}`);
    }
  };

  const handleTestConnector = async (id) => {
    try {
      const result = await integrationService.testConnector(id);
      alert(`Connector test: ${result.result.success ? '✅ Success' : '❌ Failed'}\n${result.result.message}`);
      loadTabData('connectors');
    } catch (err) {
      setError(`Test failed: ${err.message}`);
    }
  };

  const handleRetryDeadLetter = async (deliveryId) => {
    try {
      await integrationService.retryDeadLetter(deliveryId);
      loadTabData('dead-letter');
      loadData();
    } catch (err) {
      setError(`Retry failed: ${err.message}`);
    }
  };

  const handleViewDeliveries = async (webhookId) => {
    try {
      const data = await integrationService.getWebhookDeliveries(webhookId);
      alert(`Found ${data.deliveries?.length || 0} delivery log entries for webhook ${webhookId}`);
    } catch (err) {
      setError(`Failed to load delivery logs: ${err.message}`);
    }
  };

  const handleClearDeadLetter = async () => {
    if (!window.confirm('Clear all dead letter entries?')) return;
    try {
      await integrationService.clearDeadLetterQueue();
      loadTabData('dead-letter');
    } catch (err) {
      setError(`Failed to clear: ${err.message}`);
    }
  };

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Integration Center</h1>
          <p className="text-gray-400 mt-1">Manage webhooks, API keys, and external connectors</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
          {error}
          <button className="ml-2 text-red-300 hover:text-red-200" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4 bg-gray-800/50 border-gray-700">
            <div className="text-sm text-gray-400">Webhooks</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.active_webhooks}/{summary.total_webhooks}</div>
            <div className="text-xs text-gray-500">Active</div>
          </Card>
          <Card className="p-4 bg-gray-800/50 border-gray-700">
            <div className="text-sm text-gray-400">API Keys</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.active_api_keys}/{summary.total_api_keys}</div>
            <div className="text-xs text-gray-500">Active</div>
          </Card>
          <Card className="p-4 bg-gray-800/50 border-gray-700">
            <div className="text-sm text-gray-400">Delivery Rate</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.success_rate}%</div>
            <div className="text-xs text-gray-500">{summary.total_deliveries} deliveries</div>
          </Card>
          <Card className="p-4 bg-gray-800/50 border-gray-700">
            <div className="text-sm text-gray-400">Connectors</div>
            <div className="text-2xl font-bold text-white mt-1">{summary.active_connectors}/{summary.total_connectors}</div>
            <div className="text-xs text-gray-500">Active</div>
          </Card>
        </div>
      )}

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Webhooks Tab */}
      {activeTab === 'webhooks' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-white">Webhook Endpoints</h3>
            <Button onClick={() => setShowWebhookModal(true)}>+ Add Webhook</Button>
          </div>
          {webhooks.length === 0 ? (
            <Card className="p-8 text-center bg-gray-800/50 border-gray-700">
              <p className="text-gray-400">No webhooks configured. Create one to receive event notifications.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {webhooks.map((wh) => (
                <Card key={wh.id} className="p-4 bg-gray-800/50 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-white">{wh.name}</h4>
                        <StatusBadge status={wh.status} />
                      </div>
                      <p className="text-sm text-gray-400 mt-1">{wh.url}</p>
                      <div className="flex gap-2 mt-2">
                        {wh.events?.slice(0, 3).map(ev => (
                          <Badge key={ev} className="bg-indigo-500/20 text-indigo-400">{ev}</Badge>
                        ))}
                        {wh.events?.length > 3 && (
                          <Badge className="bg-gray-500/20 text-gray-400">+{wh.events.length - 3}</Badge>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-2">
                        {wh.delivery_count} deliveries · {wh.failure_count} failures
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => handleViewDeliveries(wh.id)}>Logs</Button>
                      <Button variant="danger" size="sm" onClick={() => handleDeleteWebhook(wh.id)}>Delete</Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* OAuth2 Tab */}
      {activeTab === 'oauth2' && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white">OAuth2 Clients</h3>
          {oauthClients.length === 0 ? (
            <Card className="p-8 text-center bg-gray-800/50 border-gray-700">
              <p className="text-gray-400">No OAuth2 clients configured.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {oauthClients.map((client) => (
                <Card key={client.id} className="p-4 bg-gray-800/50 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-white">{client.name}</h4>
                        <StatusBadge status={client.status} />
                      </div>
                      <p className="text-sm text-gray-400">Provider: {client.provider}</p>
                      <div className="flex gap-1 mt-1">
                        {client.scopes?.map(s => (
                          <Badge key={s} className="bg-blue-500/20 text-blue-400">{s}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* API Keys Tab */}
      {activeTab === 'api-keys' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-white">API Keys</h3>
            <Button onClick={() => setShowApiKeyModal(true)}>+ Generate Key</Button>
          </div>
          {newApiKey && (
            <Card className="p-4 bg-yellow-500/10 border-yellow-500/20">
              <h4 className="font-semibold text-yellow-400">⚠️ API Key Generated</h4>
              <p className="text-sm text-yellow-300 mt-1">Save this key now. It will not be shown again.</p>
              <div className="mt-2 p-2 bg-gray-900 rounded font-mono text-sm text-yellow-200 break-all">
                {newApiKey.full_key}
              </div>
              <Button size="sm" className="mt-2" onClick={() => { navigator.clipboard.writeText(newApiKey.full_key); alert('Copied!'); }}>
                Copy Key
              </Button>
            </Card>
          )}
          {apiKeys.length === 0 ? (
            <Card className="p-8 text-center bg-gray-800/50 border-gray-700">
              <p className="text-gray-400">No API keys generated.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {apiKeys.map((key) => (
                <Card key={key.id} className="p-4 bg-gray-800/50 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-white">{key.name}</h4>
                        <StatusBadge status={key.status} />
                      </div>
                      <p className="text-sm font-mono text-gray-400">{key.key_prefix}...</p>
                      <div className="flex gap-1 mt-1">
                        {key.permissions?.slice(0, 3).map(p => (
                          <Badge key={p} className="bg-green-500/20 text-green-400">{p}</Badge>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {key.is_active && (
                        <Button variant="danger" size="sm" onClick={() => handleRevokeApiKey(key.id)}>Revoke</Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Connectors Tab */}
      {activeTab === 'connectors' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-white">External Connectors</h3>
            <Button onClick={() => setShowConnectorModal(true)}>+ Add Connector</Button>
          </div>
          {connectors.length === 0 ? (
            <Card className="p-8 text-center bg-gray-800/50 border-gray-700">
              <p className="text-gray-400">No connectors configured.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {connectors.map((conn) => (
                <Card key={conn.id} className="p-4 bg-gray-800/50 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-white">{conn.name}</h4>
                        <StatusBadge status={conn.status} />
                      </div>
                      <p className="text-sm text-gray-400">Type: {conn.connector_type}</p>
                      {conn.health_message && (
                        <p className="text-xs text-gray-500 mt-1">{conn.health_message}</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => handleTestConnector(conn.id)}>Test</Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dead Letter Queue Tab */}
      {activeTab === 'dead-letter' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-white">Dead Letter Queue</h3>
            {deadLetter.length > 0 && (
              <Button variant="danger" size="sm" onClick={handleClearDeadLetter}>Clear All</Button>
            )}
          </div>
          {deadLetter.length === 0 ? (
            <Card className="p-8 text-center bg-gray-800/50 border-gray-700">
              <p className="text-gray-400">Dead letter queue is empty.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {deadLetter.map((entry) => (
                <Card key={entry.delivery_id} className="p-4 bg-gray-800/50 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge className="bg-red-500/20 text-red-400">Failed</Badge>
                        <span className="text-sm text-gray-300">{entry.event_type}</span>
                      </div>
                      <p className="text-sm text-gray-400 mt-1">{entry.url}</p>
                      <p className="text-xs text-gray-500 mt-1">Error: {entry.error}</p>
                      <p className="text-xs text-gray-500">Attempts: {entry.attempts}</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => handleRetryDeadLetter(entry.delivery_id)}>
                      Retry
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Webhook Modal */}
      <Modal isOpen={showWebhookModal} onClose={() => setShowWebhookModal(false)} title="Create Webhook">
        <div className="space-y-4">
          <Input label="Name" value={webhookForm.name} onChange={e => setWebhookForm({...webhookForm, name: e.target.value})} placeholder="My Webhook" />
          <Input label="URL" value={webhookForm.url} onChange={e => setWebhookForm({...webhookForm, url: e.target.value})} placeholder="https://example.com/webhook" />
          <Select label="Method" value={webhookForm.method} onChange={e => setWebhookForm({...webhookForm, method: e.target.value})} options={['GET', 'POST', 'PUT', 'PATCH', 'DELETE']} />
          <Input label="Description" value={webhookForm.description} onChange={e => setWebhookForm({...webhookForm, description: e.target.value})} placeholder="Optional description" />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowWebhookModal(false)}>Cancel</Button>
            <Button onClick={handleCreateWebhook}>Create</Button>
          </div>
        </div>
      </Modal>

      {/* API Key Modal */}
      <Modal isOpen={showApiKeyModal} onClose={() => setShowApiKeyModal(false)} title="Generate API Key">
        <div className="space-y-4">
          <Input label="Key Name" value={apiKeyForm.name} onChange={e => setApiKeyForm({...apiKeyForm, name: e.target.value})} placeholder="My API Key" />
          <Input label="Expires At" type="date" value={apiKeyForm.expires_at} onChange={e => setApiKeyForm({...apiKeyForm, expires_at: e.target.value})} />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowApiKeyModal(false)}>Cancel</Button>
            <Button onClick={handleCreateApiKey}>Generate</Button>
          </div>
        </div>
      </Modal>

      {/* Connector Modal */}
      <Modal isOpen={showConnectorModal} onClose={() => setShowConnectorModal(false)} title="Add Connector">
        <div className="space-y-4">
          <Input label="Name" value={connectorForm.name} onChange={e => setConnectorForm({...connectorForm, name: e.target.value})} placeholder="My Connector" />
          <Select label="Type" value={connectorForm.connector_type} onChange={e => setConnectorForm({...connectorForm, connector_type: e.target.value})} options={['slack', 'email_smtp', 'sms_twilio', 'calendar', 'storage_s3', 'payment_stripe', 'custom']} />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowConnectorModal(false)}>Cancel</Button>
            <Button onClick={handleCreateConnector}>Create</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default IntegrationCenterPage;
