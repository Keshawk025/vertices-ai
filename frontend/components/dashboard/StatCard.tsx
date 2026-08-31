"use client";

import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  color?: "purple" | "indigo" | "fuchsia" | "emerald" | "amber";
  loading?: boolean;
}

const colorMap = {
  purple: {
    bg: "from-[#7C3AED]/20 to-[#9333EA]/10",
    border: "border-purple-500/20",
    text: "text-purple-400",
    iconBg: "bg-purple-500/20 text-purple-300",
  },
  indigo: {
    bg: "from-indigo-600/20 to-blue-600/10",
    border: "border-indigo-500/20",
    text: "text-indigo-400",
    iconBg: "bg-indigo-500/20 text-indigo-300",
  },
  fuchsia: {
    bg: "from-fuchsia-600/20 to-pink-600/10",
    border: "border-fuchsia-500/20",
    text: "text-fuchsia-400",
    iconBg: "bg-fuchsia-500/20 text-fuchsia-300",
  },
  emerald: {
    bg: "from-emerald-600/20 to-teal-600/10",
    border: "border-emerald-500/20",
    text: "text-emerald-400",
    iconBg: "bg-emerald-500/20 text-emerald-300",
  },
  amber: {
    bg: "from-amber-600/20 to-orange-600/10",
    border: "border-amber-500/20",
    text: "text-amber-400",
    iconBg: "bg-amber-500/20 text-amber-300",
  },
};

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = "purple",
  loading = false,
}: StatCardProps) {
  const styles = colorMap[color];

  if (loading) {
    return (
      <div className="bg-[#12121A] border border-slate-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden animate-pulse">
        <div className="flex items-center justify-between mb-3">
          <div className="h-3.5 bg-slate-800 rounded w-28" />
          <div className="w-10 h-10 bg-slate-800 rounded-xl" />
        </div>
        <div className="h-7 bg-slate-800 rounded w-20 mb-2" />
        <div className="h-3 bg-slate-800/60 rounded w-32" />
      </div>
    );
  }

  return (
    <div
      className={`bg-[#12121A] border ${styles.border} bg-gradient-to-br ${styles.bg} rounded-2xl p-5 shadow-lg transition-all duration-200 hover:border-purple-500/40`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          {title}
        </span>
        <div
          className={`w-10 h-10 rounded-xl ${styles.iconBg} flex items-center justify-center shadow-inner`}
        >
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
        {value}
      </div>
      {subtitle && (
        <p className="text-xs text-slate-400 mt-1 font-medium">{subtitle}</p>
      )}
    </div>
  );
}
