import { useState } from "react";
import { LocateFixed, MapPin } from "lucide-react";
import { Button, Card, Field } from "../../ui";
import { useLocationCtx } from "./location";

/** Asks for location. Typed coordinates are offered in development only (no maps API by design). */
export function LocationPrompt({ title = "Find restaurants near you" }: { title?: string }) {
  const { status, request, setManual } = useLocationCtx();
  const [lat, setLat] = useState("17.4200");
  const [lng, setLng] = useState("78.4600");
  return (
    <Card className="space-y-4">
      <div className="grid size-11 place-items-center rounded-2xl bg-chip-green text-green-text"><MapPin size={20} /></div>
      <h2 className="font-display text-xl font-bold">{title}</h2>
      <p className="text-sm text-muted">We use your location only to measure distance to restaurants. It isn't stored.</p>
      {status === "denied" && <p className="text-sm text-muted">Location wasn't shared. You can allow it in your browser settings and try again.</p>}
      <Button loading={status === "locating"} onClick={request}><LocateFixed size={18} /> Use my location</Button>
      {import.meta.env.DEV && (
        <form className="grid grid-cols-[1fr_1fr_auto] items-end gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); setManual({ lat: Number(lat), lng: Number(lng) }); }}>
          <Field label="Latitude (dev)" value={lat} onChange={(e) => setLat(e.target.value)} />
          <Field label="Longitude (dev)" value={lng} onChange={(e) => setLng(e.target.value)} />
          <Button type="submit" variant="secondary">Set</Button>
        </form>
      )}
    </Card>
  );
}
