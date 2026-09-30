import React from "react";
import { ArrowRight, ShieldCheck, Database, Cpu, BrainCircuit, Users, DollarSign, Layers, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

const STAGES = [
  {
    step: "01",
    title: "Identity & Biometrics",
    desc: "Camera Nodes & Mobile Web Terminals capture face embeddings with neural net liveness detection.",
    icon: Cpu,
    color: "text-indigo-400",
    bg: "bg-indigo-500/10 border-indigo-500/30",
  },
  {
    step: "02",
    title: "Multi-Tenant RBAC Core",
    desc: "PostgreSQL pgvector & Redis rate limiting enforce multi-tenant isolation and 32 role scoping.",
    icon: Database,
    color: "text-purple-400",
    bg: "bg-purple-500/10 border-purple-500/30",
  },
  {
    step: "03",
    title: "Workforce & Payroll",
    desc: "Attendance, leave, shift rosters, and payroll formulas compute zero-error compensation.",
    icon: DollarSign,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
  },
  {
    step: "04",
    title: "AI Copilot & Insights",
    desc: "RAG knowledge engine and predictive analytics deliver real-time operational intelligence.",
    icon: BrainCircuit,
    color: "text-pink-400",
    bg: "bg-pink-500/10 border-pink-500/30",
  },
];

export const PlatformOverview = () => {
  return (
    <section id="platform" className="scroll-mt-24 py-20 bg-gray-950 border-t border-gray-800/80 text-white relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-xs font-semibold text-purple-400 uppercase tracking-wider mb-4">
            <Layers className="h-3.5 w-3.5" /> Platform Architecture
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
            How VisionCore Powers Your Workforce
          </h2>
          <p className="text-gray-400 text-lg">
            A seamless data pipeline connecting physical entry points to automated enterprise intelligence.
          </p>
        </div>

        {/* Architecture Flow */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          {STAGES.map((stage, idx) => {
            const Icon = stage.icon;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className="p-6 rounded-2xl bg-gray-900/70 border border-gray-800 relative group hover:border-gray-700 transition-all duration-300"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-mono font-bold text-gray-500">{stage.step}</span>
                  <div className={`p-3 rounded-xl ${stage.bg} border ${stage.color}`}>
                    <Icon className="h-6 w-6" />
                  </div>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">{stage.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{stage.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
