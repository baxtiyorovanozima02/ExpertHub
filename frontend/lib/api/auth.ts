// frontend/lib/api/auth.ts

import { api } from "@/lib/api-client";
import type { AuthToken, User } from "@/lib/types";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
}

export async function loginRequest(payload: LoginPayload): Promise<AuthToken> {
  const { data } = await api.post<AuthToken>("/api/auth/login", payload);
  return data;
}

export async function registerRequest(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/api/auth/register", payload);
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>("/api/auth/me");
  return data;
}