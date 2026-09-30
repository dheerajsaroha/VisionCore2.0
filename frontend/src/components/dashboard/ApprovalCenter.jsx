/**
 * ApprovalCenter.jsx
 * Centralized actionable enterprise approval center.
 * Aggregates pending actions across:
 * - Leave Approvals
 * - Expense Claims
 * - Asset Requests
 * - Performance Reviews
 * - Workflow Approvals
 * Connects directly to backend workflow actions.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  CheckSquare, CheckCircle, XCircle, Clock, 
  ArrowRight, DollarSign, Palmtree, Package, 
  FileText, Award, ShieldCheck 
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { ApprovalItem } from './ApprovalItem';

export function ApprovalCenter({ items = [], onApprove, onReject, loading, canAction = true }) {
  const navigate = useNavigate();
  const [processingId, setProcessingId] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  if (loading) {
    return (
      <Card className="border-slate-800/80 bg-slate-900/60 p-6">
        <Skeleton className="h-6 w-48 bg-slate-800 mb-4" />
        <Skeleton className="h-48 bg-slate-800/60 rounded-xl" />
      </Card>
    );
  }

  // Calculate categorized counts for summary breakdown
  const leaveCount = items.filter((i) => i.item_type === 'leave').length;
  const claimCount = items.filter((i) => i.item_type === 'reimbursement').length;
  const assetCount = items.filter((i) => (i.category || '').toLowerCase().includes('asset')).length;
  const perfCount = items.filter((i) => i.item_type === 'performance').length;
  const corrCount = items.filter((i) => i.item_type === 'correction').length;

  const handleAction = async (item, action) => {
    setProcessingId(item.id);
    try {
      if (action === 'approve' && onApprove) {
        await onApprove(item);
      } else if (action === 'reject' && onReject) {
        await onReject(item);
      }
      setToastMessage({ type: 'success', text: `${item.title} ${action}d successfully.` });
    } catch (err) {
      setToastMessage({ type: 'error', text: 'Failed to process request. Please try again.' });
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <>
      <Card className="border-slate-800/80 bg-slate-900/60 shadow-xl overflow-hidden h-full flex flex-col justify-between">
        <div>
          <CardHeader className="border-b border-slate-800/60 pb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckSquare className="h-5 w-5 text-indigo-400" />
                <CardTitle className="text-slate-100 text-base">Approval Center</CardTitle>
                <Badge variant="purple" className="font-bold text-xs px-2 py-0.5">
                  {items.length} Pending
                </Badge>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/dashboard/approval-workflows')}
                className="text-xs text-indigo-400 hover:text-indigo-300 p-0"
              >
                Review All
                <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </CardHeader>

          {/* Pending Actions Summary Pills */}
          {items.length > 0 && (
            <div className="px-5 pt-3.5 pb-1 flex items-center flex-wrap gap-2 text-[11px] font-medium text-slate-400">
              <span className="text-slate-500 uppercase font-bold text-[10px]">Queue:</span>
              {leaveCount > 0 && (
                <span className="px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {leaveCount} Leave Request{leaveCount > 1 ? 's' : ''}
                </span>
              )}
              {claimCount > 0 && (
                <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {claimCount} Expense Claim{claimCount > 1 ? 's' : ''}
                </span>
              )}
              {assetCount > 0 && (
                <span className="px-2 py-0.5 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  {assetCount} Asset Request{assetCount > 1 ? 's' : ''}
                </span>
              )}
              {perfCount > 0 && (
                <span className="px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {perfCount} Performance Review{perfCount > 1 ? 's' : ''}
                </span>
              )}
              {corrCount > 0 && (
                <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {corrCount} Correction{corrCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}

          <CardContent className="p-4 space-y-3">
            {items.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  title="All Caught Up!"
                  description="No pending approvals require your sign-off right now."
                  icon={CheckCircle}
                />
              </div>
            ) : (
              <AnimatePresence>
                {items.slice(0, 5).map((item) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <ApprovalItem
                      item={item}
                      canAction={canAction}
                      processing={processingId === item.id}
                      onApprove={(it) => handleAction(it, 'approve')}
                      onReject={(it) => handleAction(it, 'reject')}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </CardContent>
        </div>
      </Card>

      {toastMessage && (
        <div className={`mt-3 p-3 rounded-xl border text-xs font-medium flex items-center justify-between ${
          toastMessage.type === 'success' 
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
        }`}>
          <span>{toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="text-slate-400 hover:text-slate-200 ml-2">×</button>
        </div>
      )}
    </>
  );
}
export default ApprovalCenter;
