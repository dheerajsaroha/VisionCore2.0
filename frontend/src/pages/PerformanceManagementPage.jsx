import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Trophy, Target, BarChart3, FileText, MessageSquare, AlertTriangle,
  TrendingUp, RefreshCw, Plus, CheckCircle2, AlertCircle, Layers, Star, Activity
} from 'lucide-react';
import { performanceService } from '../services/performanceService';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import '../components/ui/Spinner';
import { formatDate } from '../lib/utils';

export default function PerformanceManagementPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [analytics, setAnalytics] = useState(null);
  const [goals, setGoals] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [feedbackList, setFeedbackList] = useState([]);
  const [competencies, setCompetencies] = useState([]);
  const [pips, setPIPs] = useState([]);
  const [promotions, setPromotions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');


  // Forms
  const [newGoal, setNewGoal] = useState({ title: '', description: '', goal_framework: 'smart', target_value: 100, current_value: 0, unit: '%' });
  const [newFeedback, setNewFeedback] = useState({ receiver_user_id: 1, content: '', feedback_type: 'peer', is_anonymous: false, rating: 5 });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [analyticsRes, goalRes, assignRes, reviewRes, fbRes, compRes, pipRes, promoRes] = await Promise.all([
        performanceService.getAnalytics(),
        performanceService.getGoals(),
        performanceService.getKPIAssignments(),
        performanceService.getReviews(),
        performanceService.getFeedback(),
        performanceService.getCompetencies(),
        performanceService.getPIPs(),
        performanceService.getPromotions()
      ]);

      setAnalytics(analyticsRes.data);
      setGoals(goalRes.data || []);
      setAssignments(assignRes.data || []);
      setReviews(reviewRes.data || []);
      setFeedbackList(fbRes.data || []);
      setCompetencies(compRes.data || []);
      setPIPs(pipRes.data || []);
      setPromotions(promoRes.data || []);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load performance management data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateGoal = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await performanceService.createGoal({
        ...newGoal,
        target_value: parseFloat(newGoal.target_value),
        current_value: parseFloat(newGoal.current_value)
      });
      setActionSuccess('Goal created successfully!');
      setNewGoal({ title: '', description: '', goal_framework: 'smart', target_value: 100, current_value: 0, unit: '%' });
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create goal');
    }
  };

  const handleSendFeedback = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    try {
      await performanceService.submitFeedback({
        ...newFeedback,
        receiver_user_id: parseInt(newFeedback.receiver_user_id, 10),
        rating: parseFloat(newFeedback.rating)
      });
      setActionSuccess('Feedback submitted successfully!');
      setNewFeedback({ receiver_user_id: 1, content: '', feedback_type: 'peer', is_anonymous: false, rating: 5 });
      fetchData();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to submit feedback');
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="space-y-8 p-1 sm:p-2">
      {/* ── HEADER BANNER ── */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-purple-950 via-slate-900 to-indigo-950 p-8 text-white shadow-2xl border border-purple-500/20">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 rounded-full bg-purple-500/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="p-3.5 rounded-2xl bg-purple-500/20 border border-purple-400/30 backdrop-blur-md">
              <Trophy className="h-8 w-8 text-purple-300" />
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-transparent">
                Performance Management
              </h1>
              <p className="text-sm text-purple-200/80 mt-0.5">
                Sprint 4 · Cycles, OKRs, Weighted KPIs, 360° Reviews, Ratings &amp; PIP Engine
              </p>
            </div>
          </div>
          <Button onClick={fetchData} variant="secondary" className="bg-white/10 hover:bg-white/20 text-white border-white/10">
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-8 flex items-center gap-1 border-b border-purple-500/20 pb-0 overflow-x-auto">
          {[
            { id: 'dashboard', label: 'Dashboard', icon: Activity },
            { id: 'goals', label: 'Goals & OKRs', icon: Target },
            { id: 'kpis', label: 'KPIs & Scoring', icon: BarChart3 },
            { id: 'reviews', label: 'Reviews', icon: FileText },
            { id: 'feedback', label: '360° Feedback', icon: MessageSquare },
            { id: 'competencies', label: 'Competencies', icon: Layers },
            { id: 'pips', label: 'PIPs', icon: AlertTriangle },
            { id: 'promotions', label: 'Promotions', icon: TrendingUp },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 font-semibold text-sm transition-all border-b-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-purple-400 text-purple-300 bg-white/5 rounded-t-xl'
                    : 'border-transparent text-purple-200/60 hover:text-white hover:bg-white/5 rounded-t-xl'
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
                <p className="text-xs font-bold text-slate-400 uppercase">Avg Rating</p>
                <Star className="h-5 w-5 text-amber-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{analytics?.avg_performance_rating || 3.5} <span className="text-sm font-normal text-slate-400">/ 5.0</span></p>
              <p className="text-xs text-slate-500 mt-1">Org-wide calibrated mean</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Goal Completion</p>
                <Target className="h-5 w-5 text-purple-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{analytics?.goal_completion_pct || 0}%</p>
              <p className="text-xs text-slate-500 mt-1">Average OKR progress</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Review Completion</p>
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{analytics?.review_completion_pct || 0}%</p>
              <p className="text-xs text-slate-500 mt-1">{analytics?.completed_reviews_count || 0} of {analytics?.total_employees_in_cycle || 0} done</p>
            </Card>

            <Card className="border-slate-800 bg-slate-900/90 p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-400 uppercase">Active PIPs</p>
                <AlertTriangle className="h-5 w-5 text-rose-400" />
              </div>
              <p className="text-3xl font-black text-white mt-2">{analytics?.active_pips_count || 0}</p>
              <p className="text-xs text-slate-500 mt-1">Under improvement plan</p>
            </Card>
          </div>

          {/* Bell Curve Visualization */}
          <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-2xl">
            <CardHeader className="p-0 pb-6 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-purple-400" /> Performance Bell Curve Distribution
              </CardTitle>
              <CardDescription className="text-slate-400">Rating spread across the organization</CardDescription>
            </CardHeader>
            <CardContent className="p-0 pt-6 space-y-4">
              {(analytics?.bell_curve || []).map((b, idx) => (
                <div key={idx} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300">{b.rating_label}</span>
                    <span className="text-purple-400">{b.count} employees ({b.pct}%)</span>
                  </div>
                  <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-purple-500 to-indigo-500 h-full transition-all duration-500"
                      style={{ width: `${Math.max(5, b.pct)}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 2: GOALS & OKRS ── */}
      {activeTab === 'goals' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Card className="lg:col-span-1 border border-slate-800 bg-slate-900/90 p-6 shadow-xl h-fit">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <Plus className="h-5 w-5 text-purple-400" /> Create Goal / OKR
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4">
              <form onSubmit={handleCreateGoal} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300">Goal Title</label>
                  <input
                    type="text"
                    value={newGoal.title}
                    onChange={(e) => setNewGoal({ ...newGoal, title: e.target.value })}
                    placeholder="e.g. Reduce API latency by 30%"
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">Framework</label>
                  <select
                    value={newGoal.goal_framework}
                    onChange={(e) => setNewGoal({ ...newGoal, goal_framework: e.target.value })}
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                  >
                    <option value="okr">OKR</option>
                    <option value="smart">SMART Goal</option>
                    <option value="personal">Personal Goal</option>
                    <option value="stretch">Stretch Goal</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-300">Target Value</label>
                    <input
                      type="number"
                      value={newGoal.target_value}
                      onChange={(e) => setNewGoal({ ...newGoal, target_value: e.target.value })}
                      className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300">Unit</label>
                    <input
                      type="text"
                      value={newGoal.unit}
                      onChange={(e) => setNewGoal({ ...newGoal, unit: e.target.value })}
                      className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                    />
                  </div>
                </div>
                <Button type="submit" className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl">
                  Save Goal
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2 border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white">Active Goals Ledger</CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4 divide-y divide-slate-800">
              {goals.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No active goals found. Create your first goal!</p>
              ) : (
                goals.map((g) => (
                  <div key={g.id} className="py-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-white text-sm flex items-center gap-2">
                        {g.title}
                        <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/30 text-xs uppercase">{g.goal_framework}</Badge>
                      </h3>
                      <span className="font-black text-purple-400 text-sm">{g.completion_pct}%</span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div className="bg-gradient-to-r from-purple-500 to-indigo-500 h-full" style={{ width: `${g.completion_pct}%` }} />
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 3: KPIS & SCORING ── */}
      {activeTab === 'kpis' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white">Assigned Key Performance Indicators</CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            <div className="divide-y divide-slate-800">
              {assignments.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No KPIs assigned for current cycle.</p>
              ) : (
                assignments.map((a) => (
                  <div key={a.id} className="py-4 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-sm">{a.kpi_name}</p>
                      <p className="text-xs text-slate-400">Target: {a.target_value} | Weight: {a.weight}x</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-black text-purple-400">{a.score ? `${a.score} / 5.0` : 'Pending'}</p>
                      <p className="text-xs text-slate-500">Actual: {a.actual_value ?? '—'}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TAB 4: REVIEWS ── */}
      {activeTab === 'reviews' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white">Performance Reviews Ledger</CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            <div className="divide-y divide-slate-800">
              {reviews.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No review cycles active or assigned.</p>
              ) : (
                reviews.map((r) => (
                  <div key={r.id} className="py-4 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-sm">Reviewee: {r.reviewee_name || `User #${r.reviewee_user_id}`}</p>
                      <p className="text-xs text-slate-400">Type: {r.review_type} | Reviewer: {r.reviewer_name || 'Self/Assigned'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge className={r.status === 'submitted' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}>
                        {r.status}
                      </Badge>
                      <span className="font-bold text-white text-sm">{r.overall_score ? `${r.overall_score} / 5.0` : '—'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TAB 5: 360° FEEDBACK ── */}
      {activeTab === 'feedback' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Card className="lg:col-span-1 border border-slate-800 bg-slate-900/90 p-6 shadow-xl h-fit">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-purple-400" /> Send Feedback
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4">
              <form onSubmit={handleSendFeedback} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300">Feedback Type</label>
                  <select
                    value={newFeedback.feedback_type}
                    onChange={(e) => setNewFeedback({ ...newFeedback, feedback_type: e.target.value })}
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                  >
                    <option value="peer">Peer Feedback</option>
                    <option value="manager">Manager Feedback</option>
                    <option value="360">360° Feedback</option>
                    <option value="anonymous">Anonymous Feedback</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">Content</label>
                  <textarea
                    rows={3}
                    value={newFeedback.content}
                    onChange={(e) => setNewFeedback({ ...newFeedback, content: e.target.value })}
                    placeholder="Provide constructive feedback..."
                    className="w-full rounded-xl bg-slate-800 border border-slate-700 p-2.5 text-white text-sm focus:outline-none"
                    required
                  />
                </div>
                <Button type="submit" className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl">
                  Submit Feedback
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2 border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
            <CardHeader className="p-0 pb-4 border-b border-slate-800">
              <CardTitle className="text-lg font-bold text-white">Received Feedback Log</CardTitle>
            </CardHeader>
            <CardContent className="p-0 pt-4 divide-y divide-slate-800">
              {feedbackList.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No feedback records found.</p>
              ) : (
                feedbackList.map((f) => (
                  <div key={f.id} className="py-4 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-purple-400">From: {f.giver_name}</span>
                      <span className="text-xs text-slate-500">{formatDate(f.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-200">{f.content}</p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TAB 6: COMPETENCIES ── */}
      {activeTab === 'competencies' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white">Configured Competency Framework</CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {competencies.map((c) => (
                <div key={c.id} className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-sm">{c.name}</span>
                    <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/30 text-xs uppercase">{c.category}</Badge>
                  </div>
                  <p className="text-xs text-slate-400">{c.description || 'No description provided.'}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TAB 7: PIPS ── */}
      {activeTab === 'pips' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-rose-400" /> Active Performance Improvement Plans
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            <div className="divide-y divide-slate-800">
              {pips.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No active PIPs in progress.</p>
              ) : (
                pips.map((p) => (
                  <div key={p.id} className="py-4 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-sm">{p.title} ({p.user_name})</p>
                      <p className="text-xs text-slate-400">Reason: {p.reason}</p>
                    </div>
                    <Badge className="bg-rose-500/20 text-rose-300 border-rose-500/30">{p.status}</Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TAB 8: PROMOTIONS ── */}
      {activeTab === 'promotions' && (
        <Card className="border border-slate-800 bg-slate-900/90 p-6 shadow-xl">
          <CardHeader className="p-0 pb-4 border-b border-slate-800">
            <CardTitle className="text-lg font-bold text-white flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-emerald-400" /> Promotion Readiness Center
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 pt-4">
            <div className="divide-y divide-slate-800">
              {promotions.length === 0 ? (
                <p className="text-slate-400 py-8 text-center text-sm">No pending promotion recommendations.</p>
              ) : (
                promotions.map((pr) => (
                  <div key={pr.id} className="py-4 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-sm">{pr.user_name} → {pr.proposed_role || 'Senior Position'}</p>
                      <p className="text-xs text-slate-400">Recommender: {pr.recommender_name} | Salary Increase: +{pr.proposed_salary_increase_pct || 0}%</p>
                    </div>
                    <Badge className={pr.status === 'approved' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}>
                      {pr.status}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}
