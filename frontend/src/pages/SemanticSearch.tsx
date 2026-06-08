import { useState } from "react";
import { fetchSemanticSearch, type SearchResult } from "../api/client";

const EXAMPLES = [
  "items that spoil quickly",
  "cleaning products",
  "children's snacks",
  "frozen desserts",
  "high protein dairy",
];

function ResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const score = result.similarity_score;
  const barWidth = Math.max(0, Math.min(100, score));

  return (
    <div className="card flex gap-4">
      <div className="text-2xl font-bold text-gray-200 w-8 shrink-0 text-center">{rank}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-semibold text-gray-900">{result.name}</p>
            <p className="text-xs text-gray-500 font-mono mt-0.5">{result.code}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-lg font-bold text-accent">{score.toFixed(1)}%</p>
            <p className="text-xs text-gray-400">similarity</p>
          </div>
        </div>

        {/* Similarity bar */}
        <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all"
            style={{ width: `${barWidth}%` }}
          />
        </div>

        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <span className="badge-blue">{result.category}</span>
          <span className="text-sm text-gray-500">{result.unit}</span>
          {result.description && (
            <p className="text-sm text-gray-500 truncate w-full mt-1">{result.description}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SemanticSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState("");

  const search = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setLastQuery(q);
    try {
      const data = await fetchSemanticSearch(q);
      setResults(data.results);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Search failed";
      setError(
        msg.includes("503")
          ? "Embeddings not generated yet. Run: python -m app.services.embedding_service"
          : msg
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    search(query);
  };

  return (
    <div className="p-8 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Semantic Search</h1>
        <p className="text-sm text-gray-500 mt-1">
          Search by meaning, not keywords. Powered by OpenAI embeddings + pgvector.
        </p>
      </div>

      {/* Search input */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Try "items that spoil quickly" or "cleaning products"…'
          className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
        />
        <button type="submit" disabled={loading || !query.trim()} className="btn-primary">
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Searching
            </span>
          ) : (
            "Search"
          )}
        </button>
      </form>

      {/* Example queries */}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-gray-400 self-center">Examples:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => { setQuery(ex); search(ex); }}
            className="text-xs px-3 py-1 rounded-full border border-accent/30 text-accent hover:bg-accent-light transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="card border-red-200 bg-red-50 text-red-700 text-sm">{error}</div>
      )}

      {/* Results */}
      {results !== null && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            {results.length} results for <span className="font-medium text-gray-900">"{lastQuery}"</span>
          </p>
          {results.length === 0 ? (
            <div className="card text-gray-400 text-center py-8">No results found.</div>
          ) : (
            results.map((r, i) => <ResultCard key={r.id} result={r} rank={i + 1} />)
          )}
        </div>
      )}

      {/* Explanation */}
      {!results && !loading && (
        <div className="card bg-accent-light border-blue-200">
          <h3 className="font-semibold text-accent mb-2">How semantic search works</h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            Each SKU description is converted into a 1536-number vector (embedding) by OpenAI.
            When you search, your query is also embedded, and PostgreSQL's pgvector extension
            finds the SKUs whose vectors point in the most similar direction — measuring the
            "angle" between them (cosine similarity). Two items near each other in vector
            space share similar meaning, even if they share no keywords.
          </p>
        </div>
      )}
    </div>
  );
}
