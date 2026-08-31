"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FileText,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  AlertTriangle,
  UploadCloud,
  FileCheck2,
  Layers,
} from "lucide-react";

export interface DocumentItem {
  id: string;
  filename: string;
  status: string;
  uploaded_at: string | Date;
  page_count: number;
  ocr_used: boolean;
  file_size: number;
}

interface RecentDocumentsProps {
  documents: DocumentItem[];
  loading?: boolean;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateVal: string | Date): string {
  if (!dateVal) return "Recently";
  try {
    const d = new Date(dateVal);
    if (isNaN(d.getTime())) return String(dateVal).split("T")[0] || "Recently";
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "Recently";
  }
}

export default function RecentDocuments({
  documents,
  loading = false,
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
}: RecentDocumentsProps) {
  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "processed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Processed
          </span>
        );
      case "uploaded":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
            <Clock className="w-3.5 h-3.5" />
            Uploaded
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="bg-[#12121A] border border-slate-800/80 rounded-2xl p-5 sm:p-6 shadow-xl">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#7C3AED]" />
            Recent Documents
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Ingested knowledge files and indexed vectors
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 sm:w-60 min-w-[180px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search filename..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] text-slate-100 placeholder-slate-500 rounded-xl py-2 pl-9 pr-3 text-xs outline-none transition-colors"
            />
          </div>

          {/* Status Filter */}
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              className="bg-slate-900/80 border border-slate-800 focus:border-[#7C3AED] text-slate-200 text-xs rounded-xl py-2 px-3 outline-none cursor-pointer"
            >
              <option value="">All Statuses</option>
              <option value="processed">Processed</option>
              <option value="uploaded">Uploaded</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading Skeleton */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-14 bg-slate-900/70 border border-slate-800/60 rounded-xl flex items-center justify-between px-4"
            >
              <div className="flex items-center gap-3 w-1/3">
                <div className="w-8 h-8 bg-slate-800 rounded-lg" />
                <div className="h-4 bg-slate-800 rounded w-full" />
              </div>
              <div className="h-4 bg-slate-800 rounded w-16" />
              <div className="h-4 bg-slate-800 rounded w-20" />
              <div className="h-6 bg-slate-800 rounded-full w-24" />
            </div>
          ))}
        </div>
      ) : documents.length === 0 ? (
        /* Empty State */
        <div
          data-testid="empty-documents-state"
          className="text-center py-12 px-4 border border-dashed border-slate-800 rounded-xl bg-slate-900/20"
        >
          <div className="w-12 h-12 rounded-2xl bg-purple-500/10 text-purple-400 flex items-center justify-center mx-auto mb-3">
            <UploadCloud className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">
            No documents found
          </h3>
          <p className="text-xs text-slate-400 max-w-xs mx-auto mt-1 mb-4">
            {searchQuery || statusFilter
              ? "No files match your search criteria."
              : "Upload your first PDF document to begin multi-document analysis and RAG retrieval."}
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl bg-[#7C3AED] hover:bg-[#9333EA] text-white shadow-md shadow-purple-600/20 transition-colors"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Document</span>
          </Link>
        </div>
      ) : (
        /* Documents Table / Responsive List */
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800/80 bg-slate-900/40">
              <tr>
                <th className="py-3 px-4 rounded-l-xl">Document</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">Pages</th>
                <th className="py-3 px-4">OCR</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 rounded-r-xl">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  className="hover:bg-slate-900/40 transition-colors"
                >
                  <td className="py-3.5 px-4 font-medium text-white flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <span className="truncate max-w-[200px] sm:max-w-xs" title={doc.filename}>
                      {doc.filename}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                    {formatBytes(doc.file_size)}
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-slate-500" />
                      {doc.page_count}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    {doc.ocr_used ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-400/10 border border-amber-400/30 px-2 py-0.5 rounded-full">
                        OCR
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 bg-slate-800/60 border border-slate-700/60 px-2 py-0.5 rounded-full">
                        Native
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    {getStatusBadge(doc.status)}
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                    {formatDate(doc.uploaded_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
