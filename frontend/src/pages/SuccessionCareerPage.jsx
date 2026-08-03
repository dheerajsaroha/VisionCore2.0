import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart2, Users, Target, TrendingUp, AlertTriangle, Heart, RefreshCw,
  Star, MapPin, GitBranch, ClipboardList, Shield, Award
} from 'lucide-react';
import { successionService } from '../services/successionService';

const NINE_BOX_LABELS = {
  '3-3': { label: 'Star', color: 'bg-emerald-500', textColor: 'text-emerald-400' },
  '3-2': { label: 'High Professional', color: 'bg-teal-500', textColor: 'text-teal-400' },
  '3-1': { label: 'Solid Pro', color: 'bg-cyan-500', textColor: 'text-cyan-400' },
  '2-3': { label: 'High Potential', color: 'bg-blue-500', textColor: 'text-blue-400' },
  '2-2': { label: 'Core Player', color: 'bg-indigo-500', textColor: 'text-indigo-400' },
  '2-1': { label: 'Effective', color: 'bg-violet-500', textColor: 'text-violet-400' },
  '1-3': { label: 'Enigma', color: 'bg-amber-500', textColor: 'text-amber-400' },
  '1-2': { label: 'Dilemma', color: 'bg-orange-500', textColor: 'text-orange-400' },
  '1-1': { label: 'Underperformer', color: 'bg-rose-500', textColor: 'text-rose-400' },
};

const RISK_COLORS = {
  low: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30',
  medium: 'text-amber-400 bg-amber-500/20 border-amber-500/30',
  high: 'text-rose-400 bg-rose-500/20 border-rose-500/30',
  critical: 'text-red-300 bg-red-500/30 border-red-400/50',
};

