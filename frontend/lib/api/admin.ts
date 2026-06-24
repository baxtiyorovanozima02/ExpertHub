// frontend/lib/api/admin.ts

import { api } from "@/lib/api-client";
import type { Expert, AdminStats, Category } from "@/lib/types";

export async function fetchAdminStats(): Promise<AdminStats> {
  const { data } = await api.get<AdminStats>("/api/admin/stats/");
  return data;
}

export async function fetchAdminExperts(): Promise<Expert[]> {
  const { data } = await api.get<Expert[]>("/api/admin/experts/");
  return data;
}

export async function verifyExpert(expertId: number): Promise<Expert> {
  const { data } = await api.put<Expert>(`/api/admin/experts/${expertId}/verify/`);
  return data;
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>("/api/categories/");
  return data;
}