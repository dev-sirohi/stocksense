import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: "⬛" },
  { to: "/inventory", label: "Inventory", icon: "📦" },
  { to: "/search", label: "Semantic Search", icon: "🔍" },
  { to: "/ask", label: "Ask Vikram", icon: "💬" },
  { to: "/metrics", label: "Performance", icon: "📊" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ── */}
      <aside className="w-60 bg-white border-r flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-6 py-5 border-b">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">
              SS
            </div>
            <div>
              <p className="font-semibold text-gray-900 text-sm leading-tight">StockSense</p>
              <p className="text-xs text-gray-400">Warehouse Intelligence</p>
            </div>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-6 py-4 border-t">
          <p className="text-xs text-gray-400">v2.0 · async + pgvector</p>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  );
}
