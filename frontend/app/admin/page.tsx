"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchAdminStats } from "@/lib/api/admin";
import { StatsCards } from "@/components/admin/stats-cards";

export default function AdminStatsPage() {
  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: fetchAdminStats,
  });

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="spinner" />
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div
        className="rounded-xl px-5 py-4 text-sm"
        style={{
          background: "rgba(240,107,138,0.08)",
          border: "1px solid rgba(240,107,138,0.2)",
          color: "#F06B8A",
        }}
      >
        Statistikani yuklashda xatolik yuz berdi
      </div>
    );
  }

  return (
    <div>
      <div className="mb-7">
        <h1
          className="text-2xl font-light"
          style={{ fontFamily: "var(--font-display)", color: "#fff" }}
        >
          Umumiy statistika
        </h1>
        <p className="mt-1 text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
          Platformadagi joriy ko'rsatkichlar
        </p>
      </div>
      <StatsCards stats={stats} />
    </div>
  );
}