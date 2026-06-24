"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { verifyExpert } from "@/lib/api/admin";
import { getApiErrorMessage } from "@/lib/api-client";
import type { Expert } from "@/lib/types";

interface Props {
  experts: Expert[];
}

export function ExpertsTable({ experts }: Props) {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);

  const verifyMutation = useMutation({
    mutationFn: (id: number) => verifyExpert(id),
    onMutate: (id) => setVerifyingId(id),
    onSettled: () => setVerifyingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-experts"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
    onError: (err) => setErrorMsg(getApiErrorMessage(err)),
  });

  if (experts.length === 0) {
    return (
      <div
        className="glass-card p-12 text-center"
        style={{ color: "rgba(248,250,255,0.35)" }}
      >
        <div className="text-3xl mb-3">🎓</div>
        <p className="text-sm">Hozircha ekspertlar yo'q</p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      {errorMsg && (
        <div
          className="px-5 py-3 text-sm"
          style={{
            background: "rgba(240,107,138,0.08)",
            borderBottom: "1px solid rgba(240,107,138,0.2)",
            color: "#F06B8A",
          }}
        >
          {errorMsg}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Ism</th>
              <th>Kategoriya</th>
              <th>Holat</th>
              <th>Amal</th>
            </tr>
          </thead>
          <tbody>
            {experts.map((expert) => (
              <tr key={expert.id}>
                <td>
                  <div className="flex items-center gap-2.5">
                    <div
                      className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0"
                      style={{ background: "rgba(79,142,247,0.15)", color: "var(--electric)" }}
                    >
                      {expert.full_name?.charAt(0)?.toUpperCase() ?? "?"}
                    </div>
                    <span className="font-medium" style={{ color: "#fff" }}>
                      {expert.full_name}
                    </span>
                  </div>
                </td>
                <td>
                  {expert.category_id ? (
                    <span
                      className="font-mono text-xs px-2 py-0.5 rounded"
                      style={{
                        background: "rgba(79,142,247,0.08)",
                        color: "var(--glow)",
                      }}
                    >
                      #{expert.category_id}
                    </span>
                  ) : (
                    <span style={{ color: "rgba(248,250,255,0.25)" }}>—</span>
                  )}
                </td>
                <td>
                  {expert.is_verified ? (
                    <span className="badge badge-green">Tasdiqlangan</span>
                  ) : (
                    <span className="badge badge-yellow">Kutilmoqda</span>
                  )}
                </td>
                <td>
                  {!expert.is_verified && (
                    <button
                      onClick={() => verifyMutation.mutate(expert.id)}
                      disabled={verifyMutation.isPending}
                      className="btn-primary py-1.5 px-3 text-xs"
                      style={{ borderRadius: "0.5rem" }}
                    >
                      {verifyingId === expert.id ? "…" : "Tasdiqlash"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}