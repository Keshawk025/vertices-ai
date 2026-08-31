"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, User } from "firebase/auth";
import Link from "next/link";
import {
  FileText,
  MessageSquare,
  Sparkles,
  ScanLine,
  HardDrive,
  UploadCloud,
  RefreshCw,
  AlertCircle,
  ArrowUpRight,
} from "lucide-react";

import { auth } from "@/lib/firebase";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import StatCard from "@/components/dashboard/StatCard";
import RecentDocuments, { DocumentItem } from "@/components/dashboard/RecentDocuments";

interface DashboardStats {
  total_documents: number;
  total_conversations: number;
  total_questions: number;
  total_ocr_documents: number;
  total_storage_bytes: number;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // 1. Listen for Firebase Auth state
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

  // 2. Fetch Stats
  const fetchStats = useCallback(async () => {
    if (!user) return;
    setLoadingStats(true);
    setError(null);

    try {
      const token = await user.getIdToken();
      const res = await fetch(`${apiUrl}/dashboard/stats`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        router.push("/login");
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed to fetch dashboard stats (${res.status})`);
      }

      const data = await res.json();
      setStats(data);
    } catch (err: any) {
      console.error("Dashboard stats fetch error:", err);
      setError("Unable to connect to Veritas AI backend service.");
    } finally {
      setLoadingStats(false);
    }
  }, [user, apiUrl, router]);

  // 3. Fetch Recent Documents
  const fetchRecentDocuments = useCallback(async () => {
    if (!user) return;
    setLoadingDocs(true);

    try {
      const token = await user.getIdToken();
      const params = new URLSearchParams();
      if (searchQuery) params.append("search", searchQuery);
      if (statusFilter) params.append("status", statusFilter);

      const url = `${apiUrl}/dashboard/recent-documents${
        params.toString() ? `?${params.toString()}` : ""
      }`;

      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        router.push("/login");
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed to fetch recent documents (${res.status})`);
      }

      const data = await res.json();
      setDocuments(data);
    } catch (err: any) {
      console.error("Recent documents fetch error:", err);
    } finally {
      setLoadingDocs(false);
    }
  }, [user, apiUrl, router, searchQuery, statusFilter]);

  // Trigger initial fetch when user is authenticated
  useEffect(() => {
    if (user) {
      fetchStats();
      fetchRecentDocuments();
    }
  }, [user, fetchStats, fetchRecentDocuments]);

  const handleRefresh = () => {
    fetchStats();
    fetchRecentDocuments();
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-400 font-medium">
            Verifying Veritas AI session...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0B0F] text-white flex">
      {/* Sidebar Navigation */}
      <Sidebar
        isOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:pl-64 min-w-0">
        {/* Top Bar Header */}
        <TopBar
          user={user}
          onToggleSidebar={() => setMobileSidebarOpen(true)}
        />

        {/* Dashboard Body */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl w-full mx-auto">
          {/* Error Banner */}
          {error && (
            <div
              data-testid="dashboard-error-banner"
              className="bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs sm:text-sm rounded-2xl p-4 flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={handleRefresh}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-semibold rounded-xl transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {/* Welcome & Quick Action Hero */}
          <div className="bg-gradient-to-r from-[#141422] via-[#16142B] to-[#12121A] border border-purple-500/20 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1 relative z-10">
              <h2 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
                Welcome, {user?.displayName || user?.email?.split("@")[0] || "User"}
              </h2>
              <p className="text-xs sm:text-sm text-purple-200/70 max-w-lg">
                Multi-document synthesis, FAISS vector embeddings, and verified RAG assistant are ready.
              </p>
            </div>

            <div className="flex items-center gap-3 relative z-10">
              <button
                type="button"
                onClick={handleRefresh}
                className="p-2.5 bg-slate-900/80 border border-slate-800 text-slate-300 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
                title="Refresh Metrics"
                aria-label="Refresh Metrics"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <Link
                href="/upload"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#7C3AED] hover:bg-[#9333EA] text-white text-xs sm:text-sm font-semibold rounded-xl shadow-lg shadow-purple-600/25 transition-all duration-200"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload Document</span>
              </Link>
            </div>
          </div>

          {/* 5 Statistics Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              title="Total Documents"
              value={stats?.total_documents ?? 0}
              subtitle="Ingested files"
              icon={FileText}
              color="purple"
              loading={loadingStats}
            />
            <StatCard
              title="Total Conversations"
              value={stats?.total_conversations ?? 0}
              subtitle="Active chat sessions"
              icon={MessageSquare}
              color="indigo"
              loading={loadingStats}
            />
            <StatCard
              title="Total Questions"
              value={stats?.total_questions ?? 0}
              subtitle="Queries evaluated"
              icon={Sparkles}
              color="fuchsia"
              loading={loadingStats}
            />
            <StatCard
              title="OCR Documents"
              value={stats?.total_ocr_documents ?? 0}
              subtitle="Scanned & OCR parsed"
              icon={ScanLine}
              color="amber"
              loading={loadingStats}
            />
            <StatCard
              title="Storage Used"
              value={formatBytes(stats?.total_storage_bytes ?? 0)}
              subtitle="Document payload"
              icon={HardDrive}
              color="emerald"
              loading={loadingStats}
            />
          </div>

          {/* Recent Documents Table & Filtering */}
          <RecentDocuments
            documents={documents}
            loading={loadingDocs}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
          />
        </main>
      </div>
    </div>
  );
}
