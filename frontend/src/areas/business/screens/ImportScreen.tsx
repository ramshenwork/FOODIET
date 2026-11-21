import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp } from "lucide-react";
import { calls, useAction, type ImportRow, type MenuImport } from "../../../api/business";
import { Banner, Button, Card } from "../../../ui";
import { useBiz } from "../context";
import { ActionError, BranchPicker, DIET_OPTIONS, PageHeader } from "../shared";

export default function ImportScreen() {
  const { business, branchId } = useBiz();
  const nav = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [imp, setImp] = useState<MenuImport | null>(null);
  const [rows, setRows] = useState<ImportRow[]>([]);
  const upload = useAction((f: File) => calls.uploadImport(business.id, branchId, f), []);
  const confirm = useAction(async () => {
    await calls.updateImport(business.id, imp!.id, rows);
    return calls.confirmImport(business.id, imp!.id);
  }, [["menu", business.id, branchId], ["dashboard", business.id]]);
  const patch = (i: number, p: Partial<ImportRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));

  return (
    <>
      <PageHeader title="Import a menu" subtitle="Upload a CSV, a photo or a PDF. You check every row; nothing is published from an import." actions={<BranchPicker />} />
      {!imp ? (
        <Card className="space-y-4">
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-line p-10 text-center hover:border-green">
            <FileUp size={28} className="text-green-text" />
            <span className="font-medium">{file ? file.name : "Choose a file"}</span>
            <span className="text-sm text-muted">CSV with a “name” column (optional: price, category, diet, description), or a JPEG, PNG, WebP or PDF. Up to 10 MB.</span>
            <input type="file" className="sr-only" accept=".csv,text/csv,image/jpeg,image/png,image/webp,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <ActionError error={upload.error} />
          <Button disabled={!file} loading={upload.isPending} onClick={() => file && upload.mutate(file, { onSuccess: (r) => { setImp(r); setRows(r.rows); } })}>Upload and read</Button>
        </Card>
      ) : imp.status === "needs_ai" ? (
        <Card className="space-y-4">
          <Banner tone="note" title="Saved, but not read automatically">{imp.message}</Banner>
          <Button variant="secondary" onClick={() => { setImp(null); setFile(null); }}>Upload another file</Button>
        </Card>
      ) : confirm.data ? (
        <Card className="space-y-4">
          <Banner tone="success" title={`Added ${confirm.data.created} dishes as drafts`}>Link recipes and publish them from the menu when ready.</Banner>
          <Button onClick={() => nav("/business/menu")}>Go to the menu</Button>
        </Card>
      ) : (
        <Card className="space-y-4 overflow-x-auto p-0">
          <div className="px-5 pt-5"><Banner tone="note" title="Check each row">{imp.message}</Banner></div>
          <table className="dtable min-w-[760px]">
            <thead><tr><th>Add</th><th>Name</th><th>Price (₹)</th><th>Category</th><th>Diet</th><th>Matched dish</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={r.include ? "" : "opacity-50"}>
                  <td><input type="checkbox" aria-label={`Include ${r.name}`} className="size-5 accent-[var(--green-500)]" checked={r.include} onChange={(e) => patch(i, { include: e.target.checked })} /></td>
                  <td><input aria-label="Name" value={r.name} onChange={(e) => patch(i, { name: e.target.value })} className="min-h-11 w-full rounded-xl border border-line bg-card px-2" /></td>
                  <td><input aria-label="Price" inputMode="decimal" value={r.price_inr ?? ""} onChange={(e) => patch(i, { price_inr: e.target.value === "" ? null : Number(e.target.value) })} className="min-h-11 w-24 rounded-xl border border-line bg-card px-2" /></td>
                  <td><input aria-label="Category" value={r.category ?? ""} onChange={(e) => patch(i, { category: e.target.value || null })} className="min-h-11 w-32 rounded-xl border border-line bg-card px-2" /></td>
                  <td><select aria-label="Diet" value={r.diet_class ?? ""} onChange={(e) => patch(i, { diet_class: e.target.value || null })} className="min-h-11 rounded-xl border border-line bg-card px-2">
                    {DIET_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></td>
                  <td>{r.canonical_dish_name ? <span className="inline-flex items-center gap-2">{r.canonical_dish_name}
                    <button className="text-xs text-muted underline" onClick={() => patch(i, { canonical_dish_id: null, canonical_dish_name: null })}>clear</button></span>
                    : <span className="text-muted">No match</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="space-y-3 px-5 pb-5">
            <ActionError error={confirm.error} />
            <Button loading={confirm.isPending} onClick={() => confirm.mutate(undefined)}>Add {rows.filter((r) => r.include).length} dishes as drafts</Button>
          </div>
        </Card>
      )}
    </>
  );
}
