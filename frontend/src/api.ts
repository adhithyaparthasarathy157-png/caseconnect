const base = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
export type RequestOptions = RequestInit & { token?: string };

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...options.headers,
      },
    });
  } catch (err) {
    if (import.meta.env.DEV) {
      console.error(`[CaseConnect] Network request failed to ${base}${path}:`, err);
    }
    throw new Error(
      "Unable to connect to the backend server. Please verify the API is running at " +
      base + " and try again."
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error?.message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function download(path: string, token: string) {
  const appliedFilters = sessionStorage.getItem("caseconnect_report_filters") || "";
  const separator = path.includes("?") ? "&" : "?";
  const filteredPath = appliedFilters ? `${path}${separator}${appliedFilters}` : path;
  let response: Response;
  try {
    response = await fetch(`${base}${filteredPath}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err) {
    if (import.meta.env.DEV) {
      console.error(`[CaseConnect] Export download failed to ${base}${filteredPath}:`, err);
    }
    throw new Error("Unable to reach backend server for file export.");
  }
  if (!response.ok) throw new Error("Export failed");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "caseconnect-cases.csv";
  link.click();
  URL.revokeObjectURL(url);
}
