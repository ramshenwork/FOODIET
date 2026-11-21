import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { consumer, usePreview } from "../../../api/consumer";
import { openCheckout, waitForAccess } from "../../../api/payments";
import { useAction } from "../../../api/business";
import type { Entitlement } from "../../../api/types";
import { useConfig } from "../../../api/hooks";
import { platform } from "../../../platform";
import { Banner, Button, Card, CountUp, ErrorState, Field, Skeleton } from "../../../ui";
import { ActionError } from "../../business/shared";
import { LocationPrompt } from "../LocationPrompt";
import { useLocationCtx } from "../location";

function refCode(): string | null {
  try { return new URLSearchParams(window.location.search).get("ref") ?? sessionStorage.getItem("ref"); } catch { return null; }
}

/** Preview (or lapsed) users: coverage, restaurant and dish names, and the way in. No nutrition values. */
export default function Paywall({ ent }: { ent: Entitlement }) {
  const { coords } = useLocationCtx();
  const preview = usePreview(coords);
  const { data: c } = useConfig();
  const qc = useQueryClient();
  const [area, setArea] = useState("");
  const [joined, setJoined] = useState(false);
  const done = () => { qc.invalidateQueries({ queryKey: ["entitlement"] }); qc.invalidateQueries({ queryKey: ["me"] }); };
  const trial = useAction(() => consumer.trial(platform.deviceId()), []);
  const sub = useAction(async (plan: "monthly" | "yearly") => {
    const r = await consumer.subscribe(plan, refCode(), crypto.randomUUID());
    if (r.checkout) {   // live: pay in Razorpay, then wait for the server's confirmation
      if ((await openCheckout(r.checkout)) === "closed") return;
    }
    await waitForAccess((e) => e.can.nutrition);
  }, []);
  const waitlist = useAction(() => consumer.waitlist(area), []);

  return (
    <div className="space-y-6">
      <section className="mesh relative overflow-hidden rounded-[28px] p-6 text-white">
        <Sparkles className="relative" />
        <h1 className="relative mt-3 text-3xl font-extrabold">{ent.display.title}</h1>
        <p className="relative mt-2 text-white/85">{ent.can.start_trial ? `${c?.trial_days ?? 7} days free, no payment details needed.` : ent.display.detail}</p>
      </section>

      {!coords ? <LocationPrompt title="How many restaurants near you have declared recipes?" /> :
        preview.isPending ? <Skeleton className="h-40" /> : preview.isError ? <ErrorState error={preview.error} onRetry={() => preview.refetch()} /> : (
          <>
            <Card>
              <p className="font-display text-5xl font-extrabold text-orange-text"><CountUp value={preview.data.coverage.declared_restaurants} /></p>
              <p className="mt-1 text-muted">{preview.data.coverage.display}</p>
            </Card>
            {preview.data.coverage.waitlist ? (
              <Card className="space-y-3">
                <h2 className="font-display text-lg font-bold">We're not in your area yet</h2>
                <p className="text-sm text-muted">Join the waitlist and we'll email you when enough restaurants near you have declared recipes.</p>
                {joined ? <Banner tone="success" title="You're on the list" /> : (
                  <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); waitlist.mutate(undefined, { onSuccess: () => setJoined(true) }); }}>
                    <div className="flex-1"><Field label="Your area" value={area} onChange={(e) => setArea(e.target.value)} placeholder="e.g. Kondapur, Hyderabad" /></div>
                    <Button type="submit" className="self-end" loading={waitlist.isPending} disabled={area.trim().length < 2}>Join</Button>
                  </form>
                )}
              </Card>
            ) : (
              <Card className="space-y-3">
                {ent.can.start_trial && <Button block loading={trial.isPending} onClick={() => trial.mutate(undefined, { onSuccess: done })}>Start {c?.trial_days ?? 7}-day free trial</Button>}
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" loading={sub.isPending && sub.variables === "monthly"} onClick={() => sub.mutate("monthly", { onSuccess: done })}>
                    Monthly{c?.price_monthly_inr != null ? ` · ₹${c.price_monthly_inr}` : ""}</Button>
                  <Button variant="secondary" loading={sub.isPending && sub.variables === "yearly"} onClick={() => sub.mutate("yearly", { onSuccess: done })}>
                    Yearly{c?.price_yearly_inr != null ? ` · ₹${c.price_yearly_inr}` : ""}</Button>
                </div>
                {c?.payments_mode === "mock" && <p className="text-xs text-muted">Test mode: no real payment is taken.</p>}
                {c?.price_monthly_inr == null && <p className="text-xs text-muted">Prices are set at launch.</p>}
                <ActionError error={trial.error ?? sub.error} />
              </Card>
            )}
            <section className="space-y-3">
              <h2 className="font-display text-lg font-bold">Near you</h2>
              {preview.data.restaurants.map((r) => (
                <Card key={r.id} className="space-y-1">
                  <div className="flex justify-between gap-2"><p className="font-semibold">{r.name}</p><span className="text-sm text-muted">{r.distance_display}</span></div>
                  <p className="text-sm text-muted">{r.declared_dishes} of {r.total_dishes} dishes with the restaurant's own recipe</p>
                  <p className="text-sm">{r.dish_names.join(" · ")}</p>
                </Card>
              ))}
            </section>
          </>
        )}
    </div>
  );
}
