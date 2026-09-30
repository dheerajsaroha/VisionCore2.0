import React, { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Eye, EyeOff, ShieldCheck, ArrowRight, Lock, Mail, AlertCircle, CheckCircle2 } from "lucide-react";
import { useAuthStore } from "../store/authStore";
import { Button, Input, Card, CardContent } from "../components/ui";
import { useTheme } from "../hooks/useTheme";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  // Set only when the backend reports the address has accounts in more than
  // one organisation, which is the single case it cannot resolve on its own.
  const [orgChoices, setOrgChoices] = useState(null);
  const [organization, setOrganization] = useState("");

  const { login, isLoading, isAuthenticated, isHydrated } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme } = useTheme();

  const from = location.state?.from?.pathname || "/dashboard";
  const resetSuccess = location.state?.reset;

  // An authenticated visitor must never be left on the sign-in form. This is
  // reachable in normal use: the browser Back button returns to /login after a
  // successful login, and the previous history entry is this page. Guard on
  // isHydrated so the redirect does not fire before an existing session has
  // finished restoring, which would bounce a signed-in user to /login.
  useEffect(() => {
    if (isHydrated && isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isHydrated, isAuthenticated, from, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await login(email, password, organization || undefined);
      navigate(from, { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      // 409: the same address exists in several organisations and the password
      // works for more than one of them. Ask rather than guess -- picking the
      // wrong tenant would sign the user into somebody else's account view.
      if (err.response?.status === 409 && detail?.organizations) {
        setOrgChoices(detail.organizations);
        setOrganization((current) => current || detail.organizations[0]);
        setError(detail.message || "Select the organisation to sign in to.");
        return;
      }
      setError(
        typeof detail === "string"
          ? detail
          : "Invalid email or password. Please try again."
      );
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center px-4 py-12 font-sans relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[450px] bg-indigo-600/15 rounded-full blur-[130px] pointer-events-none" />

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
            <div className="text-center mb-6">
              <h1 className="text-2xl font-extrabold text-white mb-2">
                Sign in to Organization
              </h1>
              <p className="text-gray-400 text-sm">
                Enter your credentials to access your multi-tenant workspace.
              </p>
            </div>

            {/* Reset Success Notice */}
            {resetSuccess && (
              <div className="mb-6 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-xs text-emerald-400 font-medium flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Your password has been reset successfully. Please sign in with your new password.</span>
              </div>
            )}

            {/* Error Notice */}
            {error && (
              <div className="mb-6 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-xs text-red-400 font-medium flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      // A new address invalidates the tenant picked for the
                      // previous one, so the prompt starts over.
                      setOrgChoices(null);
                      setOrganization("");
                    }}
                    placeholder="you@company.com"
                    required
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pl-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  />
                  <Mail className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                </div>
              </div>

              {/* Shown only when the backend reports the address belongs to
                  several organisations, which it cannot disambiguate. */}
              {orgChoices && (
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-300 mb-2">
                    Organisation
                  </label>
                  <select
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  >
                    {orgChoices.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-gray-300">
                    Password
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pl-10 pr-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  />
                  <Lock className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3.5 text-gray-400 hover:text-white transition-colors"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-400">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-700 bg-gray-800 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Keep me signed in</span>
                </label>
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                variant="primary"
                className="w-full py-3.5 rounded-xl font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  "Authenticating..."
                ) : (
                  <>
                    <span>Sign In to Dashboard</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>

            <div className="mt-8 text-center pt-6 border-t border-gray-800 text-xs text-gray-400">
              Need a new workspace?{" "}
              <Link to="/signup" className="font-bold text-indigo-400 hover:text-indigo-300">
                Create Organization
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