export default function SuccessionCareerPage() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState(null);
  const [keyPositions, setKeyPositions] = useState([]);
  const [plans, setPlans] = useState([]);
  const [nineBox, setNineBox] = useState([]);
  const [careerPaths, setCareerPaths] = useState([]);
  const [idps, setIDPs] = useState([]);
  const [flightRisks, setFlightRisks] = useState([]);
  const [mentorships, setMentorships] = useState([]);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [an, kp, pl, nb, cp, idp, fr, mt] = await Promise.all([
        successionService.getAnalytics(),
        successionService.getKeyPositions(),
        successionService.getSuccessionPlans(),
        successionService.getNineBoxGrid(),
        successionService.getCareerPaths(),
        successionService.getIDPs(),
        successionService.getFlightRisks(),
        successionService.getMentorships(),
      ]);
      setAnalytics(an.data);
      setKeyPositions(kp.data);
      setPlans(pl.data);
      setNineBox(nb.data);
      setCareerPaths(cp.data);
      setIDPs(idp.data);
      setFlightRisks(fr.data);
      setMentorships(mt.data);
    } catch (err) {
      console.error('Error loading Succession data:', err);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'dashboard', label: 'Executive Overview', icon: BarChart2 },
    { id: 'key-positions', label: 'Key Positions', icon: Shield },
    { id: 'bench', label: 'Succession Bench', icon: Users },
    { id: 'nine-box', label: '9-Box Matrix', icon: Target },
    { id: 'career', label: 'Career Pathways', icon: GitBranch },
    { id: 'idp', label: 'Dev Plans (IDP)', icon: ClipboardList },
    { id: 'flight-risk', label: 'Flight Risk', icon: AlertTriangle },
    { id: 'mentorship', label: 'Mentorship Network', icon: Heart },
  ];

  const statCards = [
    { label: 'Critical Positions', value: analytics?.critical_positions_count ?? 0, color: 'from-rose-500 to-pink-600', suffix: '' },
    { label: 'Readiness %', value: analytics?.succession_readiness_pct ?? 0, color: 'from-emerald-500 to-teal-600', suffix: '%' },
    { label: '9-Box Stars', value: analytics?.nine_box_stars_count ?? 0, color: 'from-amber-500 to-yellow-500', suffix: '' },
    { label: 'Active IDPs', value: analytics?.active_idps_count ?? 0, color: 'from-blue-500 to-indigo-600', suffix: '' },
    { label: 'High Flight Risk', value: analytics?.high_flight_risk_count ?? 0, color: 'from-orange-500 to-red-500', suffix: '' },
    { label: 'Active Mentorships', value: analytics?.active_mentorships_count ?? 0, color: 'from-purple-500 to-fuchsia-600', suffix: '' },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-rose-400 via-amber-300 to-emerald-400 bg-clip-text text-transparent">
            Succession Planning & Career Pathing Engine
          </h1>
          <p className="text-sm text-slate-400">Enterprise Talent Bench, 9-Box Matrix, IDPs, Flight Risk & Mentorship Network</p>
        </div>
        <button onClick={fetchAll} className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto gap-2 border-b border-slate-800 pb-2">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition ${activeTab === id ? 'bg-rose-600/30 text-rose-400 border border-rose-500/50' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}>
            <Icon className="w-4 h-4" />{label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-500">Loading Succession & Career Engine...</div>
      ) : (
        <div className="space-y-6">

          {/* TAB 1: EXECUTIVE OVERVIEW */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                {statCards.map((card, i) => (
                  <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className={`text-2xl font-bold bg-gradient-to-r ${card.color} bg-clip-text text-transparent`}>
                      {card.value}{card.suffix}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">{card.label}</div>
                  </div>
                ))}
              </div>

              {/* 9-Box Distribution Preview */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                  <h3 className="text-lg font-semibold text-white">9-Box Talent Distribution</h3>
                  <div className="space-y-2">
                    {analytics?.nine_box_distribution && Object.entries(analytics.nine_box_distribution).map(([cat, cnt]) => (
                      <div key={cat} className="flex justify-between items-center py-1.5 border-b border-slate-700/30">
                        <span className="text-sm text-slate-300">{cat}</span>
                        <span className="text-sm font-bold text-amber-400">{cnt}</span>
                      </div>
                    ))}
                    {(!analytics?.nine_box_distribution || Object.keys(analytics.nine_box_distribution).length === 0) && (
                      <p className="text-slate-500 text-sm">No 9-box evaluations yet.</p>
                    )}
                  </div>
                </div>

                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                  <h3 className="text-lg font-semibold text-white">Critical Position Overview</h3>
                  <div className="space-y-3">
                    {keyPositions.slice(0, 4).map(kp => (
                      <div key={kp.id} className="p-3 bg-slate-900/50 rounded-lg border border-slate-800 flex justify-between items-center">
                        <div>
                          <div className="font-medium text-white text-sm">{kp.title}</div>
                          <div className="text-xs text-slate-400">Impact: {kp.impact_rating}/5</div>
                        </div>
                        <span className={`text-xs px-2 py-1 rounded border font-medium ${RISK_COLORS[kp.vacancy_risk_level] || 'text-slate-400'}`}>
                          {kp.vacancy_risk_level.toUpperCase()} RISK
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: KEY POSITIONS */}
          {activeTab === 'key-positions' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Critical Position Registry</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {keyPositions.map(kp => (
                  <div key={kp.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex justify-between items-start">
                      <h4 className="font-semibold text-white">{kp.title}</h4>
                      <span className={`text-xs px-2.5 py-1 rounded border font-medium ${RISK_COLORS[kp.criticality_level] || 'text-slate-400'}`}>
                        {kp.criticality_level.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 space-y-1">
                      <div>Department: {kp.department_name || 'Cross-functional'}</div>
                      <div>Incumbent: {kp.incumbent_name || 'Vacant'}</div>
                      <div>Impact Rating: <span className="text-amber-400 font-semibold">{kp.impact_rating}/5.0</span></div>
                    </div>
                    <div className="flex items-center gap-2 pt-2 border-t border-slate-700/40">
                      <span className="text-xs text-slate-400">Vacancy Risk:</span>
                      <span className={`text-xs px-2 py-0.5 rounded border ${RISK_COLORS[kp.vacancy_risk_level]}`}>
                        {kp.vacancy_risk_level.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: SUCCESSION BENCH */}
          {activeTab === 'bench' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Succession Bench — Nominated Talent</h3>
              <div className="space-y-4">
                {plans.map(plan => (
                  <div key={plan.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex justify-between items-center">
                      <h4 className="font-semibold text-white">{plan.key_position_title}</h4>
                      <span className="text-xs text-slate-400">Fill Target: {plan.target_fill_timeline_months} months</span>
                    </div>
                    <div className="space-y-2">
                      {plan.candidates?.length > 0 ? plan.candidates.map(c => (
                        <div key={c.id} className="flex justify-between items-center p-2.5 bg-slate-900/50 rounded-lg border border-slate-800">
                          <div>
                            <span className="text-sm font-medium text-slate-200">{c.candidate_name}</span>
                            {c.emergency_backup && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">Emergency Backup</span>}
                          </div>
                          <span className="text-xs px-2.5 py-1 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 font-medium">
                            {c.readiness_rating.replace(/_/g, ' ').toUpperCase()}
                          </span>
                        </div>
                      )) : (
                        <p className="text-xs text-slate-500 py-2">No candidates nominated yet.</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: 9-BOX MATRIX */}
          {activeTab === 'nine-box' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">9-Box Talent Matrix — Performance vs Potential</h3>
              <div className="grid grid-cols-3 gap-2" style={{ direction: 'ltr' }}>
                {[3, 2, 1].map(perf =>
                  [1, 2, 3].map(pot => {
                    const key = `${perf}-${pot}`;
                    const meta = NINE_BOX_LABELS[key];
                    const employees = nineBox.filter(e => e.performance_rating === perf && e.potential_rating === pot);
                    return (
                      <div key={key} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-3 min-h-[90px] flex flex-col">
                        <div className={`text-xs font-semibold mb-1 ${meta?.textColor}`}>{meta?.label}</div>
                        <div className={`text-xs text-slate-500 mb-2`}>P{perf}/Pot{pot}</div>
                        <div className="flex flex-wrap gap-1">
                          {employees.map(e => (
                            <span key={e.id} className="text-xs px-1.5 py-0.5 bg-slate-700 rounded text-slate-300">{e.user_name?.split(' ')[0]}</span>
                          ))}
                          {employees.length === 0 && <span className="text-xs text-slate-600">—</span>}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              <p className="text-xs text-slate-500">Columns: Low → High Potential | Rows: High → Low Performance</p>
            </div>
          )}

          {/* TAB 5: CAREER PATHWAYS */}
          {activeTab === 'career' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Career Ladders & Progression Paths</h3>
              <div className="space-y-6">
                {careerPaths.map(path => (
                  <div key={path.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-4">
                    <div>
                      <h4 className="font-semibold text-white text-base">{path.title}</h4>
                      <p className="text-xs text-slate-400 mt-1">{path.description}</p>
                    </div>
                    <div className="flex overflow-x-auto gap-3 pb-2">
                      {path.levels?.map((lvl, i) => (
                        <div key={lvl.id} className="flex-shrink-0 bg-slate-900/60 border border-slate-700 rounded-lg p-3 w-44 space-y-1.5">
                          <div className="text-xs text-slate-500">Level {lvl.level_number}</div>
                          <div className="text-sm font-semibold text-white">{lvl.level_title}</div>
                          <div className="text-xs text-slate-400">{lvl.min_experience_years}+ yrs</div>
                          <div className="text-xs text-emerald-400">${(lvl.target_salary_min / 1000).toFixed(0)}k–${(lvl.target_salary_max / 1000).toFixed(0)}k</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 6: IDPs */}
          {activeTab === 'idp' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Individual Development Plans</h3>
              <div className="space-y-4">
                {idps.map(idp => (
                  <div key={idp.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-4">
                    <div className="flex justify-between items-center">
                      <div>
                        <h4 className="font-semibold text-white">{idp.user_name}</h4>
                        <p className="text-xs text-slate-400">Target: {idp.target_position_title || 'General Development'}</p>
                      </div>
                      <span className={`text-xs px-3 py-1 rounded-lg font-medium ${idp.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'}`}>
                        {idp.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {idp.goals?.map(goal => (
                        <div key={goal.id} className="flex items-center justify-between p-2.5 bg-slate-900/50 rounded-lg border border-slate-800">
                          <span className="text-sm text-slate-300">{goal.title}</span>
                          <div className="flex items-center gap-3">
                            <div className="w-20 bg-slate-700 h-2 rounded-full overflow-hidden">
                              <div className="bg-emerald-500 h-full" style={{ width: `${goal.completion_pct}%` }} />
                            </div>
                            <span className="text-xs font-semibold text-emerald-400 w-8 text-right">{goal.completion_pct}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 7: FLIGHT RISK */}
          {activeTab === 'flight-risk' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Talent Flight Risk Monitor</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {flightRisks.map(risk => (
                  <div key={risk.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex justify-between items-center">
                      <h4 className="font-semibold text-white">{risk.user_name}</h4>
                      <span className={`text-xs px-3 py-1 rounded border font-bold ${RISK_COLORS[risk.risk_score]}`}>
                        {risk.risk_score.toUpperCase()} RISK
                      </span>
                    </div>
                    {risk.retention_strategy && (
                      <p className="text-xs text-slate-400 bg-slate-900/50 rounded-lg p-2 border border-slate-800">
                        <span className="text-slate-300 font-medium">Retention Plan: </span>{risk.retention_strategy}
                      </p>
                    )}
                    <div className="text-xs text-slate-500">
                      Assessed: {new Date(risk.assessed_at).toLocaleDateString()}
                    </div>
                  </div>
                ))}
                {flightRisks.length === 0 && <p className="text-slate-500 col-span-2">No flight risk assessments logged.</p>}
              </div>
            </div>
          )}

          {/* TAB 8: MENTORSHIP */}
          {activeTab === 'mentorship' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Executive Mentorship Network</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {mentorships.map(pair => (
                  <div key={pair.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="text-center">
                        <div className="w-9 h-9 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center text-purple-400 font-bold text-sm">M</div>
                        <div className="text-xs text-slate-400 mt-1">{pair.mentor_name}</div>
                      </div>
                      <Heart className="w-4 h-4 text-rose-400 flex-shrink-0" />
                      <div className="text-center">
                        <div className="w-9 h-9 rounded-full bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400 font-bold text-sm">E</div>
                        <div className="text-xs text-slate-400 mt-1">{pair.mentee_name}</div>
                      </div>
                      <div className="ml-auto">
                        <span className={`text-xs px-2.5 py-1 rounded font-medium ${pair.status === 'active' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-400'}`}>
                          {pair.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    {pair.focus_areas && (
                      <p className="text-xs text-slate-400 bg-slate-900/40 p-2 rounded border border-slate-800">
                        Focus: {pair.focus_areas}
                      </p>
                    )}
                  </div>
                ))}
                {mentorships.length === 0 && <p className="text-slate-500">No mentorship pairings yet.</p>}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
