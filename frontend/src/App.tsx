import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Inventory from "./pages/Inventory";
import SemanticSearch from "./pages/SemanticSearch";
import AskVikram from "./pages/AskVikram";
import Metrics from "./pages/Metrics";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="search" element={<SemanticSearch />} />
          <Route path="ask" element={<AskVikram />} />
          <Route path="metrics" element={<Metrics />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
