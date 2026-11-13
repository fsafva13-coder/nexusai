// VITE_BACKEND_URL may be http(s):// or ws(s)://; both forms are accepted.
const RAW = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");

export const BACKEND_URL = RAW;
export const httpBase = () => RAW.replace(/^ws/, "http");
export const wsBase = () => RAW.replace(/^http/, "ws");

export async function fetchConfig(signal) {
  const res = await fetch(`${httpBase()}/api/config`, { signal });
  if (!res.ok) throw new Error(`Backend responded with ${res.status}`);
  return res.json();
}
