// frontend/lib/local-conversations.ts

export interface LocalConversation {
  id: number;
  category_id: number | null;
  created_at: string;
  preview?: string;
}

const STORAGE_KEY = "experthub-conversations";

function getAll(): LocalConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveAll(list: LocalConversation[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

export function saveLocalConversation(conv: LocalConversation) {
  const list = getAll();
  const exists = list.find((c) => c.id === conv.id);
  if (!exists) {
    saveAll([conv, ...list]);
  }
}

export function updateLocalConversationPreview(id: number, preview: string) {
  const list = getAll().map((c) =>
    c.id === id ? { ...c, preview } : c
  );
  saveAll(list);
}

export function getLocalConversations(): LocalConversation[] {
  return getAll();
}

export function removeLocalConversation(id: number) {
  saveAll(getAll().filter((c) => c.id !== id));
}