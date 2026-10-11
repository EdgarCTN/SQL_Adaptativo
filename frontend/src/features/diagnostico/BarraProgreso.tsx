interface Props {
  valor: number; // 0 a 100
  etiqueta: string;
}

export default function BarraProgreso({ valor, etiqueta }: Props) {
  const v = Math.max(0, Math.min(100, Math.round(valor)));
  return (
    <div>
      <p className="mb-1 text-sm text-slate-600">{etiqueta}</p>
      <div
        role="progressbar"
        aria-label="Progreso del diagnóstico"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={v}
        className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
      >
        <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}
