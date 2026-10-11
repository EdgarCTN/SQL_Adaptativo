import { Link } from "react-router-dom";

export default function Pagina403() {
  return (
    <main className="mx-auto mt-24 max-w-md px-4 text-center">
      <p className="text-5xl font-bold text-indigo-600">403</p>
      <h1 className="mt-3 text-xl font-semibold text-slate-900">No tienes permiso para ver esta página</h1>
      <p className="mt-2 text-sm text-slate-600">Tu cuenta no tiene acceso a esta sección.</p>
      <Link to="/" className="mt-6 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
        Volver al inicio
      </Link>
    </main>
  );
}
