import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, Lock, Key, Server, Database, Activity, CheckCircle2, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";

const SECURITY_HIGHLIGHTS = [
  {
    title: "27 RBAC System Roles",
    desc: "Pre-configured roles spanning Admin, HR Director, Payroll Specialist, Department Manager, and Employee.",
    icon: Key,
  },
  {
    title: "143 Scoped Permissions",
    desc: "Fine-grained capability checks enforcing read, write, approve, and export limits across all 40 backend routers.",
    icon: Lock,
  },
  {
    title: "Multi-Tenant Schema Isolation",
    desc: "Organization scope checking ensures strict boundary separation so tenant data never leaks across boundaries.",
    icon: Database,
  },
  {
    title: "Session & Token Blacklisting",
    desc: "JWT authentication with HttpOnly cookies, token rotation, and distributed Redis blacklist revocation.",
    icon: Server,
  },
];

export const SecurityEnterpriseSection = () => {
  return (
    <section id="security" className="scroll-mt-24 py-20 lg:py-28 bg-gray-950 border-t border-gray-800/80 text-white relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-4">
            <ShieldCheck className="h-3.5 w-3.5" /> Enterprise Grade Security
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
            Built for Compliance & Strict Isolation
          </h2>
          <p className="text-gray-400 text-lg">
            Protect your workforce biometric data, payroll records, and identity directory with multi-layered defense.
          </p>
        </div>

        {/* Highlight Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {SECURITY_HIGHLIGHTS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className="p-6 rounded-2xl bg-gray-900/80 border border-gray-800 hover:border-gray-700 transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{item.title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{item.desc}</p>
              </motion.div>
            );
          })}
        </div>

        {/* Security Deep Link Bar */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-emerald-950/40 via-gray-900 to-indigo-950/40 border border-emerald-500/30 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-300 shrink-0">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <div className="text-sm font-bold text-white">Role & Scope Matrix Documentation</div>
              <div className="text-xs text-gray-400">View exact role definitions, permission mappings, and security policies</div>
            </div>
          </div>
          <Link to="/dashboard/permissions">
            <button className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap shadow-lg shadow-emerald-600/20">
              <span>View Security Controls</span>
              <ArrowRight size={14} />
            </button>
          </Link>
        </div>
      </div>
    </section>
  );
};
