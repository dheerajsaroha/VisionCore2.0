import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, Zap, ChevronRight, Activity, Users, Lock, Sparkles, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

const STATS = [
  { label: "Role-Based Access Control", value: "32 Roles", sub: "143 Scoped Permissions" },
  { label: "Multi-Tenant Architecture", value: "Isolated", sub: "Organization Data Isolation" },
  { label: "Biometric Search Engine", value: "pgvector", sub: "Cosine Embedding Similarity" },
  { label: "Liveness Anti-Spoofing", value: "Real-time", sub: "Multi-Factor Verification" },
];

export const HeroSection = () => {
  return (
    <section className="relative pt-12 pb-20 lg:pt-16 lg:pb-28 overflow-hidden bg-gray-950 text-white">
      {/* Background Subtle Mesh Grid & Ambient Glows */}
      <div className="absolute inset-0 bg-[radial-gradient(#312e81_1px,transparent_1px)] [background-size:32px_32px] opacity-25 pointer-events-none" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-gradient-to-tr from-indigo-600/20 via-purple-600/20 to-pink-600/10 rounded-full blur-[130px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 relative z-10 text-center">
        {/* Release Badge */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs sm:text-sm font-medium text-indigo-300 mb-8 backdrop-blur-md shadow-inner"
        >
          <Sparkles className="h-4 w-4 text-indigo-400" />
          <span>VisionCore Enterprise Workforce Platform</span>
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />
          <Link to="/signup" className="text-white hover:text-indigo-200 flex items-center font-semibold ml-1">
            Get Started <ChevronRight className="h-4 w-4" />
          </Link>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.1] mb-6 text-balance max-w-5xl mx-auto"
        >
          The Enterprise Workforce Operating System{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400">
            Built for Scale & Intelligence.
          </span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-xl text-gray-300 max-w-3xl mx-auto mb-10 leading-relaxed text-balance"
        >
          Unify biometric attendance check-in, liveness detection, multi-tenant RBAC, automated payroll, 
          and AI copilots into a secure, audit-ready workforce platform.
        </motion.p>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
        >
          <Link to="/signup" className="w-full sm:w-auto">
            <button className="w-full sm:w-auto px-8 py-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold transition-all duration-200 flex items-center justify-center gap-2 shadow-xl shadow-indigo-600/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5">
              <span>Get Started</span>
              <ArrowRight size={18} />
            </button>
          </Link>
          <Link to="/login" className="w-full sm:w-auto">
            <button className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-200 hover:text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2">
              <ShieldCheck size={18} className="text-indigo-400" />
              <span>Sign In</span>
            </button>
          </Link>
        </motion.div>

        {/* Platform Trust Highlights */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-5xl mx-auto pt-6 border-t border-gray-800/80"
        >
          {STATS.map((stat, idx) => (
            <div key={idx} className="p-4 rounded-xl bg-gray-900/40 border border-gray-800/60 backdrop-blur-sm text-left">
              <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mb-0.5">
                {stat.value}
              </div>
              <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">
                {stat.label}
              </div>
              <div className="text-xs text-gray-400">
                {stat.sub}
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
};
