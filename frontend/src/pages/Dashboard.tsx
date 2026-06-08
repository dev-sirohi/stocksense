import { useEffect, useState, useCallback } from "react";
import { fetchAlerts, type AlertsResponse } from "../api/client";

// Auto-refresh interval: 30 seconds (30,000 ms)
const REFRESH_INTERVAL_MS = 30_000;

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color: "blue" | "yellow" | "red" | "gray";
}) {
  const palette = {
    blue: "bg-accent-light text-accent border-blue-200",
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    red: "bg-red-50 text-red-700 border-red-200",
    gray: "bg-gray-50 text-gray-700 border-gray-200",
  };
  return (
    <div className={`card border ${palette[color]} flex flex-col gap-1`}>
      <span className="text-3xl font-bold">{value}</span>
      <span className="text-sm font-medium opacity-80">{label}</span>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = useCallback(async () => {
    try {
      const result = await fetchAlerts();
      setData(result);
      setLastRefresh(new Date());
      setError(null);
    } catch {
      setError("Failed to load alerts. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + auto-refresh every 30 seconds
  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_INTERVAL_MS);
    return () => clearInterval(timer); // cleanup on unmount
  }, [load]);

  if (loading)
    return (
      <div className="p-8 flex items-center gap-3 text-gray-500">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        Loading dashboard...
      </div>
    );

  if (error)
    return (
      <div className="p-8">
        <div className="card border-red-200 bg-red-50 text-red-700">{error}</div>
      </div>
    );

  const s = data!.summary;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Last refreshed: {lastRefresh.toLocaleTimeString()} · auto-refreshes every 30s
          </p>
        </div>
        <button onClick={load} className="btn-primary text-sm py-1.5">
          Refresh now
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total SKUs" value={s.total_skus} color="gray" />
        <StatCard label="Expiring Soon (7d)" value={s.expiring_soon_count} color="yellow" />
        <StatCard label="Already Expired" value={s.expired_count} color="red" />
        <StatCard label="Low Stock" value={s.low_stock_count} color="blue" />
      </div>

      {/* Expiring Soon */}
      {data!.expiring_soon.length > 0 && (
        <section className="card">
          <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
            Expiring Within 7 Days ({data!.expiring_soon.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-y">
                <tr>
                  {["SKU Code", "Name", "Category", "Qty", "Expiry Date", "Days Left", "Location"].map(
                    (h) => <th key={h} className="table-th">{h}</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data!.expiring_soon.map((r) => (
                  <tr key={r.record_id} className="hover:bg-gray-50">
                    <td className="table-td font-mono text-xs text-gray-500">{r.sku_code}</td>
                    <td className="table-td font-medium">{r.sku_name}</td>
                    <td className="table-td">{r.category}</td>
                    <td className="table-td">{r.quantity}</td>
                    <td className="table-td">{r.expiry_date}</td>
                    <td className="table-td">
                      <span className={`badge-${(r.days_until_expiry ?? 0) <= 2 ? "red" : "yellow"}`}>
                        {r.days_until_expiry}d
                      </span>
                    </td>
                    <td className="table-td text-gray-500">{r.location ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Expired */}
      {data!.expired.length > 0 && (
        <section className="card">
          <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
            Expired Stock ({data!.expired.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-y">
                <tr>
                  {["SKU Code", "Name", "Category", "Qty", "Expired On", "Days Overdue", "Location"].map(
                    (h) => <th key={h} className="table-th">{h}</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data!.expired.map((r) => (
                  <tr key={r.record_id} className="hover:bg-gray-50">
                    <td className="table-td font-mono text-xs text-gray-500">{r.sku_code}</td>
                    <td className="table-td font-medium">{r.sku_name}</td>
                    <td className="table-td">{r.category}</td>
                    <td className="table-td">{r.quantity}</td>
                    <td className="table-td">{r.expiry_date}</td>
                    <td className="table-td">
                      <span className="badge-red">{r.days_overdue}d overdue</span>
                    </td>
                    <td className="table-td text-gray-500">{r.location ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Low Stock */}
      {data!.low_stock.length > 0 && (
        <section className="card">
          <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent inline-block" />
            Low Stock — Reorder Required ({data!.low_stock.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-y">
                <tr>
                  {["SKU Code", "Name", "Category", "Unit", "Stock", "Reorder Level"].map(
                    (h) => <th key={h} className="table-th">{h}</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data!.low_stock.map((r) => (
                  <tr key={r.sku_id} className="hover:bg-gray-50">
                    <td className="table-td font-mono text-xs text-gray-500">{r.sku_code}</td>
                    <td className="table-td font-medium">{r.sku_name}</td>
                    <td className="table-td">{r.category}</td>
                    <td className="table-td">{r.unit}</td>
                    <td className="table-td">
                      <span className="badge-blue">{r.total_quantity}</span>
                    </td>
                    <td className="table-td text-gray-500">{r.reorder_level}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
