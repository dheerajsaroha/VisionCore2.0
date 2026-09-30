import React from "react";
import { Link } from "react-router-dom";
import {
  Users,
  Cpu,
  Building2,
  BookOpen,
  DollarSign,
  ShieldCheck,
  BrainCircuit,
  Globe,
  ArrowRight,
  CheckCircle2,
  Award,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";

const CAPABILITIES = [
  {
    title: "Workforce & Attendance",
    category: "Workforce Core",
    icon: Users,
    desc: "Biometric check-in, shift scheduling, roster planner, capacity analytics, and holiday calendars.",
    features: ["Biometric & Geo Check-in", "Shift Roster Engine", "Overtime & Leave Tracking", "Capacity Forecasting"],
    href: "/dashboard/workforce/attendance",
    color: "indigo",
  },
  {
    title: "AI Biometrics & Liveness",
    category: "Security",
    icon: Cpu,
    desc: "Neural network anti-spoofing with pgvector embedding similarity for instant verification.",
    features: ["3D Liveness Detection", "pgvector Cosine Search", "Zero False Acceptance", "Edge Camera Node Sync"],
    href: "/dashboard/attendance",
    color: "purple",
  },
  {
    title: "HCM & Talent Operations",
    category: "People",
    icon: Building2,
    desc: "Comprehensive employee directory, multi-tier org tree, career paths, and succession planning.",
    features: ["Visual Org Tree", "Identity Directory", "Skill Matrices", "Succession Planning"],
    href: "/dashboard/hr",
    color: "emerald",
  },
  {
    title: "Performance & Learning",
    category: "Growth",
    icon: Award,
    desc: "OKRs, 360-degree performance reviews, goal calibration, and course certification tracking.",
    features: ["Goal Tracking & OKRs", "360 Performance Reviews", "Learning Management", "Skills & Certifications"],
    href: "/dashboard/performance",
    color: "amber",
  },
  {
    title: "Automated Payroll & Tax",
    category: "Finance",
    icon: DollarSign,
    desc: "Zero-error payroll generation powered by clocking logs, tax deductions, and expense claims.",
    features: ["Automated Payslips", "Tax & Deduction Formulas", "Expense Approvals", "Multi-Currency Support"],
    href: "/dashboard/payroll",
    color: "sky",
  },
  {
    title: "Enterprise Operations & Assets",
    category: "Operations",
    icon: ShieldCheck,
    desc: "IT asset tracking, SLA service tickets, and customizable multi-stage approval workflows.",
    features: ["IT Asset Inventory", "SLA Service Tickets", "Multi-Stage Approvals", "Audit Logging"],
    href: "/dashboard/operations",
    color: "pink",
  },
];

export const CapabilityGrid = () => {
  return (
    <section id="features" className="scroll-mt-24 py-20 lg:py-28 bg-gray-950 border-t border-gray-800/80 text-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-4">
            <Zap className="h-3.5 w-3.5" /> Comprehensive Capability Suite
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
            Built for Modern Enterprise Requirements
          </h2>
          <p className="text-gray-400 text-lg">
            Every module is tightly integrated into VisionCore's unified role-based authorization system.
          </p>
        </div>

        {/* Capability Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {CAPABILITIES.map((item, idx) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.08 }}
                className="p-6 sm:p-8 rounded-2xl bg-gray-900/80 border border-gray-800 hover:border-gray-700 transition-all duration-300 flex flex-col justify-between group hover:-translate-y-1 shadow-lg"
              >
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform duration-300">
                      <Icon className="h-6 w-6" />
                    </div>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-gray-800 border border-gray-700 text-gray-300">
                      {item.category}
                    </span>
                  </div>

                  <h3 className="text-xl font-bold text-white mb-3 group-hover:text-indigo-300 transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-sm text-gray-400 leading-relaxed mb-6">
                    {item.desc}
                  </p>

                  <ul className="space-y-2.5 mb-8">
                    {item.features.map((feat, fIdx) => (
                      <li key={fIdx} className="flex items-center gap-2 text-xs sm:text-sm text-gray-300">
                        <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <Link
                  to={item.href}
                  className="inline-flex items-center justify-between pt-4 border-t border-gray-800 text-sm font-semibold text-indigo-400 group-hover:text-indigo-300 transition-colors"
                >
                  <span>Explore Module</span>
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
