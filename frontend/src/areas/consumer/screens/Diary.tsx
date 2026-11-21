import { useState } from "react";
import { BarChart3, ChevronLeft, ChevronRight, Pencil, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { consumer, useDay, type DiaryEntry } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, EmptyState, ErrorState, Select, Sheet, Skeleton, TrustLabel } from "../../../ui";
import { ActionError } from "../../business/shared";
import { SharePicker } from "../parts";
import { today } from "./Home";

function shift(date: string, days: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function Diary() {
  const [date, setDate] = useState(today());
  const day = useDay(date);
  const [edit, setEdit] = useState<{ e: DiaryEntry; meal: string; shares: Record<string, number>; remove: string[] } | null>(null);
  const keys = [["diary"]];
  const save = useAction(() => consumer.updateEntry(edit!.e.id, { meal_type: edit!.meal, shares: edit!.shares, remove_item_ids: edit!.remove }), keys);
  const del = useAction((id: string) => consumer.deleteEntry(id), keys);
  const label = new Date(`${date}T12:00:00Z`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
  const d = day.data;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <button aria-label="Previous day" className="grid size-11 place-items-center rounded-full hover:bg-chip-green" onClick={() => setDate(shift(date, -1))}><ChevronLeft /></button>
        <h1 className="font-display text-xl font-bold">{date === today() ? "Today" : label}</h1>
        <button aria-label="Next day" disabled={date >= today()} className="grid size-11 place-items-center rounded-full hover:bg-chip-green disabled:opacity-30" onClick={() => setDate(shift(date, 1))}><ChevronRight /></button>
      </div>
      {day.isPending ? <Skeleton className="h-64" /> : day.isError ? <ErrorState error={day.error} onRetry={() => day.refetch()} /> : d && (
        <>
          {d.read_only && <Banner tone="note" title="Read only">Your access has ended. You can read and export your diary.</Banner>}
          <Card className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {([["energy_kcal", "Energy"], ["protein_g", "Protein"], ["carbs_g", "Carbs"], ["fat_g", "Fat"]] as const).map(([k, l]) => (
              <div key={k}><p className="text-muted">{l}</p><p className={`font-semibold ${k === "energy_kcal" ? "text-orange-text" : ""}`}>{d.totals[k]?.display ?? (d.entries.length ? "Not available" : "–")}</p></div>
            ))}
            {d.remaining_display && <p className="col-span-full text-muted">{d.remaining_display}</p>}
            {!d.read_only && <Link to="/trends" className="col-span-full inline-flex min-h-11 items-center gap-2 font-medium text-green-text"><BarChart3 size={18} /> Weekly trends</Link>}
          </Card>
          {d.entries.length === 0 ? <EmptyState title="Nothing logged" body="Add dishes from a restaurant or dish page." /> : d.entries.map((e) => (
            <Card key={e.id} className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-display font-bold capitalize">{e.meal_type}</p>
                  <p className="text-xs text-muted">{[e.restaurant, new Date(e.eaten_at).toLocaleTimeString("en-IN", { timeStyle: "short" }), e.energy_display].filter(Boolean).join(" · ")}</p>
                </div>
                {!d.read_only && <div className="flex">
                  <button aria-label="Edit meal" className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"
                    onClick={() => setEdit({ e, meal: e.meal_type, shares: {}, remove: [] })}><Pencil size={18} /></button>
                  <button aria-label="Delete meal" className="grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green" onClick={() => del.mutate(e.id)}><Trash2 size={18} /></button>
                </div>}
              </div>
              <ul className="divide-y divide-line">{e.items.map((i) => (
                <li key={i.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{i.component_label ? `${i.component_label}: ` : ""}{i.name}</p>
                    <p className="text-xs text-muted">{i.share_display} · {i.serving_label}</p>
                    <div className="mt-1"><TrustLabel kind={i.trust.label} /></div>
                  </div>
                  <span className="shrink-0 font-semibold text-orange-text">{i.energy?.display ?? "No data"}</span>
                </li>
              ))}</ul>
            </Card>
          ))}
        </>
      )}
      <ActionError error={del.error} />
      <Sheet open={edit !== null} onOpenChange={(o) => { if (!o) { setEdit(null); save.reset(); } }} title="Edit meal">
        {edit && (
          <div className="space-y-4">
            <Select label="Meal" value={edit.meal} onChange={(ev) => setEdit({ ...edit, meal: ev.target.value })} options={["breakfast", "lunch", "dinner", "snack"].map((m) => ({ value: m, label: m[0].toUpperCase() + m.slice(1) }))} />
            {edit.e.items.filter((i) => !edit.remove.includes(i.id)).map((i) => (
              <div key={i.id} className="space-y-2 rounded-2xl border border-line p-3">
                <div className="flex items-center justify-between"><span className="font-medium">{i.name}</span>
                  <button className="text-sm text-muted underline" onClick={() => setEdit({ ...edit, remove: [...edit.remove, i.id] })}>Remove</button></div>
                <SharePicker value={edit.shares[i.id] ?? i.share_fraction} onChange={(v) => setEdit({ ...edit, shares: { ...edit.shares, [i.id]: v } })} />
              </div>
            ))}
            <p className="text-xs text-muted">Values stay as they were when you logged them, even if the restaurant changes its recipe.</p>
            <ActionError error={save.error} />
            <Button block loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => setEdit(null), onError: () => undefined })}>Save</Button>
          </div>
        )}
      </Sheet>
    </div>
  );
}
