"use client";

import { useState } from "react";
import { useLogin } from "@/lib/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api-client";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loginMutation = useLogin();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    loginMutation.mutate(
      { email, password },
      { onError: (err) => setError(getApiErrorMessage(err)) }
    );
  }

  return (
    <div className="glass-card p-8">
      <h2
        className="mb-1 text-xl font-light"
        style={{ fontFamily: "var(--font-display)", color: "#fff" }}
      >
        Xush kelibsiz
      </h2>
      <p className="mb-7 text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
        Hisobingizga kiring
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            className="mb-2 block text-xs font-medium tracking-wide uppercase"
            style={{ color: "rgba(248,250,255,0.5)", letterSpacing: "0.07em" }}
          >
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="email@example.com"
            className="field-input"
          />
        </div>

        <div>
          <label
            className="mb-2 block text-xs font-medium tracking-wide uppercase"
            style={{ color: "rgba(248,250,255,0.5)", letterSpacing: "0.07em" }}
          >
            Parol
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="••••••••"
            className="field-input"
          />
        </div>

        {error && (
          <div
            className="rounded-xl px-4 py-3 text-sm"
            style={{
              background: "rgba(240,107,138,0.1)",
              border: "1px solid rgba(240,107,138,0.25)",
              color: "#F06B8A",
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loginMutation.isPending}
          className="btn-primary w-full py-3 mt-2"
        >
          {loginMutation.isPending ? "Kirilmoqda…" : "Kirish"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
        Hisobingiz yo'qmi?{" "}
        <Link
          href="/auth/register"
          className="font-medium transition-colors hover:opacity-100"
          style={{ color: "var(--electric)" }}
        >
          Ro'yxatdan o'tish
        </Link>
      </p>
    </div>
  );
}