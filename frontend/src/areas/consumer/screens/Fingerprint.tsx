import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, X } from "lucide-react";
import { consumer, feedback, useFingerprint } from "../../../api/consumer";
import { useAction } from "../../../api/business";
import { Banner, Button, Card, EmptyState, ErrorState, Skeleton } from "../../../ui";
import { ActionError } from "../../business/shared";

/** Everything learned about the diner, each tile removable. */
export default function Fingerprint() {
  const fp = useFingerprint();
  const remove = useAction((id: string) => feedback.removeLearned(id), [["fingerprint"]]);
  const consent = useAction((on: boolean) => consumer.consent("learned_preferences", on), [["fingerprint"], ["profile"]]);
  return (
    <div className="space-y-5">
      <Link to="/profile" className="inline-flex min-h-11 items-center gap-1 text-sm text-muted"><ArrowLeft size={16} /> Profile</Link>
      <h1 className="text-2xl font-extrabold">Food fingerprint</h1>
      {fp.isPending ? <Skeleton className="h-48" /> : fp.isError ? <ErrorState error={fp.error} onRetry={() => fp.refetch()} /> : !fp.data.consented ? (
        <Card className="space-y-3">
          <p>{fp.data.note}</p>
          <p className="text-sm text-muted">We look at what you log, such as cuisines and dishes you repeat. It never changes your diet, restrictions or allergy filters, and we never guess health conditions or religion.</p>
          <Button loading={consent.isPending} onClick={() => consent.mutate(true)}>Turn on</Button>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card><p className="text-sm text-muted">Top cuisines</p><p className="font-display font-bold">{fp.data.top_cuisines.join(", ") || "Not enough yet"}</p></Card>
            <Card><p className="text-sm text-muted">Protein eating out</p><p className="font-display font-bold">{fp.data.avg_protein_eating_out ?? "Not enough yet"}</p></Card>
            <Card><p className="text-sm text-muted">Most repeated</p><p className="font-display font-bold">{fp.data.most_repeated.join(", ") || "Nothing yet"}</p></Card>
          </div>
          <h2 className="font-display text-lg font-bold">What we've learned</h2>
          {fp.data.learned.length === 0 ? <EmptyState title="Nothing learned yet" body="This updates overnight from your diary." /> : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <AnimatePresence>{fp.data.learned.map((p) => (
                <motion.div key={p.id} layout exit={{ opacity: 0, scale: 0.9 }} className="card relative p-4 pr-12">
                  <p className="text-xs uppercase tracking-wide text-muted">{p.kind}</p>
                  <p className="font-medium">{p.display}</p>
                  <button aria-label={`Remove ${p.value}`} onClick={() => remove.mutate(p.id)}
                    className="absolute right-1 top-1 grid size-11 place-items-center rounded-full text-muted hover:bg-chip-green"><X size={16} /></button>
                </motion.div>
              ))}</AnimatePresence>
            </div>
          )}
          <ActionError error={remove.error} />
          <Banner tone="note" title={fp.data.note}>Removed items aren't learned again.</Banner>
          <Button variant="ghost" loading={consent.isPending} onClick={() => consent.mutate(false)}>Turn off and delete what was learned</Button>
        </>
      )}
    </div>
  );
}
