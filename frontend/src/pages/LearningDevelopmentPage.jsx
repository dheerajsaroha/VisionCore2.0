import React, { useState, useEffect } from 'react';
import {
  BookOpen, Award, CheckCircle, Video, Award as CertIcon, DollarSign,
  TrendingUp, Users, Plus, Play, RefreshCw, BarChart2, Layers, Search
} from 'lucide-react';
import { learningService } from '../services/learningService';
import { useAuthStore } from '../store/authStore';
import { usePermission } from '../hooks/usePermission';

export default function LearningDevelopmentPage() {
  const { user } = useAuthStore();
  const { hasPermission } = usePermission();
  
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState(null);
  const [courses, setCourses] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [quizzes, setQuizzes] = useState([]);
  const [skills, setSkills] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [budgets, setBudgets] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);

    // Analytics and budget are organization-wide and need `learning.view_org`,
    // which an ordinary employee deliberately does not hold. Requesting them
    // anyway is not merely wasteful: a 403 from either rejected the shared
    // `Promise.all` below, so the courses, sessions, quizzes, skills and
    // certificates the employee *is* entitled to never rendered at all.
    const canViewOrg = hasPermission('learning.view_org');

    const [anRes, cRes, eRes, sRes, qRes, skRes, certRes, bRes] = await Promise.allSettled([
      canViewOrg ? learningService.getAnalytics() : Promise.resolve({ data: null }),
      learningService.getCourses(),
      learningService.getEnrollments(),
      learningService.getSessions(),
      learningService.getQuizzes(),
      learningService.getSkills(),
      learningService.getCertificates(),
      canViewOrg ? learningService.getBudget() : Promise.resolve({ data: null }),
    ]);

    // A single failed call must not blank the sections that did succeed.
    const ok = (r, fallback) => (r.status === 'fulfilled' ? r.value?.data ?? fallback : fallback);

    setAnalytics(ok(anRes, null));
    setCourses(ok(cRes, []));
    setEnrollments(ok(eRes, []));
    setSessions(ok(sRes, []));
    setQuizzes(ok(qRes, []));
    setSkills(ok(skRes, []));
    setCertificates(ok(certRes, []));
    setBudgets(ok(bRes, []));

    const failed = [anRes, cRes, eRes, sRes, qRes, skRes, certRes, bRes].filter(
      (r) => r.status === 'rejected'
    );
    if (failed.length) {
      console.error('Some L&D data failed to load:', failed.map((f) => f.reason?.message));
    }
    setLoading(false);
  };

  // Filter tabs based on user permissions
  const allTabs = [
    // The overview is built entirely from organization-wide analytics, so it is
    // gated on `learning.view_org`. An employee landing on it saw a page of
    // zeros, which reads as a broken feature rather than a lack of entitlement.
    { id: 'dashboard', label: 'Overview Dashboard', icon: BarChart2, permission: 'learning.view_org' },
    { id: 'catalog', label: 'Course Catalog', icon: BookOpen, permission: 'learning.view' },
    { id: 'my-learning', label: 'My Learning', icon: Layers, permission: 'learning.view' },
    { id: 'sessions', label: 'Training Sessions', icon: Video, permission: 'learning.view' },
    { id: 'assessments', label: 'Assessments & Quizzes', icon: CheckCircle, permission: 'learning.view' },
    { id: 'skills', label: 'Skill Matrix', icon: TrendingUp, permission: 'learning.view' },
    { id: 'certificates', label: 'Certifications', icon: CertIcon, permission: 'learning.view' },
    { id: 'budget', label: 'Budget & Spend', icon: DollarSign, permission: 'learning.view_org' }
  ];

  const tabs = allTabs.filter(tab => hasPermission(tab.permission));

  // `activeTab` defaults to the overview, which an employee cannot see. Without
  // this the tab strip renders with nothing selected and no content at all.
  useEffect(() => {
    if (tabs.length && !tabs.some(t => t.id === activeTab)) {
      setActiveTab(tabs[0].id);
    }
  }, [tabs, activeTab]);

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent">
            Learning & Development Center
          </h1>
          <p className="text-sm text-slate-400">
            Enterprise Training Management, Competency Skill Matrix & Certification Engine
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto gap-2 border-b border-slate-800 pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition ${
                isActive
                  ? 'bg-blue-600/30 text-blue-400 border border-blue-500/50'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-500">Loading L&D Suite...</div>
      ) : (
        <div className="space-y-6">
          {/* TAB 1: OVERVIEW DASHBOARD */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                  <div className="text-sm text-slate-400">Active Courses</div>
                  <div className="text-2xl font-bold text-blue-400">{analytics?.total_active_courses || 0}</div>
                  <div className="text-xs text-slate-500 mt-1">Published Catalog</div>
                </div>
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                  <div className="text-sm text-slate-400">Total Enrollments</div>
                  <div className="text-2xl font-bold text-teal-400">{analytics?.enrolled_employees_count || 0}</div>
                  <div className="text-xs text-slate-500 mt-1">Across Organization</div>
                </div>
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                  <div className="text-sm text-slate-400">Completion Rate</div>
                  <div className="text-2xl font-bold text-emerald-400">{analytics?.course_completion_rate || 0}%</div>
                  <div className="text-xs text-slate-500 mt-1">Passed & Certified</div>
                </div>
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
                  <div className="text-sm text-slate-400">Certificates Issued</div>
                  <div className="text-2xl font-bold text-purple-400">{analytics?.certificates_issued_count || 0}</div>
                  <div className="text-xs text-slate-500 mt-1">Verified Digital Certs</div>
                </div>
              </div>

              {/* Course Catalog Preview & Skill Breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-4">
                  <h3 className="text-lg font-semibold text-white">Popular Courses</h3>
                  <div className="space-y-3">
                    {courses.slice(0, 3).map((c) => (
                      <div key={c.id} className="p-3 bg-slate-900/50 rounded-lg border border-slate-800 flex justify-between items-center">
                        <div>
                          <div className="font-medium text-white">{c.title}</div>
                          <div className="text-xs text-slate-400">{c.instructor_name} • {c.duration_hours}h</div>
                        </div>
                        <span className="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 font-medium">
                          {c.course_type.toUpperCase()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-4">
                  <h3 className="text-lg font-semibold text-white">Top Enterprise Skills</h3>
                  <div className="space-y-3">
                    {analytics?.top_skills?.map((sk, idx) => (
                      <div key={idx} className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg border border-slate-800">
                        <div>
                          <div className="font-medium text-slate-200">{sk.name}</div>
                          <div className="text-xs text-slate-400">Category: {sk.category}</div>
                        </div>
                        <div className="text-sm font-semibold text-teal-400">{sk.count} Certified Staff</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: COURSE CATALOG */}
          {activeTab === 'catalog' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">Published Course Catalog</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {courses.map((course) => (
                  <div key={course.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 flex flex-col justify-between space-y-4">
                    <div>
                      <div className="flex justify-between items-start">
                        <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                          {course.category_name || 'General'}
                        </span>
                        {course.is_mandatory && (
                          <span className="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                            Mandatory
                          </span>
                        )}
                      </div>
                      <h4 className="text-base font-semibold text-white mt-3">{course.title}</h4>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{course.description}</p>
                    </div>

                    <div className="pt-3 border-t border-slate-700/40 flex justify-between items-center text-xs text-slate-400">
                      <span>Instructor: {course.instructor_name || 'VisionCore HR'}</span>
                      <span>Pass: {course.pass_percentage}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: MY LEARNING */}
          {activeTab === 'my-learning' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Active Enrollments</h3>
              <div className="space-y-3">
                {enrollments.map((enr) => (
                  <div key={enr.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div>
                      <h4 className="font-semibold text-white">{enr.course_title}</h4>
                      <div className="text-xs text-slate-400 mt-0.5">User: {enr.user_name} • Enrolled: {new Date(enr.enrolled_at).toLocaleDateString()}</div>
                    </div>
                    <div className="flex items-center gap-4 w-full md:w-auto">
                      <div className="w-32 bg-slate-900 h-3 rounded-full overflow-hidden border border-slate-700">
                        <div className="bg-emerald-500 h-full transition-all duration-300" style={{ width: `${enr.progress_pct}%` }} />
                      </div>
                      <span className="text-sm font-semibold text-emerald-400 min-w-[45px]">{enr.progress_pct}%</span>
                      <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-300 font-medium">
                        {enr.status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: TRAINING SESSIONS */}
          {activeTab === 'sessions' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Live Workshops & Webinars</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sessions.map((sess) => (
                  <div key={sess.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex justify-between items-start">
                      <h4 className="font-semibold text-white">{sess.title}</h4>
                      <span className="text-xs px-2.5 py-1 rounded bg-teal-500/20 text-teal-400 font-medium">
                        {sess.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 space-y-1">
                      <div>Trainer: {sess.trainer_name || 'Staff Trainer'}</div>
                      <div>Location/Link: {sess.location_or_link || 'Online Room'}</div>
                      <div>Capacity: {sess.current_participants} / {sess.max_participants}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: ASSESSMENTS & QUIZZES */}
          {activeTab === 'assessments' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Course Assessments</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {quizzes.map((quiz) => (
                  <div key={quiz.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <h4 className="font-semibold text-white">{quiz.title}</h4>
                    <div className="text-xs text-slate-400">
                      Pass Score: {quiz.pass_score}% • Time Limit: {quiz.time_limit_minutes} min • Questions: {quiz.total_questions}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 6: SKILL MATRIX */}
          {activeTab === 'skills' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Enterprise Skill Inventory</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {skills.map((sk) => (
                  <div key={sk.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4 space-y-2">
                    <div className="flex justify-between items-start">
                      <h4 className="font-semibold text-white">{sk.name}</h4>
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                        {sk.category}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">{sk.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 7: CERTIFICATIONS */}
          {activeTab === 'certificates' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Issued Digital Certificates</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {certificates.map((cert) => (
                  <div key={cert.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-2 flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-white">{cert.course_title}</div>
                      <div className="text-xs text-slate-400">Awarded to: {cert.user_name}</div>
                      <div className="text-xs font-mono text-purple-400 mt-1">{cert.certificate_number}</div>
                    </div>
                    <span className="text-xs px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-300 font-medium">
                      Verified
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 8: BUDGET & SPEND */}
          {activeTab === 'budget' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Annual Training Budgets</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {budgets.map((b) => (
                  <div key={b.id} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-white">{b.department_name} ({b.fiscal_year})</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center py-2 bg-slate-900/50 rounded-lg">
                      <div>
                        <div className="text-xs text-slate-400">Allocated</div>
                        <div className="text-sm font-semibold text-slate-200">${b.allocated_amount.toLocaleString()}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Spent</div>
                        <div className="text-sm font-semibold text-rose-400">${b.spent_amount.toLocaleString()}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Remaining</div>
                        <div className="text-sm font-semibold text-emerald-400">${b.remaining_amount.toLocaleString()}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
