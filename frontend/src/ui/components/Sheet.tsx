import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import type { ReactNode } from "react";

/** A bottom sheet on phones, a centred dialog from 640 px up. */
export function Sheet({ open, onOpenChange, title, children }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div className="fixed inset-0 z-40 bg-black/50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-describedby={undefined}>
              <motion.div
                className="glass fixed inset-x-0 bottom-0 z-50 max-h-[88vh] overflow-y-auto rounded-t-[28px] p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] text-text
                           sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[440px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[24px]"
                initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
              >
                <div className="mb-4 flex items-center justify-between">
                  <Dialog.Title className="font-display text-lg font-bold">{title}</Dialog.Title>
                  <Dialog.Close className="grid size-11 place-items-center rounded-full hover:bg-chip-green" aria-label="Close"><X size={20} /></Dialog.Close>
                </div>
                {children}
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
