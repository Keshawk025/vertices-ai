import Link from "next/link";
import { Shield, ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center p-6 text-white font-sans relative overflow-hidden">
      {/* Background Radial Glow Effects */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-[#7C3AED]/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-[#9333EA]/20 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-xl text-center space-y-6 relative z-10">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] flex items-center justify-center text-white shadow-xl shadow-purple-600/30 mx-auto">
          <Shield className="w-8 h-8" />
        </div>
        <h1 className="text-4xl font-extrabold bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-transparent sm:text-5xl">
          Veritas AI
        </h1>
        <p className="text-sm font-semibold tracking-widest text-purple-300/80 uppercase">
          Intelligent Multi-Document Assistant
        </p>
        <p className="text-slate-400 text-sm sm:text-base leading-relaxed max-w-md mx-auto">
          Securely analyze, query, and synthesize insights from your document repository using advanced hybrid search and verified retrieval.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <Link
            href="/login"
            className="w-full sm:w-auto px-8 py-3 bg-[#7C3AED] hover:bg-[#9333EA] text-white font-semibold rounded-xl shadow-lg shadow-purple-600/30 flex items-center justify-center gap-2 transition-all duration-200"
          >
            <span>Sign In</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/register"
            className="w-full sm:w-auto px-8 py-3 border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 text-slate-200 font-semibold rounded-xl transition-all duration-200 flex items-center justify-center"
          >
            <span>Create Account</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
