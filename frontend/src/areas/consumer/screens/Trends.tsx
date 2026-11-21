import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTrends } from "../../../api/consumer";
import { Card, EmptyState, ErrorState, Skeleton } from "../../../ui";

function Chart({ data, field, target, color, unit }: { data: Record<string, unknown>[]; field: string; target: number | null; color: string; unit: string }) {
  return (
    <div className="h-56" role="img" aria-label={`Weekly average ${field}`}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis dataKey="label" tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
          {/* Axis scale only: keep the target line in view. */}
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={false} tickLine={false}
            domain={[0, (dataMax: number) => Math.max(dataMax, target ?? 0)]} />
          <Tooltip cursor={{ fill: "var(--chip-green)" }} contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 12 }}
            formatter={(v: number) => [`${v.toLocaleString("en-IN")} ${unit}`, "Average per logged day"]} />
          {target && <ReferenceLine y={target} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: "target", fill: "var(--text-muted)", fontSize: 11, position: "insideTopRight" }} />}
          <Bar dataKey={field} fill={color} radius={[8, 8, 0, 0]} isAnimationActive={false} />  {/* Recharts' entry animation stalls under React strict mode */}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Trends() {
  const t = useTrends();
  return (
    <div className="space-y-5">
      <Link to="/diary" className="inline-flex min-h-11 items-center gap-1 text-sm text-muted"><ArrowLeft size={16} /> Diary</Link>
      <h1 className="text-2xl font-extrabold">Trends</h1>
      {t.isPending ? <Skeleton className="h-64" /> : t.isError ? <ErrorState error={t.error} onRetry={() => t.refetch()} /> : (
        <>
          {t.data.recap ? (
            <section className="mesh rounded-[28px] p-6 text-white">
              <p className="font-display text-xl font-extrabold">{t.data.recap.title}</p>
              <ul className="mt-3 space-y-1 text-white/90">{t.data.recap.lines.map((l) => <li key={l}>{l}</li>)}</ul>
            </section>
          ) : <EmptyState title="No meals this week yet" body="Log a meal to see your weekly recap." />}
          <Card><h2 className="mb-2 font-display font-bold">Energy per logged day</h2>
            <Chart data={t.data.weeks as unknown as Record<string, unknown>[]} field="avg_energy_kcal" target={t.data.weeks[t.data.weeks.length - 1]?.energy_target ?? null} color="var(--orange-500)" unit="kcal" /></Card>
          <Card><h2 className="mb-2 font-display font-bold">Protein per logged day</h2>
            <Chart data={t.data.weeks as unknown as Record<string, unknown>[]} field="avg_protein_g" target={t.data.weeks[t.data.weeks.length - 1]?.protein_target ?? null} color="var(--green-500)" unit="g" /></Card>
          <p className="text-xs text-muted">Averages cover only days with something logged. Values are estimates, not medical advice.</p>
        </>
      )}
    </div>
  );
}
