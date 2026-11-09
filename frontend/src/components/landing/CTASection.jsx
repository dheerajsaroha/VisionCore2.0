import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, CheckCircle2, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

export const CTASection = () => {
  return (
    <section id="get-started" className="scroll-mt-24 py-20 lg:py-28 bg-gray-950 border-t border-gray-800/80 text-white relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-gradient-to-r from-indigo-600/20 via-purple-600/20 to-pink-600/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-5xl mx-auto px-6 relative z-10 text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="p-8 sm:p-12 lg:p-16 rounded-3xl bg-gradient-to-b from-gray-900 via-gray-900/90 to-gray-950 border border-gray-800 shadow-2xl relative overflow-hidden"
        >
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-300 uppercase tracking-wider mb-6">
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" /> Transform Your Workforce Operations
          </div>

          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-6 leading-tight">
            Ready to Build a Connected & Intelligent Workforce?
          </h2>

          <p className="text-gray-300 text-lg max-w-2xl mx-auto mb-10 leading-relaxed">
            Unify biometric check-in, shifts, HCM, payroll, and AI copilots into one enterprise operating system.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-10">
            <Link to="/signup" className="w-full sm:w-auto">
              <button className="w-full sm:w-auto px-8 py-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold transition-all duration-200 flex items-center justify-center gap-2 shadow-xl shadow-indigo-600/30">
                <span>Get Started Now</span>
                <ArrowRight size={18} />
              </button>
            </Link>
            <Link to="/login" className="w-full sm:w-auto">
              <button className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 hover:text-white font-semibold transition-all duration-200 flex items-center justify-center gap-2">
                <ShieldCheck size={18} className="text-indigo-400" />
                <span>Sign In to Organization</span>
              </button>
            </Link>
          </div>

          {/* Factual Architecture Guarantees */}
          <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-gray-400 font-medium pt-6 border-t border-gray-800/80">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Instant Organization Setup</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Multi-Tenant Schema Isolation</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>27 Scoped RBAC Roles</span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};
