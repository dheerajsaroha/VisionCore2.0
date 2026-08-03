import React, { useState, useEffect, useCallback } from 'react';
import EnterpriseService from '../services/enterpriseService';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Tabs } from '../components/ui/Tabs';
import { EmptyState } from '../components/ui/EmptyState';

const StatusBadge = ({ status }) => {
  const colorMap = {
    healthy: 'success',
    warning: 'warning',
    error: 'error',
    passed: 'success',
    failed: 'error',
  };
  return (
    <Badge variant={colorMap[status?.toLowerCase()] || 'default'}>
      {status || 'unknown'}
    </Badge>
  );
};

const MetricCard = ({ label, value, status }) => (
  <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
    <p className="text-sm text-gray-400 mb-1">{label}</p>
    <p className="text-2xl font-bold text-white">{value ?? '—'}</p>
    {status && <StatusBadge status={status} />}
  </div>
);

const IntegrationStatusCard = ({ title, items }) => (
  <Card className="mb-6">
    <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
    <div className="space-y-2">
      {Object.entries(items).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between py-1">
          <span className="text-sm text-gray-300 capitalize">
            {key.replace(/_/g, ' ')}
          </span>
          {typeof value === 'object' ? (
            <span className="text-sm text-gray-400">
              {value.status || JSON.stringify(value)}
            </span>
          ) : (
            <StatusBadge status={value} />
          )}
        </div>
      ))}
    </div>
  </Card>
);

