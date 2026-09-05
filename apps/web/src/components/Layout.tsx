import { Link, useRouterState, Outlet } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Chat" },
  { to: "/documents", label: "Dokumen" },
  { to: "/about", label: "Tentang" },
] as const;

export function Layout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background md:h-auto md:min-h-screen md:flex-row md:overflow-visible">
      {/* Sidebar - desktop */}
      <aside className="hidden border-r bg-card md:sticky md:top-0 md:flex md:h-screen md:w-64 md:flex-col md:overflow-y-auto">
        <div className="p-6 border-b">
          <div>
            <div className="font-semibold text-sm text-foreground">Asisten Dokumen</div>
            <div className="text-xs text-muted-foreground">Universitas Negeri Malang</div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex min-h-11 items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground/70 hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Top bar - mobile */}
      <header className="md:hidden flex shrink-0 items-center justify-between px-5 py-3 border-b bg-card">
        <div>
          <div className="font-semibold text-sm">Asisten Dokumen</div>
          <div className="text-xs text-muted-foreground">Universitas Negeri Malang</div>
        </div>
      </header>

      <main className="min-w-0 flex-1 overflow-y-auto md:overflow-visible">
        <Outlet />
      </main>

      {/* Bottom nav - mobile */}
      <nav className="md:hidden shrink-0 bg-card border-t flex pb-[env(safe-area-inset-bottom)]">
        {nav.map((item) => {
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex min-h-14 flex-1 items-center justify-center px-1 text-xs font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                className={cn(
                  "flex min-h-9 min-w-20 items-center justify-center rounded-lg px-3 transition-colors",
                  active && "bg-primary/10 font-semibold text-primary",
                )}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
