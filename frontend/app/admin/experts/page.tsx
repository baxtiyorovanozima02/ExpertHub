// frontend/app/admin/experts/page.tsx

"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchAdminExperts } from "@/lib/api/admin";
import { ExpertsTable } from "@/components/admin/experts-table";

export default function AdminExpertsPage() {
  const { data: experts = [], isLoading, isError } = useQuery({
    queryKey: ["admin-experts"],
    queryFn: fetchAdminExperts,
  });

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-600">
        Ekspertlarni yuklashda xatolik yuz berdi
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-gray-900">Ekspertlar</h1>
      <ExpertsTable experts={experts} />
    </div>
  );
}