// Minimal service worker: makes the app installable and caches the app shell.
// API responses are never cached here (paid data and access decisions stay on the server).
const SHELL = "shell-v1";
self.addEventListener("install", (e) => { self.skipWaiting(); e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/"]))); });
self.addEventListener("activate", (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.pathname.startsWith("/q/")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => caches.match("/")));
  }
});
