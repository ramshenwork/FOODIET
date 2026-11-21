import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { platform } from "../../platform";
import type { Coords } from "../../api/consumer";

type Status = "idle" | "locating" | "ready" | "denied";
interface Ctx { coords: Coords | null; status: Status; request: () => Promise<void>; setManual: (c: Coords) => void }
const LocationCtx = createContext<Ctx | null>(null);
const KEY = "last_location";

function read(): Coords | null {
  try { const v = sessionStorage.getItem(KEY); return v ? JSON.parse(v) : null; } catch { return null; }
}

/** The browser supplies the location with permission; the server does all distance maths (PostGIS). */
export function LocationProvider({ children }: { children: ReactNode }) {
  const [coords, setCoords] = useState<Coords | null>(read);
  const [status, setStatus] = useState<Status>(coords ? "ready" : "idle");
  const save = (c: Coords) => { setCoords(c); setStatus("ready"); try { sessionStorage.setItem(KEY, JSON.stringify(c)); } catch { /* ignore */ } };
  const request = useCallback(async () => {
    setStatus("locating");
    const c = await platform.locate();
    if (c) save({ lat: c.latitude, lng: c.longitude }); else setStatus("denied");
  }, []);
  return <LocationCtx.Provider value={{ coords, status, request, setManual: save }}>{children}</LocationCtx.Provider>;
}

export function useLocationCtx(): Ctx {
  const c = useContext(LocationCtx);
  if (!c) throw new Error("useLocationCtx outside LocationProvider");
  return c;
}
