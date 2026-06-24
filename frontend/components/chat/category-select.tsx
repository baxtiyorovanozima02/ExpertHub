// frontend/components/chat/category-select.tsx

"use client";

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

  if (isLoading) {
    return (
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 w-24 animate-pulse rounded-full bg-gray-200" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {categories.map((cat: Category) => (
        <button
          key={cat.id}
          onClick={() => onSelect(cat.id)}
          className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
            selected === cat.id
              ? "border-gray-900 bg-gray-900 text-white"
              : "border-gray-200 bg-white text-gray-600 hover:border-gray-400"
          }`}
        >
          {cat.icon && <span className="mr-1">{cat.icon}</span>}
          {cat.name}
        </button>
      ))}
    </div>
  );
}