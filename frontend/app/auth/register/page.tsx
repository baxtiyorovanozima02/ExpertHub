"use client";

import { useState } from "react";
import { useRegister } from "@/lib/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api-client";
import Link from "next/link";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const registerMutation = useRegister();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Parollar mos kelmadi");
      return;
    }
    registerMutation.mutate(
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
        Hisob yaratish
      </h2>
      <p className="mb-7 text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
        Platformaga ro'yxatdan o'ting
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {[
          { label: "Email", type: "email", value: email, onChange: setEmail, placeholder: "email@example.com" },
          { label: "Parol", type: "password", value: password, onChange: setPassword, placeholder: "••••••••" },
          { label: "Parolni tasdiqlang", type: "password", value: confirm, onChange: setConfirm, placeholder: "••••••••" },
        ].map((f) => (
          <div key={f.label}>
            <label
              className="mb-2 block text-xs font-medium uppercase tracking-wide"
              style={{ color: "rgba(248,250,255,0.5)", letterSpacing: "0.07em" }}
            >
              {f.label}
            </label>
            <input
              type={f.type}
              value={f.value}
              onChange={(e) => f.onChange(e.target.value)}
              required
              placeholder={f.placeholder}
              className="field-input"
            />
          </div>
        ))}

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
          disabled={registerMutation.isPending}
          className="btn-primary w-full py-3 mt-2"
        >
          {registerMutation.isPending ? "Yaratilmoqda…" : "Ro'yxatdan o'tish"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
        Hisobingiz bormi?{" "}
        <Link
          href="/auth/login"
          className="font-medium transition-colors hover:opacity-100"
          style={{ color: "var(--electric)" }}
        >
          Kirish
        </Link>
      </p>
    </div>
  );
}