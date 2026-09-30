import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, ArrowRight, ArrowLeft, Building2, CheckCircle2, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { authService } from "../services/authService";
import { Button, Input, Card, CardContent } from "../components/ui";
import { useAuthStore } from "../store/authStore";

export default function SignupPage() {
  const navigate = useNavigate();
  const { isAuthenticated, isHydrated } = useAuthStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    role: "Admin",
    organization: "",
    department: "",
    city: "",
  });

  const updateField = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError("");
  };

  // Same guard as LoginPage: a signed-in visitor landing here (e.g. via the
  // browser Back button) must be sent to their workspace, not shown a
  // registration form for a tenant they already belong to.
  useEffect(() => {
    if (isHydrated && isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isHydrated, isAuthenticated, navigate]);

  const passwordStrength = (pwd) => {
    let score = 0;
    if (pwd.length >= 8) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[^A-Za-z0-9]/.test(pwd)) score++;
    return score;
  };

  const strength = passwordStrength(formData.password);
  const strengthLabels = ["Weak", "Fair", "Good", "Strong"];
  const strengthColors = ["bg-red-500", "bg-amber-500", "bg-indigo-500", "bg-emerald-500"];

  const handleSignup = async (e) => {
    e.preventDefault();
    if (step === 1) {
      setStep(2);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        role: formData.role,
        organization: formData.organization,
        department: formData.department || undefined,
        city: formData.city || undefined,
      };
      await authService.register(payload);
      navigate("/login", { state: { registered: true } });
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed. Please verify input.");
    } finally {
      setLoading(false);
    }
  };

  const canProceedStep1 = formData.name && formData.email && formData.password && strength >= 2;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center px-4 py-12 font-sans relative overflow-hidden">
      {/* Background Ambient Light */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[450px] bg-purple-600/15 rounded-full blur-[130px] pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <Link to="/" className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-extrabold tracking-tight text-white">
              VisionCore
            </span>
          </Link>
        </div>

        {/* Card */}
        <Card className="bg-gray-900/90 border-gray-800 shadow-2xl backdrop-blur-xl">
          <CardContent className="p-8">
            <div className="mb-6">
              <div className="flex items-center justify-between">
                <h1 className="text-2xl font-extrabold text-white">
                  Create Workspace
                </h1>
                <Link to="/onboarding" className="text-xs font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                  <Building2 className="h-3.5 w-3.5" />
                  <span>Onboarding Wizard</span>
                </Link>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Step {step} of 2 — {step === 1 ? "Administrator credentials" : "Organization workspace"}
              </p>

              {/* Progress Bar */}
              <div className="w-full bg-gray-800 rounded-full h-1.5 mt-3 overflow-hidden">
                <div
                  className="bg-indigo-500 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: step === 1 ? "50%" : "100%" }}
                />
              </div>
            </div>

            {error && (
              <div className="mb-6 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-xs text-red-400 font-medium flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSignup} className="space-y-4">
              {step === 1 ? (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => updateField("name", e.target.value)}
                      placeholder="Jane Doe"
                      required
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => updateField("email", e.target.value)}
                      placeholder="jane@company.com"
                      required
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => updateField("password", e.target.value)}
                      placeholder="Min. 8 characters"
                      required
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                    {formData.password && (
                      <div className="mt-2">
                        <div className="flex gap-1.5 h-1.5">
                          {[0, 1, 2, 3].map((i) => (
                            <div
                              key={i}
                              className={`flex-1 rounded-full transition-colors ${
                                i < strength ? strengthColors[strength - 1] : "bg-gray-800"
                              }`}
                            />
                          ))}
                        </div>
                        <p className="mt-1 text-[11px] text-gray-400">
                          Strength: {strengthLabels[strength - 1] || "Too weak"}
                        </p>
                      </div>
                    )}
                  </div>

                  <Button
                    type="submit"
                    disabled={!canProceedStep1}
                    variant="primary"
                    className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 mt-4"
                  >
                    <span>Continue Workspace Setup</span>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Organization Name
                    </label>
                    <input
                      type="text"
                      value={formData.organization}
                      onChange={(e) => updateField("organization", e.target.value)}
                      placeholder="Acme Global Inc"
                      required
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      Department <span className="text-gray-500 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={formData.department}
                      onChange={(e) => updateField("department", e.target.value)}
                      placeholder="Engineering / Operations"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                      City Location <span className="text-gray-500 font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => updateField("city", e.target.value)}
                      placeholder="San Francisco"
                      className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="flex gap-3 pt-3">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setStep(1)}
                      className="flex-1 py-3 rounded-xl font-semibold border border-gray-800"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      Back
                    </Button>
                    <Button
                      type="submit"
                      disabled={loading}
                      variant="primary"
                      className="flex-1 py-3 rounded-xl font-bold shadow-lg shadow-indigo-600/30"
                    >
                      {loading ? "Creating..." : "Create Account"}
                    </Button>
                  </div>
                </>
              )}
            </form>

            <div className="mt-8 text-center pt-6 border-t border-gray-800 text-xs text-gray-400">
              Already have an account?{" "}
              <Link to="/login" className="font-bold text-indigo-400 hover:text-indigo-300">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
