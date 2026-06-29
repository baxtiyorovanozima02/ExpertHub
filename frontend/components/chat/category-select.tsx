"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCategories } from "@/lib/api/chat";
import type { Category } from "@/lib/types";

interface Props {
  selected: number | null;
  onSelect: (id: number) => void;
}

export function CategorySelect({ selected, onSelect }: Props) {
  const { data: categories = [], isLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  const [poppedId, setPoppedId] = useState<number | null>(null);

  function handleSelect(id: number) {
    onSelect(id);
    setPoppedId(id);
    setTimeout(() => setPoppedId(null), 350);
  }

  if (isLoading) {
    return (
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-8 w-24 animate-pulse rounded-full"
            style={{ background: "rgba(79,142,247,0.08)" }}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {categories.map((cat: Category, index: number) => (
        <button
          key={cat.id}
          onClick={() => handleSelect(cat.id)}
          className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all pill-in ${
            selected === cat.id ? "tag-active" : "tag-idle"
          } ${poppedId === cat.id ? "pill-pop" : ""}`}
          style={{ animationDelay: `${index * 45}ms` }}
        >
          {cat.icon && <span className="mr-1.5">{cat.icon}</span>}
          {cat.name}
        </button>
      ))}
    </div>
  );
}