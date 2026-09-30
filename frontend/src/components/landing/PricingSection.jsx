import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, Sparkles, Loader2, AlertTriangle } from "lucide-react";
import { getPublicPlans } from "../../services/publicService";

/**
 * Pricing section rendered from the live plan catalog.
 *
 * Every price, feature list and capacity limit comes from
 * GET /public/plans, which is backed by the same subscription_plans,
 * plan_features and licensing_limits rows the backend enforces. Nothing here is
 * hardcoded, so the page cannot advertise a tier the server would refuse.
 */
export const PricingSection = () => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getPublicPlans()
      .then((data) => {
        if (cancelled) return;
        setPlans(Array.isArray(data?.plans) ? data.plans : []);
        setError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setError("Pricing is temporarily unavailable.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const limitLabel = (plan, type, unit) => {
    const entry = plan.limits?.[type];
    if (!entry) return null;
    if (entry === null) return `Unlimited ${unit}`;
    return `Up to ${entry.hard ?? entry.soft} ${unit}`;
  };

  const FEATURE_LABELS = {
    attendance: "Biometric attendance",
    face_recognition: "Face recognition",
    liveness_detection: "Liveness / anti-spoof",
    geofencing: "Geofencing",
    leave_management: "Leave management",
    employee_management: "Employee directory",
    payroll: "Payroll & taxes",
    performance_reviews: "Performance & OKRs",
    recruitment: "Recruitment pipeline",
    training: "Learning management",
    analytics: "Analytics",
    ai_analytics: "AI analytics",
    reports: "Reporting",
    audit_trail: "Audit trail",
    mfa: "Multi-factor auth",
    sso: "Single sign-on",
    custom_roles: "Custom roles",
    custom_workflows: "Approval workflows",
    webhooks: "Webhooks",
    integrations: "Integrations",
    assets: "Asset tracking",
    expenses: "Expenses",
    travel: "Travel claims",
    ai_chat: "AI copilots",
    notifications: "Notifications",
  };

  const formatPrice = (value) =>
    Number(value) === 0 ? "0" : Number(value).toFixed(2);

  return (
    <section
      id="pricing"
      className="scroll-mt-24 py-20 lg:py-28 bg-gray-950 border-t border-gray-800/80 relative"
    >
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-sm font-medium mb-6">
            <Sparkles className="h-4 w-4" />
            Transparent pricing
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-white tracking-tight mb-6">
            Pay for what you actually use
          </h2>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed">
            Each plan is enforced server-side. The limits and features below are
            read from your own configuration, not a marketing mock-up.
          </p>
        </motion.div>

        {loading && (
          <div className="flex items-center justify-center gap-3 py-20 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Loading plans…</span>
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center justify-center gap-3 py-20 text-amber-400">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && plans.length === 0 && (
          <p className="text-center text-gray-500 py-20">
            No plans are currently published. Please contact sales.
          </p>
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="grid lg:grid-cols-3 gap-8">
            {plans.map((plan, index) => {
              const isTop = plan.tier === 1;
              return (
                <motion.div
                  key={plan.code}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  className={`relative rounded-3xl border p-8 flex flex-col ${
                    isTop
                      ? "border-indigo-500/50 bg-gradient-to-b from-indigo-500/10 to-gray-950 shadow-[0_0_50px_rgba(99,102,241,0.15)]"
                      : "border-gray-800 bg-gray-900/40"
                  }`}
                >
                  {isTop && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-indigo-600 text-white text-xs font-semibold">
                      Most Popular
                    </div>
                  )}

                  <h3 className="text-2xl font-bold text-white mb-2">{plan.name}</h3>
                  {plan.description && (
                    <p className="text-sm text-gray-400 mb-6">{plan.description}</p>
                  )}

                  <div className="mb-6">
                    <span className="text-5xl font-bold text-white">
                      ${formatPrice(plan.monthly_price)}
                    </span>
                    <span className="text-gray-400 ml-2">/month</span>
                    <div className="text-xs text-gray-500 mt-2">
                      {Number(plan.yearly_price) > 0 ? (
                        <>
                          ${formatPrice(plan.yearly_price)} billed yearly
                        </>
                      ) : (
                        "Free forever"
                      )}
                    </div>
                  </div>

                  {plan.trial_days > 0 && (
                    <div className="mb-6 text-sm text-indigo-300">
                      Includes a {plan.trial_days}-day trial
                    </div>
                  )}

                  {/* Capacity limits are the enforceable part of each tier. */}
                  <ul className="space-y-2 mb-6 text-sm">
                    {[
                      limitLabel(plan, "employees", "employees"),
                      limitLabel(plan, "camera_devices", "camera devices"),
                      limitLabel(plan, "biometric_devices", "biometric devices"),
                      limitLabel(plan, "storage_gb", "GB storage"),
                    ]
                      .filter(Boolean)
                      .map((line) => (
                        <li key={line} className="flex items-center gap-2 text-gray-300">
                          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                          {line}
                        </li>
                      ))}
                  </ul>

                  <div className="text-xs font-semibold text-white uppercase tracking-wider mb-3">
                    Includes {plan.features.length} features
                  </div>
                  <ul className="space-y-2 mb-8 text-sm flex-1">
                    {plan.features.slice(0, 8).map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-gray-400">
                        <Check className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                        {FEATURE_LABELS[feature] || feature.replace(/_/g, " ")}
                      </li>
                    ))}
                    {plan.features.length > 8 && (
                      <li className="text-xs text-gray-500 pl-6">
                        + {plan.features.length - 8} more
                      </li>
                    )}
                  </ul>

                  <Link
                    to="/signup"
                    className={`w-full text-center py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
                      isTop
                        ? "bg-indigo-600 hover:bg-indigo-700 text-white"
                        : "bg-gray-800 hover:bg-gray-700 text-white"
                    }`}
                  >
                    Start {plan.trial_days > 0 ? `${plan.trial_days}-day trial` : "free"}
                  </Link>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};

export default PricingSection;
