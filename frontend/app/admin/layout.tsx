// frontend/app/admin/layout.tsx

"use client";

import { useRequireAuth } from "@/lib/hooks/use-require-auth";
import { useLogout } from "@/lib/hooks/use-auth";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/admin", label: "Statistika" },
  { href: "/admin/experts", label: "Ekspertlar" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isReady, user } = useRequireAuth({ allowedRoles: ["admin"] });
  const logout = useLogout();
  const pathname = usePathname();

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-4 py-4">
          <p className="font-semibold text-gray-900">ExpertHub</p>
          <p className="mt-0.5 text-xs text-gray-500">Admin panel</p>
        </div>

        <nav className="flex-1 px-2 py-4">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`mb-1 flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-gray-200 px-4 py-4">
          <p className="truncate text-xs text-gray-500">{user?.email}</p>
          <button
            onClick={logout}
            className="mt-2 w-full rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Chiqish
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}