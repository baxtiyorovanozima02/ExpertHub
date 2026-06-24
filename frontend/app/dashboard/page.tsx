// frontend/app/dashboard/page.tsx

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

  const { messages, categoryId, setCategoryId, sendMutation } = useChatConversation();

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
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
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <p className="font-semibold text-gray-900">ExpertHub</p>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.email}</span>
          <button
            onClick={logout}
            className="rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Chiqish
          </button>
        </div>
      </header>

      {/* Kategoriya tanlash */}
      <div className="border-b border-gray-200 bg-white px-6 py-3">
        <p className="mb-2 text-xs font-medium text-gray-500">Kategoriya tanlang</p>
        <CategorySelect selected={categoryId} onSelect={setCategoryId} />
      </div>

      {/* Chat */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <ChatWindow messages={messages} isLoading={sendMutation.isPending} />

        {/* Input */}
        <form
          onSubmit={handleSend}
          className="border-t border-gray-200 bg-white px-4 py-3"
        >
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                categoryId
                  ? "Savolingizni yozing..."
                  : "Avval kategoriya tanlang"
              }
              disabled={!categoryId || sendMutation.isPending}
              className="flex-1 rounded-lg border border-gray-200 px-4 py-2.5 text-sm outline-none placeholder:text-gray-400 focus:border-gray-400 focus:ring-2 focus:ring-gray-100 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || !categoryId || sendMutation.isPending}
              className="rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
            >
              Yuborish
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}