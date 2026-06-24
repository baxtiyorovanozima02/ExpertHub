"use client";

import { useRef, useEffect } from "react";
import type { ChatMessage } from "@/lib/types";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
}

export function ChatWindow({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
        <div
          className="h-14 w-14 rounded-2xl flex items-center justify-center text-2xl"
          style={{ background: "rgba(79,142,247,0.1)", border: "1px solid rgba(79,142,247,0.2)" }}
        >
          💬
        </div>
        <p className="text-sm text-center max-w-xs" style={{ color: "rgba(248,250,255,0.35)" }}>
          Savolingizni yozing — AI ekspert ma'lumotlari asosida javob beradi
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex flex-1 flex-col gap-4 overflow-y-auto p-6 thin-scroll"
      style={{ maxWidth: "100%" }}
    >
      <div className="max-w-3xl w-full mx-auto flex flex-col gap-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div
                className="mr-2 mt-1 h-7 w-7 flex-shrink-0 rounded-full flex items-center justify-center text-xs font-bold"
                style={{ background: "linear-gradient(135deg,#4F8EF7,#6AA3FF)", color: "#fff" }}
              >
                AI
              </div>
            )}
            <div
              className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user" ? "bubble-user" : "bubble-ai"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div
              className="mr-2 mt-1 h-7 w-7 flex-shrink-0 rounded-full flex items-center justify-center text-xs font-bold"
              style={{ background: "linear-gradient(135deg,#4F8EF7,#6AA3FF)", color: "#fff" }}
            >
              AI
            </div>
            <div className="bubble-ai rounded-2xl px-4 py-3.5">
              <div className="flex gap-1.5 items-center">
                <span
                  className="h-2 w-2 rounded-full typing-dot"
                  style={{ background: "var(--electric)", animationDelay: "0ms" }}
                />
                <span
                  className="h-2 w-2 rounded-full typing-dot"
                  style={{ background: "var(--electric)", animationDelay: "160ms" }}
                />
                <span
                  className="h-2 w-2 rounded-full typing-dot"
                  style={{ background: "var(--electric)", animationDelay: "320ms" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}