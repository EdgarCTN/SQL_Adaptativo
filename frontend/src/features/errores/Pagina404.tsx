
export default function Pagina404({ mensaje = "La página que buscas no existe o cambió de lugar." }: { mensaje?: string }) {
  return (
    <main className="mx-auto mt-24 max-w-md px-4 text-center">
      <p className="text-5xl font-bold text-indigo-600">404</p>
      <h1 className="mt-3 text-xl font-semibold text-slate-900">No encontramos esta página</h1>
      <p className="mt-2 text-sm text-slate-600">{mensaje}</p>
      <a href="/" className="mt-6 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
        Volver al inicio
      </a>
    </main>
  );
}
