import { api } from "@/lib/api-client";
import type { Conversation, ChatMessage, ChatHistory, Category } from "@/lib/types";

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>("/api/categories/");
  return data;
}

export async function createConversation(categoryId: number | null): Promise<Conversation> {
  const { data } = await api.post<Conversation>("/api/chat/", {
    category_id: categoryId,
  });
  return data;
}

export async function sendMessage(
  conversationId: number,
  content: string,
  replyWithAudio: boolean = false
): Promise<ChatMessage> {
  const { data } = await api.post<ChatMessage>(
    `/api/chat/${conversationId}/message`,
    { content },
    { params: { reply_with_audio: replyWithAudio } }
  );
  return data;
}

export async function fetchHistory(conversationId: number): Promise<ChatHistory> {
  const { data } = await api.get<ChatHistory>(`/api/chat/${conversationId}/history`);
  return data;
}