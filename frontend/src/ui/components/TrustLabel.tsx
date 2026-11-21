import { BadgeCheck, CircleDashed, Store, type LucideIcon } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import clsx from "clsx";
import type { TrustLabelKind } from "../../api/types";

// Colour never stands alone: every label carries an icon and words (spec section 11).
const LABELS: Record<TrustLabelKind, { text: string; meaning: string; icon: LucideIcon | null; cls: string }> = {
  verified: {
    text: "Verified", icon: BadgeCheck, cls: "bg-green text-ink",
    meaning: "Recipe and portion checked by an audit or lab test.",
  },
  declared: {
    text: "Restaurant-declared", icon: Store, cls: "border border-green text-green-text",
    meaning: "Calculated from this outlet's own recipe.",
  },
  estimated: {
    text: "Estimated", icon: null, cls: "bg-stone/15 text-muted border border-stone/40",
    meaning: "Calculated from a reference recipe for this dish and region, not this outlet's own.",
  },
  no_data: {
    text: "No data", icon: CircleDashed, cls: "border border-dashed border-line text-muted",
    meaning: "No recipe has been declared and no reference recipe matches.",
  },
};

export function TrustLabel({ kind, note }: { kind: TrustLabelKind; note?: string }) {
  const l = LABELS[kind];
  const Icon = l.icon;
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button type="button" className={clsx("inline-flex h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-xs font-semibold", l.cls)}>
            {Icon ? <Icon size={14} strokeWidth={2.4} aria-hidden /> : <span aria-hidden className="text-sm leading-none">~</span>}
            {l.text}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content sideOffset={6} className="card z-50 max-w-64 px-3 py-2 text-xs text-text">
            {l.meaning}{note ? <span className="mt-1 block text-muted">{note}</span> : null}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
