import React from "react";
import { Link } from "react-router-dom";
import { Sparkles, BookOpen, ShieldCheck, ArrowRight, Bot, Cpu, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

const AI_FEATURE_CARDS = [
  {
    title: "AI Copilot Hub",
    desc: "Domain-specific AI copilots for HR, policy lookup, recruitment screening, and manager performance reviews.",
    icon: Bot,
    route: "/dashboard/ai-copilot-hub",
  },
  {
    title: "Enterprise RAG Studio",
    desc: "Ingest PDFs, Word documents, and policy manuals into vector search for grounded, accurate AI answers.",
    icon: BookOpen,
    route: "/dashboard/knowledge-center",
  },
  {
    title: "AI Governance & Security",
    desc: "Set per-role token budgets, restrict AI actions by RBAC permission, and log every AI prompt for compliance.",
    icon: ShieldCheck,
    route: "/dashboard/ai-governance",
  },
  {
    title: "Model & Prompt Manager",
    desc: "Manage system prompts, model endpoints, and LLM temperature configurations in one dashboard.",
    icon: Cpu,
    route: "/dashboard/prompt-manager",
  },
];

export const AISection = () => {
  return (
    <section id="ai" className="scroll-mt-24 py-20 lg:py-28 bg-gray-950 border-t border-gray-800/80 text-white relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Text Column */}
          <div className="lg:col-span-5 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-pink-500/10 border border-pink-500/20 text-xs font-semibold text-pink-400 uppercase tracking-wider">
              <Sparkles className="h-3.5 w-3.5" /> Embedded AI Intelligence
            </div>
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
              Enterprise AI That Respects Permissions
            </h2>
            <p className="text-gray-400 text-lg leading-relaxed">
              VisionCore AI operates strictly within tenant boundaries and user RBAC scoping. Employees only 
              receive insights and policy answers they are authorized to view.
            </p>

            <div className="space-y-3 pt-2">
              {[
                "Ground answers in tenant policy documents via RAG",
                "Zero data leakage across organizational tenants",
                "Complete token budget and cost control dashboard",
                "Audit logs for every AI query & copilot execution",
              ].map((point, idx) => (
                <div key={idx} className="flex items-center gap-2.5 text-sm text-gray-300">
                  <CheckCircle2 className="h-4 w-4 text-pink-400 shrink-0" />
                  <span>{point}</span>
                </div>
              ))}
            </div>

            <div className="pt-4">
              <Link to="/dashboard/ai-studio">
                <button className="px-6 py-3.5 rounded-xl bg-pink-600 hover:bg-pink-500 text-white font-bold transition-all duration-200 inline-flex items-center gap-2 shadow-lg shadow-pink-600/20">
                  <span>Explore AI Studio</span>
                  <ArrowRight size={16} />
                </button>
              </Link>
            </div>
          </div>

          {/* Right Grid Column */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {AI_FEATURE_CARDS.map((card, idx) => {
              const Icon = card.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, scale: 0.95 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: idx * 0.1 }}
                  className="p-6 rounded-2xl bg-gray-900/80 border border-gray-800 hover:border-gray-700 transition-all duration-300 flex flex-col justify-between group"
                >
                  <div>
                    <div className="w-10 h-10 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400 mb-4 group-hover:scale-110 transition-transform">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">{card.title}</h3>
                    <p className="text-xs text-gray-400 leading-relaxed mb-4">{card.desc}</p>
                  </div>

                  <Link
                    to={card.route}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-pink-400 hover:text-pink-300 transition-colors"
                  >
                    <span>View Feature</span>
                    <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};
