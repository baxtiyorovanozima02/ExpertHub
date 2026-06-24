// frontend/lib/api/expert.ts

import { api } from "@/lib/api-client";
import type { ExpertDocument, Category } from "@/lib/types";

export interface UploadTextPayload {
  content: string;
  source?: string;
}

export interface ExpertProfile {
  id: number;
  full_name: string;
  bio?: string | null;
  category_id?: number | null;
  is_verified: boolean;
}

export async function fetchExpertProfile(): Promise<ExpertProfile> {
  const { data } = await api.get<ExpertProfile>("/api/expert/me/");
  return data;
}

export async function fetchExpertDocuments(): Promise<ExpertDocument[]> {
  const { data } = await api.get<ExpertDocument[]>("/api/expert/documents/");
  return data;
}

export async function uploadTextDocument(payload: UploadTextPayload): Promise<ExpertDocument> {
  const { data } = await api.post<ExpertDocument>("/api/expert/documents/text/", payload);
  return data;
}

export async function uploadFileDocument(file: File): Promise<ExpertDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<ExpertDocument>("/api/expert/documents/file/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/api/expert/documents/${documentId}/`);
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>("/api/categories/");
  return data;
}