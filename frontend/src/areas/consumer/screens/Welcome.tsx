import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { useConfig } from "../../../api/hooks";
import { useAreaTheme } from "../../../app/theme";
import { Button } from "../../../ui";

const INCLUDED = [
  "Nutrition for each dish at each restaurant, from its own recipe where declared",
  "Trust labels and honest ranges, never false precision",
  "Dishes near you that fit your goal",
  "A diary that handles shared plates, thalis and portions",
  "Healthier options from the restaurant's real menu",
];

/** Shown before any questions: the price, what's included, and the trial. */
export default function Welcome() {
  useAreaTheme("consumer");
  const { data: c } = useConfig();
  const after = c?.price_monthly_inr != null
    ? `Then ₹${c.price_monthly_inr}/month${c.price_yearly_inr ? ` or ₹${c.price_yearly_inr}/year` : ""}.` : "Price set at launch.";
  return (
    <main className="mx-auto min-h-dvh max-w-xl px-4 py-8">
      <section className="mesh relative overflow-hidden rounded-[28px] p-7 text-white">
        <div className="absolute -right-10 -top-12 size-52 rounded-full bg-orange/40 blur-3xl" aria-hidden />
        <p className="relative font-display text-lg font-extrabold">{c?.app_name}</p>
        <h1 className="relative mt-6 text-4xl font-extrabold leading-tight">Know what's on the plate before you order.</h1>
        <p className="relative mt-3 text-white/85">The same dish name hides very different recipes. We show what this restaurant's version contains.</p>
      </section>
      <ul className="mt-6 space-y-3">
        {INCLUDED.map((i) => <li key={i} className="flex gap-3"><Check size={20} className="mt-0.5 shrink-0 text-green-text" /><span>{i}</span></li>)}
      </ul>
      <div className="mt-8 space-y-3">
        <p className="font-display text-xl font-bold">{c ? `${c.trial_days}-day free trial` : " "}</p>
        <p className="text-muted">{after} No payment details for the trial.</p>
        <Link to="/sign-in" className="block"><Button block>Start with your email</Button></Link>
        <p className="text-center text-xs text-muted">Restaurants: <Link className="underline" to="/business/sign-in">sign in here</Link></p>
      </div>
    </main>
  );
}
