"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowLeft,
  X,
  Layers,
  Sparkles,
  ShieldCheck,
  File,
} from "lucide-react";

export default function UploadPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<{
    file_id: string;
    filename: string;
    size: number;
    status: string;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (file: File) => {
    setError(null);
    setSuccessData(null);

    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setError("Only PDF files are supported for intelligent ingestion.");
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setError("File size exceeds the 20 MB limit.");
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !user) return;

    setUploading(true);
    setError(null);
    setSuccessData(null);
    setUploadStep("Uploading file to secure repository...");

    try {
      const token = await user.getIdToken();
      const formData = new FormData();
      formData.append("file", selectedFile);

      setUploadStep("Parsing PDF, generating vector embeddings & indexing in FAISS...");

      const response = await fetch(`${apiUrl}/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.status === 401) {
        router.push("/login");
        return;
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed with status ${response.status}`);
      }

      const result = await response.json();
      setSuccessData(result);
      setSelectedFile(null);
    } catch (err: any) {
      console.error("Upload error:", err);
      setError(err.message || "Failed to upload and process the document.");
    } finally {
      setUploading(false);
      setUploadStep("");
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

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
          {/* Back to Dashboard Link & Title */}
          <div className="flex items-center justify-between">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-purple-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Dashboard</span>
            </Link>
          </div>

          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Upload & Ingest Document
            </h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Upload PDF documents for automatic OCR, chunking, and FAISS vector indexing.
            </p>
          </div>

          {/* Success Banner */}
          {successData && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in duration-200">
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-sm sm:text-base font-bold text-white">
                    Document Ingested Successfully!
                  </h3>
                  <p className="text-xs text-emerald-300/80 mt-1">
                    <span className="font-semibold text-white">{successData.filename}</span> ({formatFileSize(successData.size)}) is processed and ready for querying.
                  </p>
                  <div className="flex items-center gap-2 mt-2 text-[11px] text-slate-300">
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Status: {successData.status}
                    </span>
                    <span className="text-slate-500">•</span>
                    <span>ID: {successData.file_id.slice(0, 8)}...</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => setSuccessData(null)}
                  className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-200 text-xs font-semibold rounded-xl transition-colors cursor-pointer"
                >
                  Upload Another
                </button>
                <Link
                  href="/dashboard"
                  className="px-4 py-2 bg-[#7C3AED] hover:bg-[#9333EA] text-white text-xs font-semibold rounded-xl shadow-md shadow-purple-600/30 transition-colors"
                >
                  View in Dashboard
                </Link>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-2xl p-4 sm:p-5 shadow-xl flex items-start gap-3 animate-in fade-in duration-200">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1 text-xs sm:text-sm">
                <span className="font-semibold block mb-0.5">Upload Error</span>
                {error}
              </div>
            </div>
          )}

          {/* Upload Card */}
          <div className="bg-[#12121A] border border-purple-500/20 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6">
            {/* Drag & Drop Zone */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all duration-200 cursor-pointer flex flex-col items-center justify-center ${
                dragActive
                  ? "border-[#7C3AED] bg-purple-500/10 scale-[1.01]"
                  : "border-slate-800 hover:border-purple-500/50 hover:bg-slate-900/40 bg-slate-900/20"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileChange}
                className="hidden"
                disabled={uploading}
              />

              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#7C3AED]/20 to-[#9333EA]/20 border border-purple-500/30 text-[#7C3AED] flex items-center justify-center shadow-lg shadow-purple-600/20 mb-4">
                <UploadCloud className="w-8 h-8 text-purple-300" />
              </div>

              <h3 className="text-base sm:text-lg font-bold text-white mb-1">
                Drag and drop your PDF document here
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 max-w-sm mb-4">
                or click anywhere in this area to browse and select a file from your device
              </p>

              <div className="flex items-center gap-2 text-[11px] text-slate-500 font-medium bg-slate-900/80 px-3 py-1.5 rounded-full border border-slate-800">
                <span>Supported: PDF documents</span>
                <span>•</span>
                <span>Max size: 20 MB</span>
              </div>
            </div>

            {/* Selected File Card */}
            {selectedFile && (
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-3 animate-in fade-in duration-200">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-[#7C3AED]/20 text-[#7C3AED] flex items-center justify-center shrink-0">
                    <File className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white truncate">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-slate-400">
                      {formatFileSize(selectedFile.size)}
                    </p>
                  </div>
                </div>

                {!uploading && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition-colors"
                    title="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            )}

            {/* Ingestion Steps / Progress Indicator */}
            {uploading && (
              <div className="bg-purple-950/20 border border-purple-500/30 rounded-xl p-4 space-y-3 animate-in fade-in duration-200">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 text-[#7C3AED] animate-spin shrink-0" />
                  <span className="text-xs sm:text-sm font-semibold text-purple-200">
                    {uploadStep || "Processing..."}
                  </span>
                </div>
                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                  <div className="bg-gradient-to-r from-[#7C3AED] to-[#9333EA] h-full rounded-full animate-pulse w-3/4" />
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <Link
                href="/dashboard"
                className="px-5 py-2.5 rounded-xl border border-slate-800 hover:bg-slate-800/60 text-slate-300 text-xs sm:text-sm font-semibold transition-colors"
              >
                Cancel
              </Link>
              <button
                type="button"
                onClick={handleUpload}
                disabled={!selectedFile || uploading}
                className="px-6 py-2.5 bg-[#7C3AED] hover:bg-[#9333EA] text-white text-xs sm:text-sm font-semibold rounded-xl shadow-lg shadow-purple-600/30 transition-all duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing Document...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4" />
                    <span>Start Ingestion</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Features / Info Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="bg-[#12121A]/60 border border-slate-800/80 rounded-xl p-4 flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center shrink-0 mt-0.5">
                <Layers className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-200">Hierarchical Chunking</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  500-token chunks with 100-token overlap for optimal contextual retrieval.
                </p>
              </div>
            </div>

            <div className="bg-[#12121A]/60 border border-slate-800/80 rounded-xl p-4 flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-200">FAISS Vector Store</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Dense 384-d MiniLM embeddings for instant multi-document semantic search.
                </p>
              </div>
            </div>

            <div className="bg-[#12121A]/60 border border-slate-800/80 rounded-xl p-4 flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-200">Dual Persistence</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Automatic sync across SQLite database and Firebase Cloud Storage.
                </p>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
