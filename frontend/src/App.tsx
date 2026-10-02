import { Route, Routes } from "react-router";
import HomePage from "@/pages/HomePage";
import PosPage from "@/pages/PosPage";
import StockPage from "@/pages/StockPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/pos" element={<PosPage />} />
      <Route path="/stock" element={<StockPage />} />
    </Routes>
  );
}
