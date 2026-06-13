import { useEffect, useState, useCallback } from 'react';
import { fetchSKUs, fetchCategories, type SKU } from '../api/client';

export default function Inventory() {
    const [skus, setSkus] = useState<SKU[]>([]);
    const [total, setTotal] = useState(0);
    const [categories, setCategories] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState('');
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 50;

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [skuData, catData] = await Promise.all([
                fetchSKUs({ category: category || undefined, skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
                categories.length === 0 ? fetchCategories() : Promise.resolve(null),
            ]);
            setSkus(skuData.items);
            setTotal(skuData.total);
            if (catData) setCategories(catData.categories);
        } catch {
            // silent — table just stays empty
        } finally {
            setLoading(false);
        }
    }, [category, page, categories.length]);

    useEffect(() => {
        load();
    }, [load]);

    // Client-side text search on the already-fetched page
    const filtered = skus.filter(
        (s) =>
            search === '' ||
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.code.toLowerCase().includes(search.toLowerCase())
    );

    const totalPages = Math.ceil(total / PAGE_SIZE);

    return (
        <div className="p-8 space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900">Inventory</h1>
                <p className="text-sm text-gray-500 mt-1">{total} SKUs total</p>
            </div>

            {/* Filters */}
            <div className="flex gap-3 flex-wrap">
                <input
                    type="text"
                    placeholder="Search by name or code…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="border rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                />
                <select
                    value={category}
                    onChange={(e) => {
                        setCategory(e.target.value);
                        setPage(1);
                    }}
                    className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                >
                    <option value="">All categories</option>
                    {categories.map((c) => (
                        <option key={c} value={c}>
                            {c}
                        </option>
                    ))}
                </select>
                {(search || category) && (
                    <button
                        onClick={() => {
                            setSearch('');
                            setCategory('');
                            setPage(1);
                        }}
                        className="text-sm text-accent hover:underline"
                    >
                        Clear filters
                    </button>
                )}
            </div>

            {/* Table */}
            <div className="card p-0 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-gray-50 border-b">
                            <tr>
                                {[
                                    'Code',
                                    'Name',
                                    'Category',
                                    'Unit',
                                    'Shelf Life',
                                    'Purchase ₹',
                                    'Selling ₹',
                                    'Reorder Level',
                                ].map((h) => (
                                    <th key={h} className="table-th">
                                        {h}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {loading ? (
                                <tr>
                                    <td colSpan={8} className="table-td text-center py-12 text-gray-400">
                                        Loading…
                                    </td>
                                </tr>
                            ) : filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="table-td text-center py-12 text-gray-400">
                                        No SKUs found
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((s) => (
                                    <tr key={s.id} className="hover:bg-gray-50">
                                        <td className="table-td font-mono text-xs text-gray-500">{s.code}</td>
                                        <td className="table-td font-medium text-gray-900">{s.name}</td>
                                        <td className="table-td">
                                            <span className="badge-blue">{s.category}</span>
                                        </td>
                                        <td className="table-td text-gray-500">{s.unit}</td>
                                        <td className="table-td text-gray-500">
                                            {s.shelf_life_days ? `${s.shelf_life_days}d` : '—'}
                                        </td>
                                        <td className="table-td">₹{s.purchase_price.toFixed(2)}</td>
                                        <td className="table-td">₹{s.selling_price.toFixed(2)}</td>
                                        <td className="table-td">
                                            <span className="badge-yellow">{s.reorder_level}</span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="px-4 py-3 border-t flex items-center justify-between text-sm text-gray-500">
                        <span>
                            Page {page} of {totalPages}
                        </span>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                disabled={page === 1}
                                className="px-3 py-1 rounded border hover:bg-gray-50 disabled:opacity-40"
                            >
                                ← Prev
                            </button>
                            <button
                                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                disabled={page === totalPages}
                                className="px-3 py-1 rounded border hover:bg-gray-50 disabled:opacity-40"
                            >
                                Next →
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
