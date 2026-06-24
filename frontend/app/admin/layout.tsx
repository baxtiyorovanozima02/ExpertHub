"use client";

import { useRequireAuth } from "@/lib/hooks/use-require-auth";
import { useLogout } from "@/lib/hooks/use-auth";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  {
    href: "/admin",
    label: "Statistika",
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    href: "/admin/experts",
    label: "Ekspertlar",
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isReady, user } = useRequireAuth({ allowedRoles: ["admin"] });
  const logout = useLogout();
  const pathname = usePathname();

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="aurora-bg" aria-hidden />
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen">
      <div className="aurora-bg" aria-hidden />

      {/* Sidebar */}
      <aside
        className="relative z-10 flex w-60 flex-col"
        style={{
          background: "rgba(7,12,26,0.9)",
          backdropFilter: "blur(24px)",
          borderRight: "1px solid rgba(79,142,247,0.12)",
        }}
      >
        {/* Logo */}
        <div
          className="flex items-center gap-2.5 px-5 py-5"
          style={{ borderBottom: "1px solid rgba(79,142,247,0.1)" }}
        >
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
            style={{ background: "linear-gradient(135deg,#4F8EF7,#6AA3FF)" }}
          >
            E
          </div>
          <div>
            <p
              className="text-sm font-light leading-tight"
              style={{ fontFamily: "var(--font-display)", color: "#fff" }}
            >
              Expert<span style={{ color: "var(--gold)", fontWeight: 500 }}>Hub</span>
            </p>
            <p className="text-xs leading-tight" style={{ color: "rgba(248,250,255,0.35)" }}>
              Admin panel
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${isActive ? "active" : ""}`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div
          className="px-4 py-4"
          style={{ borderTop: "1px solid rgba(79,142,247,0.1)" }}
        >
          <p
            className="truncate text-xs mb-2"
            style={{ color: "rgba(248,250,255,0.4)" }}
          >
            {user?.email}
          </p>
          <button onClick={logout} className="btn-ghost w-full justify-center">
            Chiqish
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="relative z-10 flex-1 overflow-auto p-6">
        {children}
      </main>
    </div>
  );
}