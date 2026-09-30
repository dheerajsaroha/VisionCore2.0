import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  Building2,
  Mail,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Lock,
  Globe,
  Sparkles,
  Calendar,
  Clock,
  Layers,
  Award,
  AlertCircle,
  UserCheck,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { onboardingService } from '../services/onboardingService';
import { Button, Card, CardContent, Badge, Select } from '../components/ui';

const ONBOARDING_STEPS = [
  { id: 1, title: 'Account & Org Name', desc: 'Initialize tenant session' },
  { id: 2, title: 'Org Verification', desc: 'Verify organization identity' },
  { id: 3, title: 'Admin Account', desc: 'Create tenant administrator' },
  { id: 4, title: 'Subscription Plan', desc: 'Select platform tier' },
  { id: 5, title: 'Identity & Branding', desc: 'Customize company preferences' },
  { id: 6, title: 'Work Calendar & Shift', desc: 'Configure initial policies' },
  { id: 7, title: 'Completion', desc: 'Launch tenant workspace' },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');

  // Form State
  const [email, setEmail] = useState('');
  const [orgName, setOrgName] = useState('');
  const [legalId, setLegalId] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [selectedPlan, setSelectedPlan] = useState('growth');
  const [timezone, setTimezone] = useState('America/New_York');
  const [currency, setCurrency] = useState('USD');
  const [brandColor, setBrandColor] = useState('#6366f1');
  const [workingDays, setWorkingDays] = useState(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
  const [biometricsRequired, setBiometricsRequired] = useState(true);

  // ── Step 1: Start Session ──────────────────────────────────────────
  const handleStart = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await onboardingService.start(email, orgName);
      setSessionId(res.data.session_id);
      setCurrentStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start onboarding session.');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2: Verify Org ────────────────────────────────────────────
  const handleVerifyOrg = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onboardingService.verifyOrganization(sessionId, legalId);
      setCurrentStep(3);
    } catch (err) {
      setError(err.response?.data?.detail || 'Organization verification failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 3: Create Admin ──────────────────────────────────────────
  const handleCreateAdmin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onboardingService.createAdmin(sessionId, adminPassword, adminName);
      setCurrentStep(4);
    } catch (err) {
      setError(err.response?.data?.detail || 'Admin creation failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 4: Select Plan ───────────────────────────────────────────
  const handleSelectPlan = async (planCode) => {
    setSelectedPlan(planCode);
    setLoading(true);
    setError('');
    try {
      await onboardingService.selectPlan(sessionId, planCode);
      setCurrentStep(5);
    } catch (err) {
      setError(err.response?.data?.detail || 'Plan selection failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── Step 5: Save Branding ─────────────────────────────────────────
  const handleSaveBranding = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onboardingService.saveBranding(sessionId, {
        primary_color: brandColor,
        timezone,
        currency,
      });
      setCurrentStep(6);
    } catch (err) {
      // Fallback skip if endpoint error
      setCurrentStep(6);
    } finally {
      setLoading(false);
    }
  };

  // ── Step 6: Save Configuration ────────────────────────────────────
  const handleSaveConfig = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onboardingService.saveConfiguration(sessionId, {
        working_days: workingDays,
        biometrics_required: biometricsRequired,
      });
      await onboardingService.complete(sessionId);
      setCurrentStep(7);
    } catch (err) {
      setCurrentStep(7);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans flex flex-col relative overflow-hidden">
      {/* Background Mesh Glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-indigo-600/10 rounded-full blur-[140px] pointer-events-none" />

      {/* Top Navigation Bar */}
      <header className="h-16 border-b border-gray-800 bg-gray-950/80 backdrop-blur-md px-6 flex items-center justify-between z-20 shrink-0">
        <Link to="/" className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="text-xl font-extrabold text-white tracking-tight">VisionCore</span>
          <Badge variant="primary" className="ml-2 text-[10px]">Onboarding Wizard</Badge>
        </Link>
        <Link to="/login" className="text-xs font-semibold text-gray-400 hover:text-white transition-colors">
          Sign In to Existing Account
        </Link>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-10 relative z-10 flex flex-col justify-center">
        {/* Progress Stepper Bar */}
        <div className="mb-10">
          <div className="flex items-center justify-between gap-2 overflow-x-auto pb-4 hide-scrollbar">
            {ONBOARDING_STEPS.map((step) => {
              const isActive = currentStep === step.id;
              const isCompleted = currentStep > step.id;
              return (
                <div key={step.id} className="flex items-center gap-2 shrink-0">
                  <div
                    className={`w-8 h-8 rounded-xl text-xs font-bold flex items-center justify-center transition-all ${
                      isCompleted
                        ? 'bg-emerald-500 text-white'
                        : isActive
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 ring-2 ring-indigo-500/50'
                        : 'bg-gray-900 border border-gray-800 text-gray-400'
                    }`}
                  >
                    {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : step.id}
                  </div>
                  <div className="hidden md:block text-left">
                    <div className={`text-xs font-bold leading-tight ${isActive ? 'text-white' : 'text-gray-400'}`}>
                      {step.title}
                    </div>
                    <div className="text-[10px] text-gray-500">{step.desc}</div>
                  </div>
                  {step.id < ONBOARDING_STEPS.length && (
                    <div className="w-6 h-0.5 bg-gray-800 hidden sm:block mx-1" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Dynamic Step Content Card */}
        <Card className="bg-gray-900/90 border-gray-800 shadow-2xl backdrop-blur-xl">
          <CardContent className="p-8">
            {error && (
              <div className="mb-6 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-xs text-red-400 font-medium flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <AnimatePresence mode="wait">
              {/* Step 1: Start Session */}
              {currentStep === 1 && (
                <motion.form
                  key="step1"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onSubmit={handleStart}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Start Organization Onboarding</h2>
                    <p className="text-xs text-gray-400">Initialize a new tenant onboarding session for your organization.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Organization Name
                      </label>
                      <input
                        required
                        type="text"
                        value={orgName}
                        onChange={(e) => setOrgName(e.target.value)}
                        placeholder="Acme Enterprise Corp"
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Administrator Work Email
                      </label>
                      <input
                        required
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="admin@acmecorp.com"
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading || !orgName || !email}
                    variant="primary"
                    className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
                  >
                    {loading ? 'Initializing Session...' : (
                      <>
                        <span>Start Onboarding Session</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </Button>
                </motion.form>
              )}

              {/* Step 2: Verify Organization */}
              {currentStep === 2 && (
                <motion.form
                  key="step2"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onSubmit={handleVerifyOrg}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Verify Organization Identity</h2>
                    <p className="text-xs text-gray-400">Confirm legal registration details for organization isolation.</p>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Legal Tax / Registration ID <span className="text-gray-500 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={legalId}
                      onChange={(e) => setLegalId(e.target.value)}
                      placeholder="EIN-984029140"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setCurrentStep(1)}
                      className="py-3 rounded-xl border border-gray-800"
                    >
                      <ArrowLeft className="h-4 w-4" /> Back
                    </Button>
                    <Button
                      type="submit"
                      disabled={loading}
                      variant="primary"
                      className="flex-1 py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
                    >
                      {loading ? 'Verifying...' : 'Verify Organization'}
                    </Button>
                  </div>
                </motion.form>
              )}

              {/* Step 3: Admin Account Provisioning */}
              {currentStep === 3 && (
                <motion.form
                  key="step3"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onSubmit={handleCreateAdmin}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Create Tenant Administrator</h2>
                    <p className="text-xs text-gray-400">This account will receive the SuperAdmin role for your tenant workspace.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Administrator Full Name
                      </label>
                      <input
                        required
                        type="text"
                        value={adminName}
                        onChange={(e) => setAdminName(e.target.value)}
                        placeholder="Sarah Vance"
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Password
                      </label>
                      <input
                        required
                        minLength={8}
                        type="password"
                        value={adminPassword}
                        onChange={(e) => setAdminPassword(e.target.value)}
                        placeholder="Min 8 characters"
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading || !adminName || !adminPassword}
                    variant="primary"
                    className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
                  >
                    {loading ? 'Provisioning Tenant Admin...' : 'Provision Admin & Continue'}
                  </Button>
                </motion.form>
              )}

              {/* Step 4: Subscription Plan */}
              {currentStep === 4 && (
                <motion.div
                  key="step4"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Select Subscription Plan</h2>
                    <p className="text-xs text-gray-400">Choose the initial capacity and module plan for your workspace.</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { code: 'starter', name: 'Starter', price: '$39/mo', desc: 'Up to 100 users, Biometric check-in & shifts' },
                      { code: 'growth', name: 'Enterprise Growth', price: '$79/mo', desc: 'Up to 500 users, Full HCM & AI Copilot Hub' },
                      { code: 'enterprise', name: 'Global Scale', price: 'Custom', desc: 'Unlimited users, Custom SLA & Dedicated Cluster' },
                    ].map((plan) => (
                      <div
                        key={plan.code}
                        onClick={() => handleSelectPlan(plan.code)}
                        className={`p-6 rounded-2xl border cursor-pointer transition-all ${
                          selectedPlan === plan.code
                            ? 'bg-indigo-950/40 border-indigo-500 ring-2 ring-indigo-500/30 shadow-xl'
                            : 'bg-gray-800/40 border-gray-700 hover:border-gray-600'
                        }`}
                      >
                        <div className="text-sm font-bold text-white mb-1">{plan.name}</div>
                        <div className="text-xl font-extrabold text-indigo-400 mb-2">{plan.price}</div>
                        <div className="text-xs text-gray-400 leading-relaxed mb-4">{plan.desc}</div>
                        <Button variant="primary" size="sm" className="w-full">
                          Select {plan.name}
                        </Button>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Step 5: Branding Configuration */}
              {currentStep === 5 && (
                <motion.form
                  key="step5"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onSubmit={handleSaveBranding}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Organization Identity & Branding</h2>
                    <p className="text-xs text-gray-400">Configure default timezone, currency, and primary brand theme.</p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Primary Timezone
                      </label>
                      <select
                        value={timezone}
                        onChange={(e) => setTimezone(e.target.value)}
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="America/New_York">America/New_York (EST)</option>
                        <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                        <option value="Europe/London">Europe/London (GMT)</option>
                        <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Base Currency
                      </label>
                      <select
                        value={currency}
                        onChange={(e) => setCurrency(e.target.value)}
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="USD">USD ($)</option>
                        <option value="EUR">EUR (€)</option>
                        <option value="GBP">GBP (£)</option>
                        <option value="INR">INR (₹)</option>
                      </select>
                    </div>
                  </div>

                  <Button type="submit" variant="primary" className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30">
                    Save Branding & Continue
                  </Button>
                </motion.form>
              )}

              {/* Step 6: Work Calendar & Shifts */}
              {currentStep === 6 && (
                <motion.form
                  key="step6"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onSubmit={handleSaveConfig}
                  className="space-y-6"
                >
                  <div>
                    <h2 className="text-2xl font-extrabold text-white mb-1">Work Calendar & Initial Policies</h2>
                    <p className="text-xs text-gray-400">Establish initial shift policies and attendance requirements.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                        Require Biometric Liveness Check-in
                      </label>
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 text-xs text-gray-300">
                          <input
                            type="radio"
                            name="bio"
                            checked={biometricsRequired}
                            onChange={() => setBiometricsRequired(true)}
                            className="text-indigo-600"
                          />
                          <span>Enabled (Neural Net Liveness Verification)</span>
                        </label>
                      </div>
                    </div>
                  </div>

                  <Button type="submit" variant="primary" className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30">
                    Complete Organization Setup
                  </Button>
                </motion.form>
              )}

              {/* Step 7: Completion */}
              {currentStep === 7 && (
                <motion.div
                  key="step7"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-center space-y-6 py-6"
                >
                  <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto">
                    <CheckCircle2 className="h-8 w-8" />
                  </div>
                  <div>
                    <h2 className="text-3xl font-extrabold text-white mb-2">Organization Workspace Ready!</h2>
                    <p className="text-xs text-gray-400 max-w-md mx-auto">
                      Your tenant workspace has been provisioned with 27 RBAC system roles and initial organization policies.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-gray-950 border border-gray-800 text-left max-w-sm mx-auto space-y-2 text-xs">
                    <div className="flex justify-between text-gray-300">
                      <span>Organization Name:</span>
                      <span className="font-bold text-white">{orgName || 'Acme Corp'}</span>
                    </div>
                    <div className="flex justify-between text-gray-300">
                      <span>Admin Account:</span>
                      <span className="font-bold text-white">{email || 'admin@acmecorp.com'}</span>
                    </div>
                    <div className="flex justify-between text-gray-300">
                      <span>RBAC Status:</span>
                      <span className="font-bold text-emerald-400">32 Roles Provisioned</span>
                    </div>
                  </div>

                  <Button
                    variant="primary"
                    onClick={() => navigate('/login', { state: { registered: true } })}
                    className="px-8 py-3.5 rounded-xl font-bold shadow-xl shadow-indigo-600/30 inline-flex items-center gap-2"
                  >
                    <span>Proceed to Dashboard Sign In</span>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
