"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Shield,
  Mail,
  Lock,
  User,
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
} from "lucide-react";
import {
  signUpWithEmail,
  logInWithEmail,
  logInWithGoogle,
} from "@/lib/auth";

export interface AuthFormProps {
  type: "login" | "register";
}

function formatFirebaseError(error: any): string {
  if (!error) return "An unknown error occurred.";
  const errorCode = error.code || "";

  switch (errorCode) {
    case "auth/invalid-credential":
    case "auth/user-not-found":
    case "auth/wrong-password":
      return "Invalid email or password. Please check your credentials.";
    case "auth/email-already-in-use":
      return "An account with this email address already exists.";
    case "auth/weak-password":
      return "Password is too weak. Please use at least 8 characters.";
    case "auth/invalid-email":
      return "Please provide a valid email address.";
    case "auth/popup-closed-by-user":
      return "Google sign-in popup was closed before completing.";
    case "auth/popup-blocked":
      return "Sign-in popup was blocked by your browser.";
    case "auth/too-many-requests":
      return "Too many failed attempts. Please try again later.";
    case "auth/network-request-failed":
      return "Network error. Please check your internet connection.";
    default:
      return error.message || "Authentication failed. Please try again.";
  }
}

export default function AuthForm({ type }: AuthFormProps) {
  const router = useRouter();
  const isRegister = type === "register";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const validateForm = (): boolean => {
    setError(null);

    if (isRegister && (!name || name.trim().length < 2)) {
      setError("Please enter your full name (at least 2 characters).");
      return false;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email.trim())) {
      setError("Please enter a valid email address.");
      return false;
    }

    if (!password || password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return false;
    }

    if (isRegister && password !== confirmPassword) {
      setError("Passwords do not match.");
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (isRegister) {
        await signUpWithEmail(email.trim(), password);
        setSuccess("Account created successfully! Redirecting to dashboard...");
      } else {
        await logInWithEmail(email.trim(), password);
        setSuccess("Login successful! Redirecting to dashboard...");
      }

      setTimeout(() => {
        router.push("/dashboard");
      }, 1000);
    } catch (err: any) {
      setError(formatFirebaseError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await logInWithGoogle();
      setSuccess("Authenticated with Google! Redirecting to dashboard...");

      setTimeout(() => {
        router.push("/dashboard");
      }, 1000);
    } catch (err: any) {
      setError(formatFirebaseError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden text-white font-sans">
      {/* Background Radial Glow Effects */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-[#7C3AED]/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-[#9333EA]/20 rounded-full blur-3xl pointer-events-none" />

      {/* Main Glassmorphic Auth Card */}
      <div className="w-full max-w-md bg-[#12121A]/90 backdrop-blur-xl border border-purple-500/20 rounded-2xl p-6 sm:p-8 shadow-2xl shadow-purple-950/40 relative z-10">
        {/* Branding Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] flex items-center justify-center text-white shadow-lg shadow-purple-600/30 mb-3 mx-auto">
            <Shield className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-transparent">
            Veritas AI
          </h1>
          <p className="text-xs text-purple-300/70 font-medium tracking-wide uppercase mt-1">
            Intelligent Multi-Document Assistant
          </p>
          <h2 className="text-lg font-semibold text-slate-200 mt-4">
            {isRegister ? "Create Your Account" : "Welcome Back"}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {isRegister
              ? "Sign up to start retrieving intelligent document insights"
              : "Sign in to access your documents and conversations"}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            data-testid="error-banner"
            className="mb-5 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs sm:text-sm rounded-xl p-3.5 flex items-start gap-3 animate-in fade-in duration-200"
          >
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">{error}</div>
          </div>
        )}

        {/* Success Alert */}
        {success && (
          <div
            data-testid="success-banner"
            className="mb-5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs sm:text-sm rounded-xl p-3.5 flex items-start gap-3 animate-in fade-in duration-200"
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="flex-1">{success}</div>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name Field (Register Mode Only) */}
          {isRegister && (
            <div>
              <label
                htmlFor="name-input"
                className="block text-xs font-medium text-slate-300 mb-1.5"
              >
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  id="name-input"
                  type="text"
                  placeholder="John Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                  className="w-full bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] text-slate-100 placeholder-slate-500 rounded-xl py-2.5 pl-10 pr-4 text-sm transition-all duration-200 outline-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          {/* Email Field */}
          <div>
            <label
              htmlFor="email-input"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                id="email-input"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="w-full bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] text-slate-100 placeholder-slate-500 rounded-xl py-2.5 pl-10 pr-4 text-sm transition-all duration-200 outline-none disabled:opacity-50"
              />
            </div>
          </div>

          {/* Password Field */}
          <div>
            <label
              htmlFor="password-input"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                id="password-input"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                className="w-full bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] text-slate-100 placeholder-slate-500 rounded-xl py-2.5 pl-10 pr-10 text-sm transition-all duration-200 outline-none disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Confirm Password Field (Register Mode Only) */}
          {isRegister && (
            <div>
              <label
                htmlFor="confirm-password-input"
                className="block text-xs font-medium text-slate-300 mb-1.5"
              >
                Confirm Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  id="confirm-password-input"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={loading}
                  className="w-full bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] text-slate-100 placeholder-slate-500 rounded-xl py-2.5 pl-10 pr-4 text-sm transition-all duration-200 outline-none disabled:opacity-50"
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 bg-[#7C3AED] hover:bg-[#9333EA] text-white font-semibold py-3 rounded-xl shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 transition-all duration-200 text-sm disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed group"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <span>{isRegister ? "Sign Up" : "Sign In"}</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="relative my-6 text-center text-xs">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-800" />
          </div>
          <span className="relative bg-[#12121A] px-3 text-slate-500 font-medium">
            or continue with
          </span>
        </div>

        {/* Google Sign In Button */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={loading}
          className="w-full border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 text-slate-200 font-medium py-2.5 rounded-xl flex items-center justify-center gap-3 transition-all duration-200 text-sm disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#EA4335"
              d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.3 9 5 12 5z"
            />
            <path
              fill="#4285F4"
              d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
            />
            <path
              fill="#FBBC05"
              d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 10.8 0 12.5s.7 2.8 1.9 5.2l3.7-2.9z"
            />
            <path
              fill="#34A853"
              d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.3-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z"
            />
          </svg>
          <span>Google</span>
        </button>

        {/* Toggle Mode Footer */}
        <div className="mt-6 text-center text-xs text-slate-400">
          {isRegister ? (
            <>
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-[#7C3AED] hover:text-[#9333EA] font-semibold underline underline-offset-4 transition-colors"
              >
                Sign in
              </Link>
            </>
          ) : (
            <>
              Don't have an account?{" "}
              <Link
                href="/register"
                className="text-[#7C3AED] hover:text-[#9333EA] font-semibold underline underline-offset-4 transition-colors"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
