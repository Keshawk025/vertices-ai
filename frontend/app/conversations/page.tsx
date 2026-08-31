"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import {
  MessageSquare,
  Plus,
  Send,
  Loader2,
  Trash2,
  Bot,
  User as UserIcon,
  BookOpen,
  Sparkles,
  AlertCircle,
  Clock,
  Shield,
  FileText,
} from "lucide-react";

interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  citations?: Array<{ page?: number; chunk_id?: string }>;
}

export default function ConversationsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputQuery, setInputQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

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

  // Fetch list of conversations
  const fetchConversations = useCallback(async () => {
    if (!user) return;
    setLoadingConversations(true);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${apiUrl}/conversations`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        router.push("/login");
        return;
      }

      if (res.ok) {
        const data: Conversation[] = await res.json();
        setConversations(data);
        if (data.length > 0 && !activeConversationId) {
          setActiveConversationId(data[0].id);
        }
      }
    } catch (err: any) {
      console.error("Error fetching conversations:", err);
    } finally {
      setLoadingConversations(false);
    }
  }, [user, apiUrl, router, activeConversationId]);

  // Fetch history for selected conversation
  const fetchHistory = useCallback(async (convId: string) => {
    if (!user || !convId) return;
    setLoadingHistory(true);
    setError(null);

    try {
      const token = await user.getIdToken();
      const res = await fetch(`${apiUrl}/conversations/${convId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        router.push("/login");
        return;
      }

      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      } else {
        throw new Error("Failed to load conversation history.");
      }
    } catch (err: any) {
      console.error("History error:", err);
      setError(err.message || "Failed to load conversation history.");
    } finally {
      setLoadingHistory(false);
    }
  }, [user, apiUrl, router]);

  useEffect(() => {
    if (user) {
      fetchConversations();
    }
  }, [user, fetchConversations]);

  useEffect(() => {
    if (activeConversationId) {
      fetchHistory(activeConversationId);
    }
  }, [activeConversationId, fetchHistory]);

  // Create new conversation
  const handleNewConversation = async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const title = `Chat ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
      const res = await fetch(`${apiUrl}/conversations`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title }),
      });

      if (res.ok) {
        const newConv: Conversation = await res.json();
        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(newConv.id);
        setMessages([]);
      }
    } catch (err: any) {
      console.error("New conversation error:", err);
    }
  };

  // Send message
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || !user || sending) return;

    let targetConvId = activeConversationId;

    // Auto-create conversation if none exists
    if (!targetConvId) {
      try {
        const token = await user.getIdToken();
        const title = inputQuery.slice(0, 30);
        const res = await fetch(`${apiUrl}/conversations`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ title }),
        });
        if (res.ok) {
          const newConv: Conversation = await res.json();
          setConversations((prev) => [newConv, ...prev]);
          targetConvId = newConv.id;
          setActiveConversationId(newConv.id);
        } else {
          return;
        }
      } catch (err) {
        console.error("Auto-create conv error:", err);
        return;
      }
    }

    const query = inputQuery.trim();
    setInputQuery("");
    setError(null);

    // Optimistically add user message
    const optimisticMsg: Message = {
      role: "user",
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMsg]);
    setSending(true);

    try {
      const token = await user.getIdToken();
      const res = await fetch(`${apiUrl}/conversations/${targetConvId}/message`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ content: query }),
      });

      if (!res.ok) {
        throw new Error(`Failed to generate answer (${res.status})`);
      }

      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.answer || "No response received.",
        citations: data.citations || [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      console.error("Send message error:", err);
      setError(err.message || "Failed to process question through RAG service.");
    } finally {
      setSending(false);
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!user) return;

    try {
      const token = await user.getIdToken();
      const res = await fetch(`${apiUrl}/conversations/${convId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const remaining = conversations.filter((c) => c.id !== convId);
        setConversations(remaining);
        if (activeConversationId === convId) {
          if (remaining.length > 0) {
            setActiveConversationId(remaining[0].id);
          } else {
            setActiveConversationId(null);
            setMessages([]);
          }
        }
      }
    } catch (err) {
      console.error("Delete conversation error:", err);
    }
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

      <div className="flex-1 flex flex-col md:pl-64 min-w-0 h-screen overflow-hidden">
        <TopBar user={user} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 flex min-h-0 overflow-hidden">
          {/* Conversation List Sidebar */}
          <div className="w-80 bg-[#0E0E14] border-r border-slate-800/80 flex flex-col hidden lg:flex">
            {/* Header */}
            <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-bold text-white">Sessions</span>
              </div>
              <button
                type="button"
                onClick={handleNewConversation}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#7C3AED] hover:bg-[#9333EA] text-white text-xs font-semibold rounded-xl shadow-md shadow-purple-600/25 transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Chat</span>
              </button>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
              {loadingConversations ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <MessageSquare className="w-8 h-8 text-slate-600 mx-auto mb-2 opacity-50" />
                  <p className="text-xs text-slate-400">No chat sessions yet.</p>
                  <button
                    type="button"
                    onClick={handleNewConversation}
                    className="mt-3 text-xs text-purple-400 hover:text-purple-300 font-semibold underline underline-offset-2"
                  >
                    Start a session
                  </button>
                </div>
              ) : (
                conversations.map((conv) => {
                  const isActive = conv.id === activeConversationId;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => setActiveConversationId(conv.id)}
                      className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all duration-150 ${
                        isActive
                          ? "bg-[#7C3AED]/15 border border-[#7C3AED]/30 text-white shadow-sm"
                          : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <MessageSquare
                          className={`w-4 h-4 shrink-0 ${
                            isActive ? "text-[#7C3AED]" : "text-slate-500"
                          }`}
                        />
                        <span className="text-xs font-medium truncate">
                          {conv.title || "Untitled Chat"}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 rounded-md transition-opacity"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Main Chat Interface */}
          <div className="flex-1 flex flex-col min-w-0 bg-[#0B0B0F]">
            {/* Chat Top Banner */}
            <div className="h-14 border-b border-slate-800/80 px-4 sm:px-6 flex items-center justify-between bg-[#12121A]/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#7C3AED] to-[#9333EA] flex items-center justify-center text-white shadow-sm">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-xs sm:text-sm font-bold text-white">
                    Veritas AI RAG Assistant
                  </h2>
                  <p className="text-[10px] text-purple-300/70">
                    Dense FAISS Vector Search & Self-Correcting Synthesis
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleNewConversation}
                className="lg:hidden flex items-center gap-1 px-3 py-1.5 bg-[#7C3AED] text-white text-xs font-semibold rounded-xl"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New</span>
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mx-4 sm:mx-6 mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{error}</span>
              </div>
            )}

            {/* Message Feed */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
              {loadingHistory ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-8 h-8 text-[#7C3AED] animate-spin" />
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto space-y-4">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#7C3AED]/20 to-[#9333EA]/20 border border-purple-500/30 flex items-center justify-center text-[#7C3AED] shadow-xl shadow-purple-600/20">
                    <BookOpen className="w-7 h-7" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">
                      Ask Questions Across Your Documents
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Veritas AI indexes your PDFs into vector representations and answers queries with verified source citations.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-2">
                    <button
                      type="button"
                      onClick={() => setInputQuery("Summarize the key points of the uploaded documents.")}
                      className="p-3 bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 rounded-xl text-left text-xs text-slate-300 transition-colors"
                    >
                      "Summarize the key points of the documents."
                    </button>
                    <button
                      type="button"
                      onClick={() => setInputQuery("What are the main findings and conclusions?")}
                      className="p-3 bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 rounded-xl text-left text-xs text-slate-300 transition-colors"
                    >
                      "What are the main findings?"
                    </button>
                  </div>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  return (
                    <div
                      key={idx}
                      className={`flex gap-3 max-w-3xl ${
                        isUser ? "ml-auto flex-row-reverse" : "mr-auto"
                      }`}
                    >
                      {/* Avatar */}
                      <div
                        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${
                          isUser
                            ? "bg-[#7C3AED] text-white"
                            : "bg-gradient-to-tr from-[#1E1B4B] to-[#312E81] border border-purple-500/30 text-purple-300"
                        }`}
                      >
                        {isUser ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                      </div>

                      {/* Content Bubble */}
                      <div
                        className={`rounded-2xl p-4 text-xs sm:text-sm space-y-2 leading-relaxed ${
                          isUser
                            ? "bg-[#7C3AED] text-white shadow-md shadow-purple-950/40 rounded-tr-sm"
                            : "bg-[#12121A] border border-slate-800/80 text-slate-200 shadow-lg rounded-tl-sm"
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{msg.content}</p>

                        {/* Citations block */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="pt-2 mt-2 border-t border-slate-800/60 space-y-1">
                            <span className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider block">
                              Source Citations:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.citations.map((cite, cIdx) => (
                                <span
                                  key={cIdx}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-950/40 border border-purple-500/20 text-[10px] text-purple-300 font-medium"
                                >
                                  <FileText className="w-3 h-3 text-purple-400" />
                                  Page {cite.page ?? "N/A"}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}

              {/* Streaming / Ingestion placeholder */}
              {sending && (
                <div className="flex gap-3 max-w-3xl mr-auto">
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1E1B4B] to-[#312E81] border border-purple-500/30 text-purple-300 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="bg-[#12121A] border border-slate-800/80 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-400 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-[#7C3AED]" />
                    <span>Searching FAISS vector index & synthesizing verified answer...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <div className="p-4 sm:p-6 border-t border-slate-800/80 bg-[#12121A]/80 backdrop-blur-md">
              <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center gap-3">
                <div className="relative flex-1">
                  <input
                    type="text"
                    placeholder="Ask a question about your ingested documents..."
                    value={inputQuery}
                    onChange={(e) => setInputQuery(e.target.value)}
                    disabled={sending}
                    className="w-full bg-slate-900/90 border border-slate-800 focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED] rounded-xl py-3 pl-4 pr-12 text-xs sm:text-sm text-slate-100 placeholder-slate-500 outline-none transition-all disabled:opacity-50"
                  />
                </div>

                <button
                  type="submit"
                  disabled={!inputQuery.trim() || sending}
                  className="px-5 py-3 bg-[#7C3AED] hover:bg-[#9333EA] text-white font-semibold rounded-xl shadow-lg shadow-purple-600/30 flex items-center gap-2 text-xs sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-all shrink-0"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Ask</span>
                      <Send className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
