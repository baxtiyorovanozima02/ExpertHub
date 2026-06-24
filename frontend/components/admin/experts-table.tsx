// frontend/components/admin/experts-table.tsx

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

  const verifyMutation = useMutation({
    mutationFn: (id: number) => verifyExpert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-experts"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
    onError: (err) => setErrorMsg(getApiErrorMessage(err)),
  });

  if (experts.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
        Hozircha ekspertlar yo'q
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      {errorMsg && (
        <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-600">
          {errorMsg}
        </div>
      )}
      <table className="w-full text-sm">
        <thead className="border-b border-gray-200 bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Ism</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Kategoriya</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Holat</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Amal</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {experts.map((expert) => (
            <tr key={expert.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium text-gray-900">{expert.full_name}</td>
              <td className="px-4 py-3 text-gray-500">
                {expert.category_id ? `#${expert.category_id}` : "—"}
              </td>
              <td className="px-4 py-3">
                {expert.is_verified ? (
                  <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                    Tasdiqlangan
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-700">
                    Kutilmoqda
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                {!expert.is_verified && (
                  <button
                    onClick={() => verifyMutation.mutate(expert.id)}
                    disabled={verifyMutation.isPending}
                    className="rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                  >
                    {verifyMutation.isPending ? "..." : "Tasdiqlash"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}