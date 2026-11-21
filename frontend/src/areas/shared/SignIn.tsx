import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Mail } from "lucide-react";
import { ApiError } from "../../api/client";
import { useConfig, useRequestOtp, useVerifyOtp } from "../../api/hooks";
import { useAreaTheme } from "../../app/theme";
import { platform } from "../../platform";
import { Button, Field } from "../../ui";

export default function SignIn({ role }: { role: "consumer" | "business" }) {
  useAreaTheme(role === "business" ? "business" : "consumer");
  const { data: config } = useConfig();
  const nav = useNavigate();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const request = useRequestOtp();
  const verify = useVerifyOtp();

  const err = (e: unknown) => (e instanceof ApiError ? e.fields?.[0]?.message ?? e.message : undefined);

  const sendCode = (e: React.FormEvent) => {
    e.preventDefault();
    request.mutate({ email, role }, { onSuccess: () => setStep("code") });
  };
  const checkCode = (e: React.FormEvent) => {
    e.preventDefault();
    verify.mutate({ email, code, role, device_id: platform.deviceId() },
      { onSuccess: () => nav(role === "business" ? "/business" : "/", { replace: true }) });
  };

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-[400px]">
        <p className="mb-8 font-display text-2xl font-extrabold tracking-tight">
          {config?.app_name ?? " "}{role === "business" && <span className="ml-2 text-base font-semibold text-green-text">for restaurants</span>}
        </p>
        <AnimatePresence mode="wait" initial={false}>
          {step === "email" ? (
            <motion.form key="email" onSubmit={sendCode} className="space-y-5"
              initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.22 }}>
              <h1 className="text-3xl font-extrabold">Sign in</h1>
              <p className="text-muted">We'll email you a six-digit code. No password needed.</p>
              <Field label="Email" type="email" autoComplete="email" inputMode="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} error={err(request.error)} placeholder="you@example.com" />
              <Button type="submit" block loading={request.isPending}><Mail size={18} /> Email me a code</Button>
            </motion.form>
          ) : (
            <motion.form key="code" onSubmit={checkCode} className="space-y-5"
              initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: 0.22 }}>
              <button type="button" onClick={() => { setStep("email"); setCode(""); verify.reset(); }}
                className="-ml-2 inline-flex min-h-11 items-center gap-1 rounded-full px-2 text-sm text-muted hover:text-text">
                <ArrowLeft size={16} /> Change email
              </button>
              <h1 className="text-3xl font-extrabold">Enter your code</h1>
              <p className="text-muted">Sent to <span className="font-medium text-text">{email}</span>. It expires in {request.data?.ttl_minutes ?? 10} minutes.</p>
              <Field label="Six-digit code" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required
                value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} error={err(verify.error)}
                className="font-display text-2xl tracking-[0.5em]" />
              <Button type="submit" block loading={verify.isPending} disabled={code.length !== 6}>Continue</Button>
              <button type="button" className="min-h-11 text-sm font-medium text-green-text" onClick={() => request.mutate({ email, role })}>
                Send a new code
              </button>
            </motion.form>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
