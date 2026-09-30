import React from "react";
import { Link } from "react-router-dom";
import { Zap, ChevronRight, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

export const AnnouncementBanner = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full bg-gradient-to-r from-indigo-900/90 via-purple-900/90 to-indigo-950/90 border-b border-indigo-500/20 py-2.5 px-4 text-center text-xs sm:text-sm text-indigo-200 font-medium relative z-50 backdrop-blur-md"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 text-xs font-semibold uppercase tracking-wider">
          <Sparkles className="h-3 w-3 text-indigo-400 animate-pulse" />
          VisionCore 2.0 Release
        </span>
        <span className="text-gray-200 hidden sm:inline">
          AI Workforce Intelligence Platform with Biometrics, 27-Role RBAC & Multi-Tenant Isolation
        </span>
        <Link
          to="/signup"
          className="inline-flex items-center gap-1 text-white hover:text-indigo-300 underline font-semibold transition-colors group"
        >
          <span>Explore Platform</span>
          <ChevronRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </div>
    </motion.div>
  );
};
