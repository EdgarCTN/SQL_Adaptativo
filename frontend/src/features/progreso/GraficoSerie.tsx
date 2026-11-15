import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface FilaGrafico {
  etiqueta: string; // eje X (ej. «1», «2»…)
  detalle: string; // texto del tooltip (ej. «Cierre 2 · 12 nov 2026»)
  valor: number | null;
}

interface Props {
  titulo: string;
  descripcion: string; // qué mide, en palabras del estudiante
  filas: FilaGrafico[];
  alternativa: string; // texto alternativo visible: reemplaza al gráfico para quien no lo ve
  formato: (v: number) => string;
  dominio?: [number | "auto", number | "auto"];
  ticks?: number[];
  escalon?: boolean;
  lineaReferencia?: { y: number; etiqueta: string };
  etiquetaX: string;
}

const COLOR = "#4338ca"; // indigo-700: contraste suficiente sobre fondo blanco

export default function GraficoSerie({
  titulo, descripcion, filas, alternativa, formato, dominio = [0, "auto"], ticks, escalon = false, lineaReferencia, etiquetaX,
}: Props) {
  return (
    <figure className="rounded-xl border border-slate-200 bg-white p-4">
      <figcaption>
        <h3 className="text-base font-semibold text-slate-900">{titulo}</h3>
        <p className="text-xs text-slate-600">{descripcion}</p>
      </figcaption>
      {/* El gráfico es decorativo para lectores de pantalla: su equivalente es el texto alternativo y la tabla de datos. */}
      <div aria-hidden="true" className="mt-2 h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={filas} margin={{ top: 8, right: 12, bottom: 16, left: 0 }} accessibilityLayer={false}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="etiqueta"
              tick={{ fontSize: 11, fill: "#475569" }}
              label={{ value: etiquetaX, position: "insideBottom", offset: -10, fontSize: 11, fill: "#475569" }}
            />
            <YAxis
              domain={dominio}
              ticks={ticks}
              allowDecimals={!ticks}
              tickFormatter={(v: number) => formato(v)}
              tick={{ fontSize: 11, fill: "#475569" }}
              width={48}
            />
            <Tooltip
              labelFormatter={(_, carga) => carga?.[0]?.payload?.detalle ?? ""}
              formatter={(v) => [typeof v === "number" ? formato(v) : "—", titulo]}
            />
            {lineaReferencia && (
              <ReferenceLine
                y={lineaReferencia.y}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{ value: lineaReferencia.etiqueta, position: "insideTopRight", fontSize: 10, fill: "#475569" }}
              />
            )}
            <Line
              type={escalon ? "stepAfter" : "monotone"}
              dataKey="valor"
              stroke={COLOR}
              strokeWidth={2}
              dot={{ r: 3, fill: COLOR }}
              activeDot={{ r: 5 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-sm text-slate-700">{alternativa}</p>
    </figure>
  );
}
