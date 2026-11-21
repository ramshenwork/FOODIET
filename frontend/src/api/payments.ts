// Payments: open Razorpay Checkout (live) and wait for the server to confirm. The browser never grants access:
// it polls GET /me/entitlement until the server's record changes after the verified webhook.
import { api } from "./client";
import type { Entitlement } from "./types";

declare global { interface Window { Razorpay?: new (o: Record<string, unknown>) => { open: () => void } } }

function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load the payment page."));
    document.head.appendChild(s);
  });
}

/** Opens Razorpay Checkout with server-provided options; resolves when the diner finishes or closes it. */
export async function openCheckout(options: Record<string, unknown>): Promise<"paid" | "closed"> {
  await loadCheckout();
  return new Promise((resolve) => {
    const rz = new window.Razorpay!({ ...options, handler: () => resolve("paid"), modal: { ondismiss: () => resolve("closed") } });
    rz.open();
  });
}

/** Polls until the server reports a capability change, or gives up after about a minute. */
export async function waitForAccess(check: (e: Entitlement) => boolean, tries = 30): Promise<boolean> {
  for (let i = 0; i < tries; i++) {
    const e = await api<Entitlement>("/me/entitlement");
    if (check(e)) return true;
    await new Promise((r) => setTimeout(r, 2000));
  }
  return false;
}
