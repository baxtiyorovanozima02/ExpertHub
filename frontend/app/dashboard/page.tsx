"use client";

import { useState } from "react";
import { useRequireAuth } from "@/lib/hooks/use-require-auth";
import { useLogout } from "@/lib/hooks/use-auth";
import { useChatConversation } from "@/lib/hooks/use-chat-conversation";
import { CategorySelect } from "@/components/chat/category-select";
import { ChatWindow } from "@/components/chat/chat-window";

export default function DashboardPage() {
  const { isReady, user } = useRequireAuth({ allowedRoles: ["user"] });
  const logout = useLogout();
  const [input, setInput] = useState("");
  const [inputFocused, setInputFocused] = useState(false);

  const { messages, categoryId, setCategoryId, sendMutation } = useChatConversation();

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="aurora-bg" aria-hidden />
        <div className="spinner" />
      </div>
    );
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sendMutation.isPending) return;
    setInput("");
    sendMutation.mutate(text);
  }

  return (
    <div className="relative flex min-h-screen flex-col">
      <div className="aurora-bg" aria-hidden />

      {/* Decorative floating glow orbs for extra depth */}
      <div
        className="glow-orb"
        aria-hidden
        style={{
          top: "8%",
          left: "8%",
          width: "260px",
          height: "260px",
          background: "rgba(79,142,247,0.16)",
        }}
      />
      <div
        className="glow-orb"
        aria-hidden
        style={{
          bottom: "4%",
          right: "6%",
          width: "300px",
          height: "300px",
          background: "rgba(240,168,67,0.10)",
          animationDelay: "2s",
        }}
      />

      {/* Header */}
      <header
        className="relative z-10 flex items-center justify-between px-6 py-4"
        style={{
          background: "rgba(7,12,26,0.8)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid rgba(79,142,247,0.12)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-sm font-bold avatar-glow"
            style={{ background: "linear-gradient(135deg,#4F8EF7,#6AA3FF)" }}
          >
            E
          </div>
          <span
            className="text-lg font-light"
            style={{ fontFamily: "var(--font-display)", color: "#fff" }}
          >
            Expert<span style={{ color: "var(--gold)", fontWeight: 500 }}>Hub</span>
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span
            className="text-xs hidden sm:flex items-center gap-1.5"
            style={{ color: "rgba(248,250,255,0.4)" }}
          >
            <span className="status-dot" />
            {user?.email}
          </span>
          <button onClick={logout} className="btn-ghost">
            Chiqish
          </button>
        </div>
      </header>

      {/* Category strip */}
      <div
        className="relative z-10 px-6 py-3"
        style={{
          background: "rgba(7,12,26,0.6)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(79,142,247,0.08)",
        }}
      >
        <p
          className="mb-2.5 text-xs font-medium uppercase tracking-widest"
          style={{ color: "rgba(248,250,255,0.35)", letterSpacing: "0.1em" }}
        >
          Kategoriya tanlang
        </p>
        <CategorySelect selected={categoryId} onSelect={setCategoryId} />
      </div>

      {/* Chat area */}
      <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
        <ChatWindow messages={messages} isLoading={sendMutation.isPending} />

        {/* Input bar */}
        <form
          onSubmit={handleSend}
          className="px-4 py-4"
          style={{
            background: "rgba(7,12,26,0.85)",
            backdropFilter: "blur(20px)",
            borderTop: "1px solid rgba(79,142,247,0.12)",
          }}
        >
          <div className="flex gap-2 max-w-4xl mx-auto">
            <div className={`input-glow-wrap flex-1 ${inputFocused ? "focused" : ""}`}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                placeholder={
                  categoryId
                    ? "Savolingizni yozing…"
                    : "Avval kategoriya tanlang"
                }
                disabled={!categoryId || sendMutation.isPending}
                className="field-input w-full"
                style={{ borderRadius: "0.85rem" }}
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || !categoryId || sendMutation.isPending}
              className="btn-primary px-6"
            >
              {sendMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4" strokeDashoffset="10" />
                  </svg>
                  Yuborilmoqda
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Yuborish
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}