"use client";

import type { AdminStats } from "@/lib/types";

interface Props {
  stats: AdminStats;
}

const cards = [
  {
    key: "total_users" as const,
    label: "Foydalanuvchilar",
    icon: "👥",
    color: "var(--electric)",
  },
  {
    key: "total_experts" as const,
    label: "Ekspertlar",
    icon: "🎓",
    color: "var(--gold)",
  },
  {
    key: "verified_experts" as const,
    label: "Tasdiqlangan",
    icon: "✅",
    color: "var(--sage)",
  },
  {
    key: "total_categories" as const,
    label: "Kategoriyalar",
    icon: "🗂️",
    color: "var(--rose)",
  },
  {
    key: "total_documents" as const,
    label: "Hujjatlar",
    icon: "📄",
    color: "#A78BFA",
  },
];

export function StatsCards({ stats }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div key={card.key} className="stat-card">
          <div
            className="mb-3 text-xl w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: `${card.color}18` }}
          >
            {card.icon}
          </div>
          <p
            className="text-2xl font-semibold"
            style={{ color: "#fff", fontVariantNumeric: "tabular-nums" }}
          >
            {stats[card.key]}
          </p>
          <p
            className="mt-0.5 text-xs"
            style={{ color: "rgba(248,250,255,0.45)" }}
          >
            {card.label}
          </p>
        </div>
      ))}
    </div>
  );
}