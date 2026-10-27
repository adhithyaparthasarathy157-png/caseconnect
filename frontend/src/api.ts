const base = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
export type RequestOptions = RequestInit & { token?: string };
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}), ...options.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.error?.message || `Request failed (${response.status})`); }
  return response.json() as Promise<T>;
}
export async function download(path: string, token: string) {
  const response = await fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("Export failed");
  const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = "caseconnect-cases.csv"; link.click(); URL.revokeObjectURL(url);
}
