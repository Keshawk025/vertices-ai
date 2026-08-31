"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { User } from "firebase/auth";
import { Shield, LogOut, Menu, User as UserIcon } from "lucide-react";
import { logOut } from "@/lib/auth";

interface TopBarProps {
  user: User | null;
  onToggleSidebar?: () => void;
}

export default function TopBar({ user, onToggleSidebar }: TopBarProps) {
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await logOut();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  const getUserInitial = () => {
    if (!user) return "U";
    if (user.displayName) return user.displayName.charAt(0).toUpperCase();
    if (user.email) return user.email.charAt(0).toUpperCase();
    return "U";
  };

  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#0E0E14]/80 backdrop-blur-md sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="md:hidden p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition-colors"
            aria-label="Toggle Sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="flex items-center gap-2">
          <div className="md:hidden w-8 h-8 rounded-lg bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] flex items-center justify-center text-white shadow-md shadow-purple-600/20">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white tracking-tight">Veritas AI</h1>
            <p className="text-[10px] text-purple-400 font-medium tracking-wide uppercase hidden sm:block">
              Product Dashboard
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        {/* User Info */}
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-800">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] text-white flex items-center justify-center text-xs font-bold shadow-sm shadow-purple-600/30">
            {getUserInitial()}
          </div>
          <span className="text-xs text-slate-300 font-medium max-w-[140px] sm:max-w-[200px] truncate">
            {user?.email || "Authenticated User"}
          </span>
        </div>

        {/* Logout Action */}
        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-rose-400 px-3 py-1.5 rounded-xl border border-slate-800 hover:border-rose-500/30 hover:bg-rose-500/10 transition-all duration-200 cursor-pointer"
          title="Sign Out"
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">Sign Out</span>
        </button>
      </div>
    </header>
  );
}
