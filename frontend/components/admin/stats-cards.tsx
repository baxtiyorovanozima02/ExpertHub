// frontend/components/admin/stats-cards.tsx

"use client";

import type { AdminStats } from "@/lib/types";

interface Props {
  stats: AdminStats;
}

const cards = [
  { key: "total_users" as const, label: "Jami foydalanuvchilar" },
  { key: "total_experts" as const, label: "Jami ekspertlar" },
  { key: "verified_experts" as const, label: "Tasdiqlangan ekspertlar" },
  { key: "total_categories" as const, label: "Kategoriyalar" },
  { key: "total_documents" as const, label: "Hujjatlar" },
];

export function StatsCards({ stats }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.key}
          className="rounded-lg border border-gray-200 bg-white p-4"
        >
          <p className="text-2xl font-bold text-gray-900">{stats[card.key]}</p>
          <p className="mt-1 text-xs text-gray-500">{card.label}</p>
        </div>
      ))}
    </div>
  );
}