"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import RecentDocuments, { DocumentItem } from "@/components/dashboard/RecentDocuments";
import {
  FileText,
  UploadCloud,
  Loader2,
  RefreshCw,
  Search,
  Filter,
} from "lucide-react";

export default function DocumentsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

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

  const fetchDocuments = useCallback(async () => {
    if (!user) return;
    setLoadingDocs(true);
    setError(null);

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
        throw new Error(`Failed to fetch documents (${res.status})`);
      }

      const data = await res.json();
      setDocuments(data);
    } catch (err: any) {
      console.error("Documents fetch error:", err);
      setError("Unable to load documents from backend.");
    } finally {
      setLoadingDocs(false);
    }
  }, [user, apiUrl, router, searchQuery, statusFilter]);

  useEffect(() => {
    if (user) {
      fetchDocuments();
    }
  }, [user, fetchDocuments]);

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

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Document Repository
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 mt-1">
                Manage, search, and monitor all ingested PDFs in your knowledge base.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={fetchDocuments}
                className="p-2.5 bg-slate-900/80 border border-slate-800 text-slate-300 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>

              <Link
                href="/upload"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#7C3AED] hover:bg-[#9333EA] text-white text-xs sm:text-sm font-semibold rounded-xl shadow-lg shadow-purple-600/25 transition-all"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload Document</span>
              </Link>
            </div>
          </div>

          {/* Documents Component with Filters */}
          <RecentDocuments
            documents={documents}
            loading={loadingDocs}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            onRefresh={fetchDocuments}
          />
        </main>
      </div>
    </div>
  );
}
