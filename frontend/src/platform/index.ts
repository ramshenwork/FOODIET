// Device features behind one small interface (spec section 15). The Capacitor shell will
// replace these browser versions without touching the screens that call them.

export interface Coordinates { latitude: number; longitude: number; accuracy: number }

export const platform = {
  /** Asks the browser for the user's location. Resolves null if refused or unavailable. */
  locate(): Promise<Coordinates | null> {
    return new Promise((resolve) => {
      if (!("geolocation" in navigator)) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy }),
        () => resolve(null),
        { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
      );
    });
  },

  /** Browser notifications; native push arrives with the phone app. */
  async notify(title: string, body: string): Promise<boolean> {
    if (!("Notification" in window)) return false;
    const perm = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    if (perm !== "granted") return false;
    new Notification(title, { body, icon: "/icon.svg" });
    return true;
  },

  /** In the browser a QR code is scanned with the phone camera app, which opens /q/{code} directly. */
  async scanQr(): Promise<string | null> {
    return null;
  },

  /** A stable per-install id, used for the device limit and the one-trial-per-device rule. */
  deviceId(): string {
    const KEY = "device_id";
    try {
      let id = localStorage.getItem(KEY);
      if (!id) { id = crypto.randomUUID(); localStorage.setItem(KEY, id); }
      return id;
    } catch {
      return "unavailable";
    }
  },
};