const NotificationPanel = ({ notifications, onMarkRead }) => {
  if (!notifications?.length) {
    return <EmptyState title="No notifications" description="You're all caught up!" />;
  }

  return (
    <div className="space-y-3">
      {notifications.map((notif) => (
        <div
          key={notif.id}
          className={`p-4 rounded-lg border ${
            notif.is_read
              ? 'bg-gray-800/30 border-gray-700'
              : 'bg-gray-800/60 border-indigo-500/30'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="text-sm font-medium text-white">{notif.title}</h4>
                {!notif.is_read && (
                  <span className="w-2 h-2 bg-indigo-500 rounded-full" />
                )}
                <Badge variant="default" className="text-xs">
                  {notif.priority}
                </Badge>
              </div>
              <p className="text-sm text-gray-400">{notif.message}</p>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(notif.created_at).toLocaleString()} · {notif.source_module}
              </p>
            </div>
            {!notif.is_read && (
              <button
                onClick={() => onMarkRead(notif.id)}
                className="text-xs text-indigo-400 hover:text-indigo-300 ml-4"
              >
                Mark Read
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

const AuditTimeline = ({ entries }) => {
  if (!entries?.length) {
    return <EmptyState title="No audit entries" description="No activity recorded yet." />;
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/20 border border-gray-700/50"
        >
          <div className="flex-shrink-0 mt-0.5">
            <div
              className={`w-2 h-2 rounded-full ${
                entry.severity === 'critical'
                  ? 'bg-red-500'
                  : entry.severity === 'warning'
                  ? 'bg-yellow-500'
                  : 'bg-blue-500'
              }`}
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium text-white">{entry.module}</span>
              <span className="text-gray-500">·</span>
              <span className="text-gray-400">{entry.action}</span>
              <span className="text-gray-500">·</span>
              <span className="text-gray-500">{entry.entity_type}</span>
            </div>
            <p className="text-sm text-gray-400 truncate">{entry.summary}</p>
            <p className="text-xs text-gray-500 mt-1">
              {new Date(entry.timestamp).toLocaleString()}
            </p>
          </div>
          <Badge
            variant={
              entry.severity === 'critical'
                ? 'error'
                : entry.severity === 'warning'
                ? 'warning'
                : 'default'
            }
            className="text-xs"
          >
            {entry.severity}
          </Badge>
        </div>
      ))}
    </div>
  );
};

const EnterpriseIntegrationPage = () => {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [integrationStatus, setIntegrationStatus] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [auditEntries, setAuditEntries] = useState([]);
  const [eventStats, setEventStats] = useState(null);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, notifs, audit, stats] = await Promise.all([
        EnterpriseService.getIntegrationStatus().catch(() => null),
        EnterpriseService.getNotifications({ limit: 20 }).catch(() => ({ notifications: [], unread_count: 0 })),
        EnterpriseService.getAuditTimeline({ limit: 20 }).catch(() => ({ entries: [], total: 0 })),
        EnterpriseService.getEventStats().catch(() => null),
      ]);
      setIntegrationStatus(status);
      setNotifications(notifs?.notifications || []);
      setUnreadCount(notifs?.unread_count || 0);
      setAuditEntries(audit?.entries || []);
      setEventStats(stats);
    } catch (err) {
      setError(err.message || 'Failed to load integration data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMarkRead = async (notificationId) => {
    try {
      await EnterpriseService.markNotificationRead(notificationId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await EnterpriseService.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    }
  };

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'notifications', label: `Notifications${unreadCount > 0 ? ` (${unreadCount})` : ''}` },
    { id: 'audit', label: 'Audit Trail' },
    { id: 'events', label: 'Event Bus' },
  ];

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
        <div className="max-w-7xl mx-auto">
          <Card className="p-8 text-center">
            <p className="text-red-400 mb-4">⚠️ {error}</p>
            <button
              onClick={loadData}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Retry
            </button>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white">Enterprise Platform</h1>
              <p className="text-gray-400 mt-1">
                Cross-module integration, notifications, audit trail, and event bus
              </p>
            </div>
            <StatusBadge status={integrationStatus?.event_bus?.status || 'unknown'} />
          </div>
        </div>

        {/* Tabs */}
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        {/* Tab Content */}
        <div className="mt-6">
          {activeTab === 'overview' && (
            <div>
              {/* Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <MetricCard
                  label="Events Published"
                  value={eventStats?.total_events_published ?? 0}
                  status="healthy"
                />
                <MetricCard
                  label="Dead Letter Queue"
                  value={eventStats?.dead_letter_count ?? 0}
                  status={eventStats?.dead_letter_count > 0 ? 'warning' : 'healthy'}
                />
                <MetricCard
                  label="Notifications"
                  value={unreadCount}
                  status={unreadCount > 0 ? 'warning' : 'healthy'}
                />
                <MetricCard
                  label="Audit Entries"
                  value={auditEntries.length}
                  status="healthy"
                />
              </div>

              {/* Integration Status Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {integrationStatus && (
                  <>
                    <IntegrationStatusCard
                      title="Event Bus"
                      items={integrationStatus.event_bus || {}}
                    />
                    <IntegrationStatusCard
                      title="Notification Service"
                      items={integrationStatus.notification_service || {}}
                    />
                    <IntegrationStatusCard
                      title="Audit Service"
                      items={integrationStatus.audit_service || {}}
                    />
                  </>
                )}
              </div>

              {/* Recent Audit Timeline */}
              <Card className="mt-6">
                <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>
                <AuditTimeline entries={auditEntries.slice(0, 10)} />
              </Card>
            </div>
          )}

          {activeTab === 'notifications' && (
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">
                  Notifications
                  {unreadCount > 0 && (
                    <span className="ml-2 text-sm text-gray-400">
                      ({unreadCount} unread)
                    </span>
                  )}
                </h3>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-sm text-indigo-400 hover:text-indigo-300"
                  >
                    Mark all as read
                  </button>
                )}
              </div>
              <NotificationPanel
                notifications={notifications}
                onMarkRead={handleMarkRead}
              />
            </Card>
          )}

          {activeTab === 'audit' && (
            <Card>
              <h3 className="text-lg font-semibold text-white mb-4">Audit Trail</h3>
              <AuditTimeline entries={auditEntries} />
            </Card>
          )}

          {activeTab === 'events' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">
                  Event Bus Statistics
                </h3>
                {eventStats && (
                  <div className="space-y-3">
                    <div className="flex justify-between py-2 border-b border-gray-700">
                      <span className="text-gray-400">Total Events Published</span>
                      <span className="text-white font-medium">
                        {eventStats.total_events_published}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-700">
                      <span className="text-gray-400">Dead Letter Queue</span>
                      <span className="text-white font-medium">
                        {eventStats.dead_letter_count}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-700">
                      <span className="text-gray-400">Max Retries</span>
                      <span className="text-white font-medium">
                        {eventStats.max_retries}
                      </span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-gray-400">History Enabled</span>
                      <span className="text-white font-medium">
                        {eventStats.history_enabled ? 'Yes' : 'No'}
                      </span>
                    </div>
                  </div>
                )}
              </Card>

              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">
                  Subscribers
                </h3>
                {eventStats && (
                  <div className="space-y-3">
                    {Object.keys(eventStats.sync_subscribers || {}).length > 0 && (
                      <div>
                        <h4 className="text-sm text-gray-400 mb-2">
                          Sync Subscribers
                        </h4>
                        {Object.entries(eventStats.sync_subscribers).map(
                          ([eventType, count]) => (
                            <div
                              key={eventType}
                              className="flex justify-between py-1 text-sm"
                            >
                              <span className="text-gray-300">{eventType}</span>
                              <span className="text-white">{count}</span>
                            </div>
                          )
                        )}
                      </div>
                    )}
                    {Object.keys(eventStats.async_subscribers || {}).length === 0 &&
                      Object.keys(eventStats.sync_subscribers || {}).length ===
                        0 && (
                        <p className="text-gray-500 text-sm">
                          No subscribers registered yet.
                        </p>
                      )}
                  </div>
                )}
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EnterpriseIntegrationPage;

