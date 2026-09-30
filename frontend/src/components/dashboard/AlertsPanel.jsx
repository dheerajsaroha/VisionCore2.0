/**
 * AlertsPanel.jsx
 * Displays meaningful operational and compliance alerts:
 * - Late employee arrivals
 * - Expiring certifications
 * - Pending performance reviews
 * - Overdue policy acknowledgments
 * - Asset maintenance tasks due
 * - Open support tickets
 * - Upcoming scheduled leave
 * - Pending shift swap conflicts
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  AlertTriangle, ShieldAlert, Clock, 
  FileCheck, Ticket, UserCheck, ArrowRight, CheckCircle2 
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { AlertItem } from './AlertItem';

export function AlertsPanel({ alerts = [], loading }) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <Skeleton className="h-6 w-48 bg-slate-800 mb-4" />
        <Skeleton className="h-40 bg-slate-800/60 rounded-xl" />
      </Card>
    );
  }

  const highSeverityCount = alerts.filter((a) => a.severity === 'high').length;

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden h-full flex flex-col justify-between">
      <div>
        <CardHeader className="border-b border-slate-800/60 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              <CardTitle className="text-slate-100 text-base">Workforce Operational Alerts</CardTitle>
            </div>
            <div className="flex items-center gap-1.5">
              {highSeverityCount > 0 && (
                <Badge variant="danger" className="text-xs px-2 py-0.5">
                  {highSeverityCount} High Priority
                </Badge>
              )}
              <Badge variant="warning" className="text-xs px-2 py-0.5">
                {alerts.length} Active
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 space-y-2.5">
          {alerts.length === 0 ? (
            <div className="py-8">
              <EmptyState
                title="All Systems Nominal"
                description="Zero anomalies or compliance exceptions detected in this tenant."
                icon={CheckCircle2}
              />
            </div>
          ) : (
            alerts.slice(0, 5).map((alt) => (
              <AlertItem
                key={alt.id}
                alert={alt}
                onClick={(item) => item.link && navigate(item.link)}
              />
            ))
          )}
        </CardContent>
      </div>
    </Card>
  );
}
export default AlertsPanel;
