import React from "react";
import { Link } from "react-router-dom";
import { Network, Globe, Key, Cpu, Zap, ArrowRight, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

const INTEGRATION_CATEGORIES = [
  {
    category: "Identity & SSO",
    desc: "Single Sign-On and directory sync via standard protocols.",
    items: ["Okta SSO", "Azure AD / Entra ID", "SAML 2.0 & OAuth2", "Google Workspace"],
  },
  {
    category: "Biometric Hardware",
    desc: "Edge nodes and IP cameras for physical check-in points.",
    items: ["RTSP IP Camera Streams", "Android Kiosk Terminals", "Thermal Liveness Scanners", "USB Webcams"],
  },
  {
    category: "Payroll & ERP",
    desc: "Seamless export and bidirectional sync for payroll calculations.",
    items: ["SAP SuccessFactors", "Workday Connector", "QuickBooks Payroll", "Custom REST Webhooks"],
  },
  {
    category: "Developer APIs",
    desc: "Full OpenAPI / Swagger specification with SDK bindings.",
    items: ["FastAPI OpenAPI Spec", "Scoped API Tokens", "Event Webhooks", "Rate-Limited REST"],
  },
];

export const IntegrationsSection = () => {
  return (
    <section className="py-20 bg-gray-950 border-t border-gray-800/80 text-white relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-xs font-semibold text-sky-400 uppercase tracking-wider mb-4">
            <Network className="h-3.5 w-3.5" /> Open Enterprise Ecosystem
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
            Connects With Your Existing Infrastructure
          </h2>
          <p className="text-gray-400 text-lg">
            Integrate VisionCore into your identity providers, camera networks, and payroll systems without lock-in.
          </p>
        </div>

        {/* Categories Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {INTEGRATION_CATEGORIES.map((cat, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              className="p-6 rounded-2xl bg-gray-900/80 border border-gray-800 hover:border-gray-700 transition-all duration-300 flex flex-col justify-between"
            >
              <div>
                <h3 className="text-lg font-bold text-white mb-2">{cat.category}</h3>
                <p className="text-xs text-gray-400 mb-6 leading-relaxed">{cat.desc}</p>
                <ul className="space-y-2 mb-6">
                  {cat.items.map((item, iIdx) => (
                    <li key={iIdx} className="flex items-center gap-2 text-xs font-medium text-gray-300">
                      <CheckCircle2 className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <Link
                to="/dashboard/enterprise"
                className="inline-flex items-center gap-1 text-xs font-semibold text-sky-400 hover:text-sky-300 transition-colors pt-4 border-t border-gray-800"
              >
                <span>View Integrations</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};
