// frontend/lib/hooks/use-auth.ts

"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  loginRequest,
  registerRequest,
  fetchMe,
  type LoginPayload,
  type RegisterPayload,
} from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/auth-store";
import { api } from "@/lib/api-client";

function redirectByRole(role: string, router: ReturnType<typeof useRouter>) {
  router.replace(role === "admin" ? "/admin" : "/dashboard");
}

export function useLogin() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  return useMutation({
    mutationFn: (payload: LoginPayload) => loginRequest(payload),
    onSuccess: async (token) => {
      useAuthStore.setState({ token: token.access_token });
      api.defaults.headers.common.Authorization = `Bearer ${token.access_token}`;
      const me = await fetchMe();
      setAuth(token.access_token, me);
      redirectByRole(me.role, router);
    },
  });
}

export function useRegister() {
  const loginMutation = useLogin();

  return useMutation({
    mutationFn: (payload: RegisterPayload) => registerRequest(payload),
    onSuccess: (_, variables) => {
      loginMutation.mutate({ email: variables.email, password: variables.password });
    },
  });
}

export function useLogout() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  return () => {
    logout();
    router.replace("/login");
  };
}