// frontend/lib/hooks/use-chat-conversation.ts

"use client";

import { useCallback, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { createConversation, sendMessage, fetchHistory } from "@/lib/api/chat";
import { saveLocalConversation, updateLocalConversationPreview } from "@/lib/local-conversations";
import type { ChatMessage } from "@/lib/types";

export function useChatConversation(initialConversationId?: number) {
  const [conversationId, setConversationId] = useState<number | undefined>(initialConversationId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [categoryId, setCategoryId] = useState<number | null>(null);

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let activeId = conversationId;

      if (!activeId) {
        const conversation = await createConversation(categoryId);
        activeId = conversation.id;
        setConversationId(activeId);
        saveLocalConversation({
          id: conversation.id,
          category_id: conversation.category_id ?? null,
          created_at: conversation.created_at,
        });
      }

      const optimisticUserMessage: ChatMessage = {
        id: Date.now(),
        conversation_id: activeId,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticUserMessage]);

      const assistantMessage = await sendMessage(activeId, content);
      updateLocalConversationPreview(activeId, content.slice(0, 80));
      return assistantMessage;
    },
    onSuccess: (assistantMessage) => {
      setMessages((prev) => [...prev, assistantMessage]);
    },
  });

  const loadHistory = useCallback(async (id: number) => {
    const history = await fetchHistory(id);
    setConversationId(history.conversation.id);
    setCategoryId(history.conversation.category_id ?? null);
    setMessages(history.messages);
  }, []);

  return {
    conversationId,
    categoryId,
    setCategoryId,
    messages,
    sendMutation,
    loadHistory,
  };
}