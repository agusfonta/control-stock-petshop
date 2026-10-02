import { Link } from "react-router";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold">Animall — Control Stock Petshop</h1>
      <nav className="flex gap-4">
        <Link className="underline" to="/pos">
          POS mostrador
        </Link>
        <Link className="underline" to="/stock">
          Stock
        </Link>
      </nav>
    </main>
  );
}
