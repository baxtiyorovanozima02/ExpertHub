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
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-600">
        Statistikani yuklashda xatolik yuz berdi
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-gray-900">Umumiy statistika</h1>
      <StatsCards stats={stats} />
    </div>
  );
}