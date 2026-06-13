import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { fetchMetrics, type MetricsResponse, type EndpointMetric } from '../api/client';

function ms(val: number) {
    return `${val.toFixed(1)} ms`;
}

function CacheBar({ pct }: { pct: number }) {
    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs font-medium text-accent w-10 text-right">{pct.toFixed(0)}%</span>
        </div>
    );
}

export default function Metrics() {
    const [data, setData] = useState<MetricsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [chartData, setChartData] = useState<
        {
            name: string;
            avg: number;
            p95: number;
            cached: number | null;
        }[]
    >([{ name: '', avg: 0, p95: 0, cached: null }]);

    const load = async () => {
        setLoading(true);
        try {
            setData(await fetchMetrics());
            setError(null);
        } catch {
            setError('Failed to load metrics. Hit some endpoints first, then reload.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const endpoints = data?.endpoints ?? [];

    // Recharts data: avg vs P95 response time per endpoint
    useEffect(() => {
        if (!data?.endpoints) return;
        setChartData(
            data.endpoints.slice(0, 8).map((e: EndpointMetric) => ({
                name: e.endpoint.replace('/api/inventory/', '').replace('/api/', '') || '/',
                avg: e.avg_response_time_ms,
                p95: e.p95_response_time_ms,
                cached: e.cache_hits > 0 ? e.avg_response_time_ms * 0.05 : null,
            }))
        );
    }, [data]);

    if (loading)
        return (
            <div className="p-8 flex items-center gap-3 text-gray-500">
                <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                Loading metrics…
            </div>
        );

    if (error)
        return (
            <div className="p-8">
                <div className="card border-yellow-200 bg-yellow-50 text-yellow-800 text-sm">{error}</div>
            </div>
        );

    return (
        <div className="p-8 space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">API Performance</h1>
                    <p className="text-sm text-gray-500 mt-1">
                        {data!.total_requests_tracked.toLocaleString()} requests tracked · Updated{' '}
                        {new Date(data!.generated_at).toLocaleTimeString()}
                    </p>
                </div>
                <button onClick={load} className="btn-primary text-sm py-1.5">
                    Refresh
                </button>
            </div>

            {/* Response time chart */}
            <section className="card">
                <h2 className="text-base font-semibold text-gray-900 mb-6">Avg vs P95 Response Time by Endpoint</h2>
                <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 11, fill: '#6b7280' }}
                            angle={-35}
                            textAnchor="end"
                            height={70}
                        />
                        <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => `${v}ms`} />
                        <Tooltip
                            formatter={(value: number, name: string) => [
                                `${value.toFixed(1)} ms`,
                                name === 'avg' ? 'Avg response' : 'P95 response',
                            ]}
                            contentStyle={{ fontSize: 12, borderRadius: 8 }}
                        />
                        <Legend
                            formatter={(val) => (val === 'avg' ? 'Avg (ms)' : 'P95 (ms)')}
                            wrapperStyle={{ fontSize: 12 }}
                        />
                        <Bar dataKey="avg" fill="#1A56DB" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="p95" fill="#93C5FD" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </section>

            {/* Per-endpoint stats table */}
            <section className="card p-0 overflow-hidden">
                <div className="px-6 py-4 border-b">
                    <h2 className="text-base font-semibold text-gray-900">Endpoint Statistics</h2>
                    <p className="text-xs text-gray-400 mt-0.5">
                        P95 = the response time that 95% of requests complete under. High cache hit % = faster avg
                        times.
                    </p>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-gray-50 border-b">
                            <tr>
                                {['Endpoint', 'Method', 'Requests', 'Avg', 'P95', 'Max', 'Cache Hit %'].map((h) => (
                                    <th key={h} className="table-th">
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {endpoints.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="table-td text-center py-8 text-gray-400">
                                        No metrics recorded yet. Make a few API requests first.
                                    </td>
                                </tr>
                            ) : (
                                endpoints.map((e) => (
                                    <tr key={`${e.method}-${e.endpoint}`} className="hover:bg-gray-50">
                                        <td className="table-td font-mono text-xs text-gray-600">{e.endpoint}</td>
                                        <td className="table-td">
                                            <span className="badge-blue">{e.method}</span>
                                        </td>
                                        <td className="table-td">{e.request_count.toLocaleString()}</td>
                                        <td className="table-td font-medium">{ms(e.avg_response_time_ms)}</td>
                                        <td className="table-td">
                                            <span
                                                className={
                                                    e.p95_response_time_ms > 500
                                                        ? 'text-red-600 font-medium'
                                                        : e.p95_response_time_ms > 100
                                                          ? 'text-yellow-600 font-medium'
                                                          : 'text-green-600 font-medium'
                                                }
                                            >
                                                {ms(e.p95_response_time_ms)}
                                            </span>
                                        </td>
                                        <td className="table-td text-gray-500">{ms(e.max_response_time_ms)}</td>
                                        <td className="table-td w-40">
                                            <CacheBar pct={e.cache_hit_rate_pct} />
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* Slowest requests today */}
            {data!.slowest_today.length > 0 && (
                <section className="card p-0 overflow-hidden">
                    <div className="px-6 py-4 border-b">
                        <h2 className="text-base font-semibold text-gray-900">Slowest 10 Requests Today</h2>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50 border-b">
                                <tr>
                                    {['Endpoint', 'Method', 'Response Time', 'Status', 'Cache', 'Time'].map((h) => (
                                        <th key={h} className="table-th">
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                {data!.slowest_today.map((r, i) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                        <td className="table-td font-mono text-xs text-gray-600">{r.endpoint}</td>
                                        <td className="table-td">
                                            <span className="badge-blue">{r.method}</span>
                                        </td>
                                        <td className="table-td font-medium text-red-600">{ms(r.response_time_ms)}</td>
                                        <td className="table-td">
                                            <span className={r.status_code < 400 ? 'badge-green' : 'badge-red'}>
                                                {r.status_code}
                                            </span>
                                        </td>
                                        <td className="table-td">
                                            {r.cache_hit ? (
                                                <span className="badge-green">HIT</span>
                                            ) : (
                                                <span className="badge-yellow">MISS</span>
                                            )}
                                        </td>
                                        <td className="table-td text-gray-400 text-xs">
                                            {r.recorded_at ? new Date(r.recorded_at).toLocaleTimeString() : '—'}
                                        </td>
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
