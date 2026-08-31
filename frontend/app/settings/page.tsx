"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import {
  Settings,
  Shield,
  User as UserIcon,
  Mail,
  Server,
  Database,
  Key,
  CheckCircle2,
  Loader2,
} from "lucide-react";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Auth guard
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      if (currentUser) {
        setUser(currentUser);
        setAuthChecking(false);
      } else {
        setUser(null);
        setAuthChecking(false);
        router.push("/login");
      }
    });

    return () => unsubscribe();
  }, [router]);

  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center text-white">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-[#7C3AED] animate-spin" />
          <span className="text-sm font-medium text-slate-400">Loading Veritas AI...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0B0F] flex text-slate-100 font-sans">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col md:pl-64 min-w-0">
        <TopBar user={user} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-5xl w-full mx-auto space-y-6">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Settings & Configuration
            </h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Manage your Veritas AI account and connected service endpoints.
            </p>
          </div>

          {/* Account Profile Card */}
          <div className="bg-[#12121A] border border-purple-500/20 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-purple-600/30">
                {user?.email?.charAt(0).toUpperCase() || "U"}
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold text-white">
                  {user?.displayName || user?.email?.split("@")[0] || "User"}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">{user?.email}</p>
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 mt-2 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-semibold border border-emerald-500/30">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Authenticated via Firebase</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-slate-800/80">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                  User ID (UID)
                </span>
                <span className="text-xs font-mono text-slate-300 break-all">
                  {user?.uid || "N/A"}
                </span>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">
                  Auth Provider
                </span>
                <span className="text-xs text-slate-300">
                  {user?.providerData?.[0]?.providerId || "firebase/password"}
                </span>
              </div>
            </div>
          </div>

          {/* System & API Configuration Card */}
          <div className="bg-[#12121A] border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Connected Infrastructure
            </h3>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="flex items-center gap-3">
                  <Server className="w-4 h-4 text-purple-400" />
                  <div>
                    <p className="text-xs font-semibold text-white">Backend API Server</p>
                    <p className="text-[11px] font-mono text-slate-400">{apiUrl}</p>
                  </div>
                </div>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  Active
                </span>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="flex items-center gap-3">
                  <Database className="w-4 h-4 text-indigo-400" />
                  <div>
                    <p className="text-xs font-semibold text-white">Firebase Project</p>
                    <p className="text-[11px] font-mono text-slate-400">
                      {process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "veritas-ai-a08ec"}
                    </p>
                  </div>
                </div>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                  Connected
                </span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
