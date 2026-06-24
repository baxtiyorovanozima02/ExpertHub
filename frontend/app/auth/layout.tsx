export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      {/* Aurora background */}
      <div className="aurora-bg" aria-hidden />

      <div className="relative z-10 w-full max-w-sm">
        {/* Logo area */}
        <div className="mb-10 text-center">
          <div className="inline-flex items-center gap-2 mb-4">
            <div
              className="h-9 w-9 rounded-xl flex items-center justify-center text-white text-lg font-bold"
              style={{ background: "linear-gradient(135deg,#4F8EF7,#6AA3FF)" }}
            >
              E
            </div>
            <span
              className="text-2xl font-light tracking-tight"
              style={{ fontFamily: "var(--font-display)", color: "#fff" }}
            >
              Expert<span style={{ color: "var(--gold)", fontWeight: 500 }}>Hub</span>
            </span>
          </div>
          <p className="text-sm" style={{ color: "rgba(248,250,255,0.45)" }}>
            Kasb ekspertlari maslahat platformasi
          </p>
        </div>

        {children}
      </div>
    </div>
  );
}