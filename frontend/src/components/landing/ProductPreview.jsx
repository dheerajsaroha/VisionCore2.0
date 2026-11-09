import React, { useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  Users,
  DollarSign,
  Layers,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const TABS = [
  { id: "biometrics", label: "Biometric Attendance Pipeline", icon: Cpu },
  { id: "workforce", label: "Workforce & Shift Roster", icon: Users },
  { id: "ai", label: "AI Copilot & RAG Studio", icon: BrainCircuit },
  { id: "payroll", label: "Automated Payroll & Finance", icon: DollarSign },
  { id: "security", label: "Multi-Tenant RBAC & Audit", icon: ShieldCheck },
];

export const ProductPreview = () => {
  const [activeTab, setActiveTab] = useState("biometrics");

  return (
    <section id="preview" className="scroll-mt-24 py-16 lg:py-24 bg-gray-950 border-t border-gray-800/80 relative">
      <div className="max-w-7xl mx-auto px-6">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-4">
            <Layers className="h-3.5 w-3.5" /> Live Platform Experience
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight mb-4">
            Unified Control Pane for the Modern Enterprise
          </h2>
          <p className="text-gray-400 text-lg">
            Explore how VisionCore handles biometrics, workforce planning, payroll calculation, 
            and AI copilots in a single interface.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center justify-start lg:justify-center gap-2 overflow-x-auto pb-4 mb-8 hide-scrollbar">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all duration-200 border ${
                  isActive
                    ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/20"
                    : "bg-gray-900/80 text-gray-400 hover:text-white hover:bg-gray-800 border-gray-800"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-white" : "text-gray-400"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Preview Frame */}
        <div className="relative rounded-2xl border border-gray-800 bg-gray-900/90 shadow-2xl p-4 sm:p-6 lg:p-8 backdrop-blur-xl">
          {/* Top Window Bar */}
          <div className="flex items-center justify-between pb-6 mb-6 border-b border-gray-800 text-xs text-gray-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
              <span className="ml-2 font-mono text-gray-400 font-medium hidden sm:inline">
                visioncore.internal/enterprise/dashboard
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Live Tenant Isolated
              </span>
              <span className="font-mono text-gray-500">v2.4.0-prod</span>
            </div>
          </div>

          {/* Dynamic Tab Content */}
          <AnimatePresence mode="wait">
            {activeTab === "biometrics" && (
              <motion.div
                key="biometrics"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {/* Metrics Row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400 mb-1">Live Liveness Detection</div>
                    <div className="text-2xl font-bold text-white flex items-center gap-2">
                      99.85% <span className="text-xs text-emerald-400 font-semibold">Anti-Spoof Passed</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Deep Learning 3D Surface Analysis</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400 mb-1">Embedding Match Speed</div>
                    <div className="text-2xl font-bold text-indigo-400">142 ms</div>
                    <div className="text-xs text-gray-500 mt-1">pgvector HNSW Cosine Distance</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400 mb-1">Today's Biometric Check-ins</div>
                    <div className="text-2xl font-bold text-white">4,892</div>
                    <div className="text-xs text-emerald-400 mt-1">0 False Acceptance Incidents</div>
                  </div>
                </div>

                {/* Simulated Verification Stream */}
                <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2 text-sm font-bold text-white">
                      <UserCheck className="h-4 w-4 text-indigo-400" />
                      Recent Verification Stream
                    </div>
                    <span className="text-xs text-gray-400 font-mono">Real-time Stream</span>
                  </div>
                  <div className="divide-y divide-gray-800/80">
                    {[
                      { name: "Dr. Sarah Jenkins", dept: "AI Engineering", time: "09:02:14 AM", score: "99.92%", status: "Verified", method: "Camera Node #04" },
                      { name: "Marcus Vance", dept: "Global Operations", time: "09:01:45 AM", score: "99.81%", status: "Verified", method: "Mobile Web Terminal" },
                      { name: "Priya Sharma", dept: "Finance & Tax", time: "08:58:30 AM", score: "99.88%", status: "Verified", method: "Kiosk Terminal #01" },
                    ].map((row, i) => (
                      <div key={i} className="py-3 flex items-center justify-between text-xs sm:text-sm">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center font-bold text-indigo-300">
                            {row.name.charAt(0)}
                          </div>
                          <div>
                            <div className="font-semibold text-white">{row.name}</div>
                            <div className="text-xs text-gray-400">{row.dept}</div>
                          </div>
                        </div>
                        <div className="hidden sm:block text-xs text-gray-400 font-mono">{row.method}</div>
                        <div className="text-right">
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-semibold text-xs">
                            <CheckCircle2 className="h-3 w-3" /> {row.status} ({row.score})
                          </span>
                          <div className="text-xs text-gray-500 font-mono mt-0.5">{row.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "workforce" && (
              <motion.div
                key="workforce"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Total Headcount</div>
                    <div className="text-2xl font-bold text-white mt-1">1,248</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">On Duty Today</div>
                    <div className="text-2xl font-bold text-emerald-400 mt-1">1,180 (94.5%)</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Active Leave</div>
                    <div className="text-2xl font-bold text-amber-400 mt-1">42 Employees</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Shift Fill Rate</div>
                    <div className="text-2xl font-bold text-indigo-400 mt-1">99.1%</div>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-4">
                  <div className="text-sm font-bold text-white mb-3">Shift & Overtime Distribution</div>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-xs text-gray-300 mb-1">
                        <span>Morning Shift (08:00 - 16:00)</span>
                        <span className="font-semibold text-white">650 / 660 Capacity</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-gray-800 overflow-hidden">
                        <div className="h-full bg-indigo-500 rounded-full" style={{ width: "98.4%" }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-300 mb-1">
                        <span>Evening Shift (16:00 - 00:00)</span>
                        <span className="font-semibold text-white">420 / 450 Capacity</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-gray-800 overflow-hidden">
                        <div className="h-full bg-purple-500 rounded-full" style={{ width: "93.3%" }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-300 mb-1">
                        <span>Night Shift (00:00 - 08:00)</span>
                        <span className="font-semibold text-white">110 / 120 Capacity</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-gray-800 overflow-hidden">
                        <div className="h-full bg-pink-500 rounded-full" style={{ width: "91.6%" }} />
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "ai" && (
              <motion.div
                key="ai"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/30 flex items-start gap-4">
                  <div className="p-2.5 rounded-lg bg-indigo-600 text-white shrink-0">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">VisionCore AI Copilot Hub</div>
                    <div className="text-xs text-gray-300 mt-1 leading-relaxed">
                      "Querying company leave policies and overtime rules using RAG knowledge search across 42 active HR handbook documents..."
                    </div>
                    <div className="mt-3 p-3 rounded-lg bg-gray-950 border border-gray-800 text-xs font-mono text-indigo-300">
                      Response: "Under Section 4.2 of North America Policy, employees receive 1.5x hourly rate for hours exceeding 40h/week. Approval required by Manager role."
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "payroll" && (
              <motion.div
                key="payroll"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Current Payroll Cycle</div>
                    <div className="text-2xl font-bold text-white mt-1">$482,500.00</div>
                    <div className="text-xs text-emerald-400 mt-1">Calculated from 100% Verified Clock Data</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Reimbursement Claims</div>
                    <div className="text-2xl font-bold text-indigo-400 mt-1">$14,280.00</div>
                    <div className="text-xs text-gray-400 mt-1">28 Approved Claims Pending Payout</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Tax Withholdings</div>
                    <div className="text-2xl font-bold text-purple-400 mt-1">$96,500.00</div>
                    <div className="text-xs text-gray-400 mt-1">Automated Multi-State Compliance</div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "security" && (
              <motion.div
                key="security"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">RBAC Configuration</div>
                    <div className="text-xl font-bold text-white mt-1">32 Roles / 143 Permissions</div>
                    <div className="text-xs text-emerald-400 mt-1">Strict Least-Privilege Scoping</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Tenant Data Isolation</div>
                    <div className="text-xl font-bold text-indigo-400 mt-1">Schema & Org Isolation</div>
                    <div className="text-xs text-gray-400 mt-1">Zero Cross-Tenant Leakage</div>
                  </div>
                  <div className="p-4 rounded-xl bg-gray-950/60 border border-gray-800">
                    <div className="text-xs text-gray-400">Redis Token Blacklist</div>
                    <div className="text-xl font-bold text-purple-400 mt-1">Active & Rate-Limited</div>
                    <div className="text-xs text-gray-400 mt-1">HttpOnly Cookie Token Rotation</div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
};
