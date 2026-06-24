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
        <div className="spinner" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="rounded-xl px-5 py-4 text-sm"
        style={{
          background: "rgba(240,107,138,0.08)",
          border: "1px solid rgba(240,107,138,0.2)",
          color: "#F06B8A",
        }}
      >
        Ekspertlarni yuklashda xatolik yuz berdi
      </div>
    );
  }

  return (
    <div>
      <div className="mb-7 flex items-center justify-between">
        <div>
          <h1
            className="text-2xl font-light"
            style={{ fontFamily: "var(--font-display)", color: "#fff" }}
          >
            Ekspertlar
          </h1>
          <p className="mt-1 text-sm" style={{ color: "rgba(248,250,255,0.4)" }}>
            {experts.length} ta ekspert topildi
          </p>
        </div>
      </div>
      <ExpertsTable experts={experts} />
    </div>
  );
}