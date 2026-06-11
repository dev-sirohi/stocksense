import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

export interface SKU {
  id: number;
  code: string;
  name: string;
  category: string;
  unit: string;
  reorder_level: number;
  shelf_life_days: number | null;
  purchase_price: number;
  selling_price: number;
  description: string | null;
  has_embedding?: boolean;
}

export interface StockItem {
  sku_id: number;
  code: string;
  name: string;
  category: string;
  unit: string;
  reorder_level: number;
  total_quantity: number;
  needs_reorder: boolean;
}

export interface AlertItem {
  record_id: number;
  sku_code: string;
  sku_name: string;
  category: string;
  quantity: number;
  expiry_date: string;
  days_until_expiry?: number;
  days_overdue?: number;
  location: string | null;
}

export interface LowStockItem {
  sku_id: number;
  sku_code: string;
  sku_name: string;
  category: string;
  unit: string;
  total_quantity: number;
  reorder_level: number;
}

export interface AlertSummary {
  total_skus: number;
  expiring_soon_count: number;
  expired_count: number;
  low_stock_count: number;
}

export interface AlertsResponse {
  expiring_soon: AlertItem[];
  expired: AlertItem[];
  low_stock: LowStockItem[];
  summary: AlertSummary;
}

export interface SearchResult {
  id: number;
  code: string;
  name: string;
  category: string;
  unit: string;
  description: string | null;
  similarity_score: number;
  cosine_distance: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface EndpointMetric {
  endpoint: string;
  method: string;
  request_count: number;
  avg_response_time_ms: number;
  min_response_time_ms: number;
  max_response_time_ms: number;
  p95_response_time_ms: number;
  cache_hit_rate_pct: number;
  cache_hits: number;
}

export interface SlowRequest {
  endpoint: string;
  method: string;
  response_time_ms: number;
  status_code: number;
  cache_hit: boolean;
  recorded_at: string;
}

export interface MetricsResponse {
  endpoints: EndpointMetric[];
  slowest_today: SlowRequest[];
  total_requests_tracked: number;
  generated_at: string;
}

export interface SKUListResponse {
  total: number;
  page: number;
  items: SKU[];
}

export const fetchAlerts = () =>
  api.get<AlertsResponse>("/inventory/alerts").then((r) => r.data);

export const fetchSKUs = (params: {
  category?: string;
  skip?: number;
  limit?: number;
}) => api.get<SKUListResponse>("/inventory/skus", { params }).then((r) => r.data);

export const fetchCategories = () =>
  api.get<{ categories: string[] }>("/inventory/categories").then((r) => r.data);

export const fetchStock = (skuId?: number) =>
  api
    .get<{ items: StockItem[] }>("/inventory/stock", {
      params: skuId ? { sku_id: skuId } : {},
    })
    .then((r) => r.data);

export const fetchSemanticSearch = (q: string) =>
  api.get<SearchResponse>("/inventory/search", { params: { q } }).then((r) => r.data);

export const fetchMetrics = () =>
  api.get<MetricsResponse>("/metrics").then((r) => r.data);
