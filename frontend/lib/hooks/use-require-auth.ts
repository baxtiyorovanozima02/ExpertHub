// frontend/lib/hooks/use-require-auth.ts

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import type { UserRole } from "@/lib/types";

interface UseRequireAuthOptions {
  allowedRoles?: UserRole[];
  redirectTo?: string;
}

export function useRequireAuth({
  allowedRoles,
  redirectTo = "/login",
}: UseRequireAuthOptions = {}) {
  const router = useRouter();
  const { token, user, isHydrated } = useAuthStore();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!isHydrated) return;

    if (!token || !user) {
      router.replace(redirectTo);
      return;
    }

    if (allowedRoles && !allowedRoles.includes(user.role)) {
      const fallback =
        user.role === "admin" ? "/admin" :
        user.role === "expert" ? "/expert" : "/dashboard";
      router.replace(fallback);
      return;
    }

    setChecked(true);
  }, [isHydrated, token, user]);

  return { user, isReady: checked };
}