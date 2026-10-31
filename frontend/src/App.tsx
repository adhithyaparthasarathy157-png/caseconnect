import { FormEvent, useEffect, useRef, useState } from "react";

import { api, download } from "./api";
import { dateOnlyForApi, formatDateOnly, formatDateTime } from "./dateTime";
import { InstitutionPortal } from "./InstitutionPortal";
import { CaseSlaPanel, SlaManagementPage } from "./SlaManagement";

type Tab = "Overview" | "Cases" | "Institutions" | "Overlaps" | "Alerts" | "Reports" | "Audit" | "AI Screening" | "SLA Management";
type Row = Record<string, unknown>;
type Bureau = { id: number; code: string; name: string };
type User = { id: number; full_name: string; email?: string; role: string; is_active?: boolean; bureau_id: number | null; institution_id: number | null };
type Case = Row & { id: number; case_id: string; institution_id: number; current_bureau_id: number; assigned_officer_id?: number | null; status: string; subject: string; description: string; receipt_date: string; category: string; priority: string };
type CaseContext = { case: Case; history: Row[]; overlaps: Row[]; alerts: Row[]; coordination: Row[] };
type Profile = Row & { id: number; name: string; permanent_id?: string | null; permanent_id_verified: boolean; total_cases: number; cases_by_status: Record<string, number>; cases: Case[]; related_overlaps: Row[]; related_coordination: Row[]; accounts?: User[] };

const tabs: Tab[] = ["Overview", "Cases", "Institutions", "Overlaps", "Alerts", "Reports", "Audit", "AI Screening", "SLA Management"];
const paths: Partial<Record<Tab, string>> = { Institutions: "/api/institutions", Overlaps: "/api/overlaps", Alerts: "/api/alerts", Audit: "/api/audit-events" };
const statuses = ["Received", "Under Review", "Under Process", "Pending Institution Response", "Transferred", "Escalated", "Disposed", "Closed"];
const today = () => {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
};

const SENSITIVE_KEYS = new Set(["password", "token", "secret", "access_token", "hashed_password", "jwt"]);
const FIELD_LABELS: Record<string, string> = {
  status: "Status",
  current_bureau_id: "Current Bureau",
  originating_bureau_id: "Originating Bureau",
  assigned_officer_id: "Assigned Officer",
  institution_id: "Institution",
  priority: "Priority",
  subject: "Subject",
  category: "Category",
  subcategory: "Subcategory",
  receipt_date: "Receipt Date",
  source_channel: "Source Channel",
  expected_disposal_date: "Expected Disposal",
  next_action: "Next Action",
  remarks: "Remarks",
};

function formatKey(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function formatValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") {
    if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value)) {
      return formatDateTime(value);
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "-";
    return value.map(item => typeof item === "object" && item !== null ? JSON.stringify(item) : String(item)).join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([k]) => !SENSITIVE_KEYS.has(k.toLowerCase())
    );
    if (entries.length === 0) return "-";
    return (
      <div className="kv-list">
        {entries.map(([k, v]) => (
          <span className="kv-item" key={k}>
            <strong className="kv-key">{formatKey(k)}:</strong>{" "}
            <span className="kv-val">
              {v === null || v === undefined ? "-" : typeof v === "object" ? JSON.stringify(v) : String(v)}
            </span>
          </span>
        ))}
      </div>
    );
  }
  return String(value);
}

function Rows({ rows, select, emptyMessage }: { rows: Row[]; select?: (row: Row) => void; emptyMessage?: string }) {
  if (!rows.length) return <p className="empty-neutral">{emptyMessage || "No accessible records match this view."}</p>;
  const keys = Object.keys(rows[0]).filter(key => !["description", "details", "reasons"].includes(key)).slice(0, 7);
  return (
    <div className="table">
      <table>
        <thead>
          <tr>{keys.map(key => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={String(row.id || row.case_id || index)} onClick={() => select?.(row)}>
              {keys.map(key => (
                <td key={key}>{formatValue(row[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type CaseEvent = {
  id: string;
  case_id: number;
  action_type: string;
  actor_id?: number | null;
  bureau_id?: number | null;
  previous_values?: Record<string, unknown> | null;
  new_values?: Record<string, unknown> | null;
  remarks?: string | null;
  created_at: string;
};

function TimelineTable({ events }: { events: Row[] }) {
  if (!events || events.length === 0) {
    return <p className="empty-neutral">No workflow history recorded for this case.</p>;
  }
  return (
    <div className="table">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Action</th>
            <th>Remarks / Reason</th>
            <th>Previous Values</th>
            <th>New Values</th>
            <th>Bureau / Actor</th>
            <th>Event ID</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev, index) => {
            const event = ev as unknown as CaseEvent;
            return (
              <tr key={event.id || index}>
                <td>{formatDateTime(event.created_at)}</td>
                <td><span className="badge">{event.action_type || "-"}</span></td>
                <td style={{ maxWidth: 260, whiteSpace: "normal" }}>{event.remarks || "-"}</td>
                <td>{formatValue(event.previous_values)}</td>
                <td>{formatValue(event.new_values)}</td>
                <td>
                  <small>
                    {event.bureau_id ? `Bureau #${event.bureau_id}` : "-"}
                    {event.actor_id ? ` · User #${event.actor_id}` : ""}
                  </small>
                </td>
                <td>
                  <small title={event.id} style={{ fontFamily: "monospace", color: "#64748b" }}>
                    {event.id ? `${event.id.slice(0, 8)}...` : "-"}
                  </small>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CasesTable({ rows, open }: { rows: Case[]; open: (caseId: string) => void }) {
  if (!rows.length) return <p className="empty">No accessible cases match this search.</p>;
  return <div className="table"><table><thead><tr><th>Case ID</th><th>Institution ID</th><th>Receipt Date</th><th>Subject</th><th>Category</th><th>Stage / status</th><th>Priority</th><th /></tr></thead><tbody>{rows.map(item => <tr key={item.id}><td><button className="linkbutton" onClick={() => open(item.case_id)}>{item.case_id}</button></td><td>{item.institution_id}</td><td>{formatDateOnly(item.receipt_date)}</td><td className="subject">{item.subject}</td><td>{item.category}</td><td><span className="badge">{item.status}</span></td><td>{item.priority}</td><td><button onClick={() => open(item.case_id)}>Open</button></td></tr>)}</tbody></table></div>;
}

function Chart({ title, data }: { title: string; data: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(data));
  return <section className="panel chart"><h2>{title}</h2>{Object.entries(data).map(([label, value]) => <div className="bar" key={label}><span>{label}</span><i><b style={{ width: `${value / max * 100}%` }} /></i><strong>{value}</strong></div>)}</section>;
}

function Landing() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <div className="emblem-group">
          <span className="emblem-tag">AICTE</span>
          <div>
            <div className="brand-title">CaseConnect</div>
            <div className="brand-sub">All India Council for Technical Education</div>
          </div>
        </div>
        <span className="badge">National Prototype</span>
      </header>

      <main className="landing-main">
        <div className="landing-hero">
          <span className="eyebrow-pill">Case Management &amp; Scrutiny Portal</span>
          <h1>Application Tracking and Case Coordination Workspace</h1>
          <p className="subtitle">
            A unified administrative platform connecting AICTE scrutiny bureaus with approved technical institutions for end-to-end case tracking, grievance resolution, and inter-bureau coordination.
          </p>
          <div className="disclaimer-pill">
            Synthetic Demonstration Data • Not Official AICTE Records
          </div>
        </div>

        <div className="landing-grid">
          <article className="portal-card">
            <span className="portal-card-badge badge-admin">AICTE Officers &amp; Scrutiny</span>
            <h2>Admin Portal</h2>
            <p className="card-desc">
              Dedicated operational workspace for AICTE administrators, scrutiny officers, and regional bureau coordinators to manage cases, process transfers, detect institutional overlaps, and audit resolution workflows.
            </p>
            <ul className="portal-features">
              <li>Comprehensive Cases Dashboard &amp; Tracking</li>
              <li>Consolidated Institution Registry &amp; Profiles</li>
              <li>Explainable Overlap Detection &amp; Review</li>
              <li>Bilateral Bureau Coordination Requests</li>
              <li>Custom Analytics, Metrics, and Safe CSV Exports</li>
            </ul>
            <button
              className="portal-btn portal-btn-admin"
              onClick={() => { window.location.href = "/admin/login"; }}
            >
              Sign In to Admin Portal →
            </button>
            <p className="portal-subtext">Authorized administrators and bureau officers only</p>
          </article>

          <article className="portal-card">
            <span className="portal-card-badge badge-institution">Approved Institutions</span>
            <h2>Institution User Portal</h2>
            <p className="card-desc">
              Self-service portal for authorized representatives of AICTE-approved institutions to submit applications, review real-time processing stages, track official alerts, and view institutional records.
            </p>
            <ul className="portal-features">
              <li>Institution Application Docket &amp; History</li>
              <li>Direct Application Intake without ID Entry</li>
              <li>Stage Timeline, Deficiencies &amp; Action Notices</li>
              <li>Targeted Clarification &amp; Response Submissions</li>
              <li>Institution Profile &amp; Permanent ID Status</li>
            </ul>
            <button
              className="portal-btn portal-btn-inst"
              onClick={() => { window.location.href = "/institution/login"; }}
            >
              Sign In to Institution Portal →
            </button>
            <p className="portal-subtext">Registered institution representatives and grievance coordinators</p>
          </article>
        </div>
      </main>

      <footer className="landing-footer">
        <div>All India Council for Technical Education (AICTE) — CaseConnect Prototype</div>
        <small>Developed for SIH 2026. Demonstration environment utilizing synthetic records only.</small>
      </footer>
    </div>
  );
}

function Login({ login }: { login: (token: string) => void }) {
  const institutionPortal = window.location.pathname.startsWith("/institution");
  // Vite loads these values only in local development mode. Production builds
  // receive empty initial values and do not embed the local demo credentials.
  const demoAutofill = import.meta.env.DEV && import.meta.env.VITE_DEMO_AUTOFILL === "true";
  const [email, setEmail] = useState(demoAutofill ? institutionPortal ? import.meta.env.VITE_INSTITUTION_DEMO_EMAIL || "" : import.meta.env.VITE_DEMO_EMAIL || "" : ""), [password, setPassword] = useState(demoAutofill ? institutionPortal ? import.meta.env.VITE_INSTITUTION_DEMO_PASSWORD || "" : import.meta.env.VITE_DEMO_PASSWORD || "" : ""), [error, setError] = useState(""), [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) return setError("Enter your email address and password.");
    try {
      setLoading(true);
      setError("");
      const res = await api<{ access_token: string }>("/api/auth/token", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      login(res.access_token);
    } catch (x) {
      setError((x as Error).message || "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <main className="login">
      <section>
        <button
          type="button"
          className="linkbutton"
          onClick={() => { window.location.href = "/"; }}
          style={{ marginBottom: 16, fontSize: 13, textDecoration: "none", display: "inline-block" }}
        >
          ← Back to Portal Selection
        </button>
        <p className="eyebrow">AICTE CASECONNECT</p>
        <h1>{institutionPortal ? "Institution User Portal" : "Admin Portal"}</h1>
        <p>Synthetic demonstration data only — not official AICTE records.</p>
        <form onSubmit={submit} noValidate>
          <label>Email
            <input type="email" value={email} autoComplete="username" onChange={event => setEmail(event.target.value)} />
          </label>
          <label>Password
            <input type="password" value={password} autoComplete="current-password" onChange={event => setPassword(event.target.value)} />
          </label>
          {error && <p className="error">{error}</p>}
          <button disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        </form>
      </section>
    </main>
  );
}

function CaseForm({ bureaus, token, created, fail }: { bureaus: Bureau[]; token: string; created: (item: Case) => void; fail: (message: string) => void }) {
  const [saving, setSaving] = useState(false), [error, setError] = useState("");
  const clear = () => { setError(""); fail(""); };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget, data = new FormData(form), get = (key: string) => String(data.get(key) || "").trim();
    if (!Number(get("institution_id")) || !Number(get("originating_bureau_id"))) return setError("Institution ID and originating bureau are required.");
    if (get("subject").length < 4) return setError("Subject must contain at least 4 characters.");
    if (!get("description")) return setError("Complaint description is required.");
    let receiptDate: string;
    try { receiptDate = dateOnlyForApi(get("receipt_date"), "Receipt Date"); } catch (x) { return setError((x as Error).message); }
    try {
      setSaving(true); clear();
      const item = await api<Case>("/api/cases", { token, method: "POST", body: JSON.stringify({ institution_id: Number(get("institution_id")), originating_bureau_id: Number(get("originating_bureau_id")), receipt_date: receiptDate, source_channel: get("source_channel"), category: get("category"), priority: get("priority"), subject: get("subject"), description: get("description"), expected_disposal_date: get("expected_disposal_date") || undefined, external_reference: get("external_reference") || undefined, next_action: get("next_action") || undefined }) });
      created(item);
    } catch (x) { const message = (x as Error).message; setError(message); fail(message); }
    finally { setSaving(false); }
  };
  return <form className="panel formgrid" onSubmit={submit} onChange={clear} noValidate><div className="formtitle"><h2>Create synthetic case</h2><p>Required fields are shown first. The case is saved only after server confirmation.</p></div><label>Institution ID *<input name="institution_id" type="number" min="1" required inputMode="numeric" /><small>Use an accessible institution ID from the Institutions directory.</small></label><label>Receipt Date *<input name="receipt_date" type="date" defaultValue={today()} required /><small>Choose a date only. It is stored and displayed as DD-MM-YYYY.</small></label><label>Subject *<input name="subject" minLength={4} required /></label><label>Complaint Description *<textarea name="description" required /></label><label>Originating Bureau *<select name="originating_bureau_id" required><option value="">Select bureau</option>{bureaus.map(item => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label><label>Category *<input name="category" defaultValue="Grievance" required /></label><label>Source Channel *<input name="source_channel" defaultValue="Portal" required /></label><label>Priority *<select name="priority" defaultValue="Medium">{["Low", "Medium", "High", "Critical"].map(item => <option key={item}>{item}</option>)}</select></label><details className="wide"><summary>Additional details (optional)</summary><div className="formgrid details"><label>Expected Disposal Date<input name="expected_disposal_date" type="date" /><small>An optional planning date; it is separate from Receipt Date.</small></label><label>External Reference<input name="external_reference" /></label><label className="wide">Next Action<input name="next_action" /></label></div></details>{error && <p className="error wide">{error}</p>}<button disabled={saving}>{saving ? "Creating..." : "Create synthetic case"}</button></form>;
}

type CoordinationItem = Row & {
  id: string;
  overlap_id: number;
  requesting_case_id: number;
  receiving_case_id: number;
  requesting_bureau_id: number;
  receiving_bureau_id: number;
  requester_id: number;
  status: string;
  reason: string;
  response?: string | null;
  responded_by_id?: number | null;
  responded_at?: string | null;
  created_at: string;
  updated_at: string;
};

function CoordinationPanel({
  rows,
  overlaps,
  currentCase,
  token,
  refresh,
  notice,
  fail,
}: {
  rows: Row[];
  overlaps?: Row[];
  currentCase?: Case;
  token: string;
  refresh: () => Promise<void>;
  notice: (message: string) => void;
  fail: (message: string) => void;
}) {
  const [selected, setSelected] = useState<Row | null>(null);
  const [response, setResponse] = useState("");
  const [status, setStatus] = useState("Responded");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [showInitiate, setShowInitiate] = useState(false);
  const [initiateOverlapId, setInitiateOverlapId] = useState<number | "">("");
  const [initiateReason, setInitiateReason] = useState("");
  const [initiating, setInitiating] = useState(false);

  const submitResponse = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || response.trim().length < 2) return setError("Enter a response of at least 2 characters.");
    try {
      setSaving(true);
      setError("");
      const updated = await api<Row>(`/api/coordination/${selected.id}/respond`, {
        token,
        method: "POST",
        body: JSON.stringify({ status, response: response.trim() }),
      });
      setSelected(updated);
      setResponse("");
      await refresh();
      notice("Coordination response saved.");
    } catch (x) {
      const message = (x as Error).message;
      setError(message);
      fail(message);
    } finally {
      setSaving(false);
    }
  };

  const submitInitiate = async (event: FormEvent) => {
    event.preventDefault();
    if (!initiateOverlapId || !currentCase) return setError("Select an overlap to coordinate.");
    if (initiateReason.trim().length < 2) return setError("Enter a reason of at least 2 characters.");
    try {
      setInitiating(true);
      setError("");
      await api<Row>(`/api/coordination/from-overlap/${initiateOverlapId}`, {
        token,
        method: "POST",
        body: JSON.stringify({ requesting_case_id: currentCase.id, reason: initiateReason.trim() }),
      });
      setShowInitiate(false);
      setInitiateReason("");
      setInitiateOverlapId("");
      await refresh();
      notice("Coordination request submitted successfully.");
    } catch (x) {
      const message = (x as Error).message;
      setError(message);
      fail(message);
    } finally {
      setInitiating(false);
    }
  };

  return (
    <>
      {rows.length === 0 ? (
        <p className="empty-neutral">No coordination activity recorded yet for this case.</p>
      ) : (
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Reason</th>
                <th>Requesting Bureau</th>
                <th>Receiving Bureau</th>
                <th>Response</th>
                <th>Updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, index) => {
                const item = r as unknown as CoordinationItem;
                const isSelected = selected?.id === item.id;
                return (
                  <tr key={item.id || index} style={isSelected ? { background: "#edf4fe" } : undefined}>
                    <td><span className="badge">{item.status || "Pending"}</span></td>
                    <td style={{ maxWidth: 260, whiteSpace: "normal" }}>{item.reason}</td>
                    <td>Bureau #{item.requesting_bureau_id}</td>
                    <td>Bureau #{item.receiving_bureau_id}</td>
                    <td style={{ maxWidth: 240, whiteSpace: "normal" }}>{item.response || <em style={{ color: "#718096" }}>Awaiting response</em>}</td>
                    <td>{formatDateTime(item.updated_at || item.created_at)}</td>
                    <td>
                      <button
                        className="btn-sm"
                        onClick={() => { setSelected(isSelected ? null : item); setError(""); }}
                      >
                        {isSelected ? "Close" : item.status === "Resolved" ? "View" : "Respond"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {currentCase && (() => {
        const eligibleOverlaps = (overlaps || []).filter((ov: Row) => {
          const isCross = Boolean(ov.is_cross_bureau);
          const isAlreadyRequested = ov.status === "Coordination Requested";
          return isCross && !isAlreadyRequested;
        });

        if (!showInitiate) {
          if (eligibleOverlaps.length > 0) {
            return (
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn-sm btn-outline"
                  onClick={() => { setShowInitiate(true); setError(""); }}
                >
                  + Request Inter-Bureau Coordination ({eligibleOverlaps.length} eligible overlap{eligibleOverlaps.length > 1 ? "s" : ""})
                </button>
              </div>
            );
          }
          if (overlaps && overlaps.length > 0) {
            return (
              <div style={{ marginTop: 10 }}>
                <p className="empty-neutral" style={{ textAlign: "left", fontSize: 12 }}>
                   <strong>No overlaps eligible for inter-bureau coordination.</strong> The {overlaps.length} detected overlap{overlaps.length > 1 ? "s" : ""} for this case {overlaps.length > 1 ? "are" : "is"} currently assigned to the same bureau (Bureau #{currentCase.current_bureau_id}). Under AICTE rules, inter-bureau coordination is only applicable between cases currently assigned to different bureaus.
                </p>
              </div>
            );
          }
          return null;
        }

        return (
          <div style={{ marginTop: 10 }}>
            <section className="coordination-subpanel">
              <h4>Initiate Inter-Bureau Coordination Request</h4>
              <form className="formgrid" onSubmit={submitInitiate}>
                <label className="wide">
                  Related Overlap Candidate (Cross-Bureau Only) *
                  <select
                    value={initiateOverlapId}
                    onChange={e => setInitiateOverlapId(Number(e.target.value) || "")}
                    required
                  >
                    <option value="">Select candidate overlap</option>
                    {eligibleOverlaps.map((ov: Row) => {
                      const isLow = Number(ov.case_low_id) === currentCase.id;
                      const otherRef = isLow ? String(ov.case_high_reference || "") : String(ov.case_low_reference || "");
                      const otherBureau = isLow ? ov.case_high_bureau_id : ov.case_low_bureau_id;
                      const otherId = isLow ? ov.case_high_id : ov.case_low_id;
                      return (
                        <option key={String(ov.id)} value={Number(ov.id)}>
                          Overlap #{String(ov.id)} — Target Case: {otherRef || `Case #${String(otherId)}`} (Bureau #{String(otherBureau ?? "?")}, {String(ov.similarity_score)}% match)
                        </option>
                      );
                    })}
                  </select>
                </label>
                <label className="wide">
                  Coordination Reason *
                  <textarea
                    value={initiateReason}
                    onChange={e => setInitiateReason(e.target.value)}
                    placeholder="Describe why cross-bureau coordination is required..."
                    minLength={2}
                    required
                  />
                </label>
                {error && <p className="error wide">{error}</p>}
                <div className="coordination-actions wide">
                  <button disabled={initiating}>{initiating ? "Submitting..." : "Send Coordination Request"}</button>
                  <button type="button" className="btn-outline" onClick={() => setShowInitiate(false)}>Cancel</button>
                </div>
              </form>
            </section>
          </div>
        );
      })()}

      {selected && (
        <section className="panel coordination-subpanel">
          <h3>Coordination Request #{String(selected.id).slice(0, 8)}...</h3>
          <p>
            <strong>Status:</strong> <span className="badge">{String(selected.status)}</span>
            {selected.response ? ` — Response: ${String(selected.response)}` : ""}
          </p>
          <p><strong>Reason:</strong> {String(selected.reason)}</p>
          {String(selected.status) === "Resolved" ? (
            <p className="notice">This coordination request is resolved.</p>
          ) : (
            <form className="formgrid" onSubmit={submitResponse}>
              <label>
                Response status
                <select value={status} onChange={event => setStatus(event.target.value)}>
                  {["Responded", "More Information Requested", "Resolved"].map(item => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                Response
                <textarea
                  value={response}
                  onChange={event => setResponse(event.target.value)}
                  minLength={2}
                  placeholder="Provide resolution details or requested information..."
                  required
                />
              </label>
              {error && <p className="error wide">{error}</p>}
              <div className="coordination-actions wide">
                <button disabled={saving}>{saving ? "Submitting..." : "Submit response"}</button>
                <button type="button" className="btn-outline" onClick={() => setSelected(null)}>Close</button>
              </div>
            </form>
          )}
        </section>
      )}
    </>
  );
}

type AlertItem = Row & {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  case_id?: number | null;
  overlap_id?: number | null;
  bureau_id?: number | null;
  region?: string | null;
  is_read: boolean;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  created_at: string;
};

function AlertPanel({
  rows,
  token,
  refresh,
  notice,
  fail,
  emptyMessage,
}: {
  rows: Row[];
  token: string;
  refresh: () => Promise<void>;
  notice: (message: string) => void;
  fail: (message: string) => void;
  emptyMessage?: string;
}) {
  const [selected, setSelected] = useState<Row | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const mutate = async (alertId: string, operation: "acknowledge" | "resolve") => {
    try {
      setSavingId(alertId);
      setError("");
      const updated = await api<Row>(`/api/alerts/${alertId}/${operation}`, { token, method: "POST" });
      if (selected?.id === alertId) setSelected(updated);
      await refresh();
      notice(`Alert ${operation === "acknowledge" ? "acknowledged" : "resolved"}.`);
    } catch (x) {
      const message = (x as Error).message;
      setError(message);
      fail(message);
    } finally {
      setSavingId(null);
    }
  };

  if (!rows || rows.length === 0) {
    return <p className="empty-neutral">{emptyMessage || "No alerts recorded for this case."}</p>;
  }

  return (
    <>
      <div className="table">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Title</th>
              <th>Message</th>
              <th>Issued</th>
              <th>State</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, index) => {
              const alert = r as unknown as AlertItem;
              const sev = String(alert.severity || "Info").toLowerCase();
              const isResolved = Boolean(alert.resolved_at);
              const isAck = Boolean(alert.acknowledged_at);
              const isBusy = savingId === alert.id;
              const isSelected = selected?.id === alert.id;
              return (
                <tr key={alert.id || index} style={isSelected ? { background: "#edf4fe" } : undefined}>
                  <td>
                    <span className={`badge-severity badge-${sev}`}>
                      {alert.severity || "Info"}
                    </span>
                  </td>
                  <td><strong>{alert.title}</strong></td>
                  <td style={{ maxWidth: 320, whiteSpace: "normal" }}>{alert.message}</td>
                  <td>{formatDateTime(alert.created_at)}</td>
                  <td>
                    {isResolved ? (
                      <span className="badge badge-resolved">Resolved</span>
                    ) : isAck ? (
                      <span className="badge badge-ack">Acknowledged</span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        className="btn-sm"
                        disabled={isBusy || isAck || isResolved}
                        onClick={() => mutate(alert.id, "acknowledge")}
                      >
                        Acknowledge
                      </button>
                      <button
                        className="btn-sm"
                        disabled={isBusy || isResolved}
                        onClick={() => mutate(alert.id, "resolve")}
                      >
                        Resolve
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {error && <p className="error">{error}</p>}
    </>
  );
}

function CaseDetail({ context, token, bureaus, back, reload, openInstitution, notice, fail }: { context: CaseContext; token: string; bureaus: Bureau[]; back: () => void; reload: () => Promise<void>; openInstitution: (id: number) => void; notice: (message: string) => void; fail: (message: string) => void }) {
  const c = context.case, [actionError, setActionError] = useState("");
  const action = async (path: string, body: unknown, method = "POST") => { try { setActionError(""); await api(path, { token, method, body: JSON.stringify(body) }); await reload(); notice("Server confirmed the workflow change."); } catch (x) { const message = (x as Error).message; setActionError(message); fail(message); } };
  return (
    <section className="panel detail">
      <div className="detailhead">
        <div>
          <p className="eyebrow">CASE DETAIL</p>
          <h2>{c.case_id} <span className="badge">{c.status}</span></h2>
          <p>{c.subject}</p>
        </div>
        <button onClick={back}>Back to cases</button>
      </div>
      <div className="cards">
        <article><p>Institution ID</p><button onClick={() => openInstitution(c.institution_id)}>{c.institution_id}</button></article>
        <article><p>Receipt Date</p><strong>{formatDateOnly(c.receipt_date)}</strong></article>
        <article><p>Current Stage</p><strong>{c.status}</strong></article>
        <article><p>Priority</p><strong>{c.priority}</strong></article>
      </div>
      <p className="description">{c.description}</p>
      {actionError && <p className="error">{actionError}</p>}
      <div className="actions workflows">
        <form onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); action(`/api/cases/${c.case_id}`, { status: data.get("status"), remarks: data.get("remarks") }, "PATCH"); }}>
          <label>Status<select name="status">{statuses.filter(item => item !== c.status).map(item => <option key={item}>{item}</option>)}</select></label>
          <input name="remarks" minLength={2} required placeholder="Reason" />
          <button>Update status</button>
        </form>
        <form onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); action(`/api/cases/${c.case_id}/actions`, { action_type: "note", remarks: data.get("remarks") }); }}>
          <label>Add note<input name="remarks" minLength={2} required /></label>
          <button>Add</button>
        </form>
        <form onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); action(`/api/cases/${c.case_id}/actions`, { action_type: "transferred", target_bureau_id: Number(data.get("bureau")), remarks: data.get("remarks") }); }}>
          <label>Transfer to<select name="bureau" required><option value="">Select bureau</option>{bureaus.filter(item => item.id !== c.current_bureau_id).map(item => <option key={item.id} value={item.id}>{item.code}</option>)}</select></label>
          <input name="remarks" minLength={2} required placeholder="Reason" />
          <button>Transfer</button>
        </form>
      </div>
      <h3>SLA & Pendency Tracking</h3>
      <CaseSlaPanel caseId={c.case_id} token={token} notice={notice} fail={fail} reload={reload} />
      <h3>Timeline / workflow history</h3>
      <TimelineTable events={context.history} />
      <h3>AI Case Insights</h3>
      <AiCaseInsights caseId={c.case_id} token={token} />
      <h3>Coordination</h3>
      <CoordinationPanel rows={context.coordination} overlaps={context.overlaps} currentCase={c} token={token} refresh={reload} notice={notice} fail={fail} />
      <h3>Alerts</h3>
      <AlertPanel rows={context.alerts} token={token} refresh={reload} notice={notice} fail={fail} emptyMessage="No alerts recorded for this case." />
    </section>
  );
}

// ======= AI Intelligence Panel (Overview enhancement) =======
type AiSummaryData = {
  generated_at: string;
  summary_metrics: Record<string, number>;
  status_distribution: Record<string, number>;
  priority_distribution: Record<string, number>;
  overdue_cases: Array<{ case_id: string; institution: string; overdue_days: number; status: string; priority: string }>;
  high_activity_institutions: Array<{ institution_name: string; recent_30_days: number; prev_30_days: number; increase: number }>;
  recommended_actions: Array<{ action: string; urgency: string; affected_count: number }>;
};

function AiIntelligencePanel({ token }: { token: string }) {
  const [data, setData] = useState<AiSummaryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api<AiSummaryData>("/api/ai/intelligence-summary", { token })
      .then(setData)
      .catch(x => setError((x as Error).message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="loading">Loading AI intelligence summary...</p>;
  if (error) return <p style={{ color: "#e53e3e", fontSize: 13 }}>AI summary unavailable: {error}</p>;
  if (!data) return null;

  const m = data.summary_metrics;
  return (
    <section className="panel" style={{ borderLeft: "4px solid #6366f1", background: "#fafafe" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="eyebrow" style={{ color: "#6366f1" }}>AI INTELLIGENCE BRIEFING</p>
          <h3 style={{ margin: 0 }}>Rule-Based Intelligence Summary</h3>
          <small style={{ color: "#718096" }}>
            Generated from live data · Rule-based analysis · {new Date(data.generated_at).toLocaleString()}
          </small>
        </div>
        <button className="btn-sm btn-outline" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>

      <div className="cards" style={{ marginTop: 12 }}>
        {Object.entries(m).map(([k, v]) => (
          <article key={k} style={{ borderTop: "2px solid #6366f1" }}>
            <p>{k.replaceAll("_", " ")}</p>
            <strong style={{ color: v > 0 && k !== "total_active_cases" ? "#e53e3e" : undefined }}>{v}</strong>
          </article>
        ))}
      </div>

      {data.recommended_actions.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <strong style={{ fontSize: 13 }}>Recommended Actions:</strong>
          <ul style={{ marginTop: 6, paddingLeft: 20, fontSize: 13 }}>
            {data.recommended_actions.map((a, i) => (
              <li key={i} style={{ marginBottom: 4, color: a.urgency === "High" ? "#c53030" : "#2d3748" }}>
                <span style={{ fontWeight: 600 }}>[{a.urgency}]</span> {a.action} ({a.affected_count} affected)
              </li>
            ))}
          </ul>
        </div>
      )}

      {expanded && (
        <>
          {data.overdue_cases.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <strong style={{ fontSize: 13, color: "#c53030" }}>⚠ Overdue Cases (Top 10)</strong>
              <div className="table" style={{ marginTop: 6 }}>
                <table>
                  <thead><tr><th>Case ID</th><th>Institution</th><th>Category</th><th>Overdue Days</th><th>Priority</th></tr></thead>
                  <tbody>
                    {data.overdue_cases.map(c => (
                      <tr key={c.case_id}>
                        <td><strong>{c.case_id}</strong></td>
                        <td>{c.institution}</td>
                        <td>{c.priority}</td>
                        <td style={{ color: "#c53030", fontWeight: 600 }}>{c.overdue_days} days</td>
                        <td><span className="badge">{c.priority}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {data.high_activity_institutions.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <strong style={{ fontSize: 13 }}>Institutions with Increased Activity</strong>
              <div className="table" style={{ marginTop: 6 }}>
                <table>
                  <thead><tr><th>Institution</th><th>Last 30 Days</th><th>Prev 30 Days</th><th>Increase</th></tr></thead>
                  <tbody>
                    {data.high_activity_institutions.map((inst, i) => (
                      <tr key={i}>
                        <td>{inst.institution_name}</td>
                        <td>{inst.recent_30_days}</td>
                        <td>{inst.prev_30_days}</td>
                        <td style={{ color: "#e53e3e", fontWeight: 600 }}>+{inst.increase}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
      <p style={{ fontSize: 11, color: "#a0aec0", marginTop: 8 }}>
        Note: Rule-based analysis only. Not a trained predictive model. All recommendations require human review.
      </p>
    </section>
  );
}

// ======= AI Case Insights (in CaseDetail) =======
type AiCaseRec = {
  case_id: string;
  summary: string;
  bureau_recommendation: { recommended_bureau: string; confidence: number; evidence: string[]; model_type: string };
  priority_assessment: { priority_level: string; priority_score: number; factors: string[]; pending_days: number; model_type: string };
  next_action: { recommended_next_action: string; model_type: string };
  coordination_check: { needs_cross_bureau_coordination: boolean; cross_bureau_overlap_count: number };
};

function AiCaseInsights({ caseId, token }: { caseId: string; token: string }) {
  const [rec, setRec] = useState<AiCaseRec | null>(null);
  const [matches, setMatches] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!caseId || !token) return;
    setLoading(true);
    Promise.all([
      api<AiCaseRec>(`/api/ai/case-recommendation/${caseId}`, { token }),
      api<{ matches: Record<string, unknown>[] }>(`/api/ai/semantic-matches/${caseId}`, { token }),
    ])
      .then(([r, m]) => { setRec(r); setMatches(m.matches || []); })
      .catch(x => setError((x as Error).message))
      .finally(() => setLoading(false));
  }, [caseId, token]);

  const prioColor = (level: string) => ({ Critical: "#c53030", High: "#c05621", Medium: "#744210", Low: "#276749" }[level] || "#2d3748");

  if (loading) return <p className="loading" style={{ fontSize: 13 }}>Loading AI case insights...</p>;
  if (error) return <p style={{ color: "#e53e3e", fontSize: 12 }}>AI insights unavailable: {error}</p>;
  if (!rec) return null;

  return (
    <section className="panel" style={{ borderLeft: "4px solid #6366f1", background: "#fafafe", marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="eyebrow" style={{ color: "#6366f1" }}>AI CASE INSIGHTS</p>
          <p style={{ margin: 0, fontSize: 13 }}>{rec.summary}</p>
        </div>
        <button className="btn-sm btn-outline" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Collapse" : "Details"}
        </button>
      </div>
      <div className="cards" style={{ marginTop: 10 }}>
        <article style={{ borderTop: "2px solid #6366f1" }}>
          <p>Recommended Bureau</p>
          <strong style={{ fontSize: 14 }}>{rec.bureau_recommendation.recommended_bureau}</strong>
          <small style={{ color: "#718096" }}>{Math.round(rec.bureau_recommendation.confidence * 100)}% confidence</small>
        </article>
        <article style={{ borderTop: `2px solid ${prioColor(rec.priority_assessment.priority_level)}` }}>
          <p>AI Priority</p>
          <strong style={{ color: prioColor(rec.priority_assessment.priority_level) }}>
            {rec.priority_assessment.priority_level} ({rec.priority_assessment.priority_score}/100)
          </strong>
          <small style={{ color: "#718096" }}>{rec.priority_assessment.pending_days} days pending</small>
        </article>
        {rec.coordination_check.needs_cross_bureau_coordination && (
          <article style={{ borderTop: "2px solid #e53e3e" }}>
            <p>Cross-Bureau</p>
            <strong style={{ color: "#e53e3e" }}>Coordination Needed</strong>
            <small>{rec.coordination_check.cross_bureau_overlap_count} overlap(s)</small>
          </article>
        )}
      </div>
      {expanded && (
        <div style={{ marginTop: 12, fontSize: 13 }}>
          <div style={{ marginBottom: 10 }}>
            <strong>Next Action:</strong>
            <p style={{ margin: "4px 0", background: "#edf2f7", padding: "6px 10px", borderRadius: 4 }}>
              {rec.next_action.recommended_next_action}
            </p>
          </div>
          {rec.priority_assessment.factors.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <strong>Priority Factors:</strong>
              <ul style={{ paddingLeft: 18, marginTop: 4 }}>
                {rec.priority_assessment.factors.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
          {matches.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>Semantically Similar Cases (Sentence-Transformers Neural Embeddings):</strong>
                <span className="badge" style={{ fontSize: 11, background: "#e0e7ff", color: "#3730a3" }}>
                  Human Review Required · Never Auto-Merged
                </span>
              </div>
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 10 }}>
                {matches.map((m, i) => (
                  <div key={i} style={{ background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: 6, padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 6 }}>
                      <div>
                        <strong style={{ fontSize: 14 }}>{String(m.case_id)}</strong>
                        <span style={{ marginLeft: 8, color: "#475569", fontSize: 13 }}>({String(m.institution_name || "Same Institution")})</span>
                      </div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <span style={{
                          padding: "2px 8px", borderRadius: 9999, fontSize: 11, fontWeight: 600,
                          background: Number(m.similarity_percent) >= 70 ? "#fee2e2" : "#fef3c7",
                          color: Number(m.similarity_percent) >= 70 ? "#991b1b" : "#92400e",
                        }}>
                          {String(m.similarity_percent)}% Match · {String(m.interpretation)}
                        </span>
                        {Boolean(m.is_cross_bureau) && (
                          <span style={{ padding: "2px 8px", borderRadius: 9999, fontSize: 11, fontWeight: 600, background: "#f1f5f9", color: "#0f172a" }}>
                            Cross-Bureau
                          </span>
                        )}
                      </div>
                    </div>
                    <p style={{ margin: "6px 0 2px 0", fontSize: 13, fontWeight: 500 }}>{String(m.subject)}</p>
                    <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#64748b", margin: "4px 0" }}>
                      <span><strong>Category:</strong> {String(m.category)}</span>
                      <span><strong>Bureaus:</strong> {String(m.this_bureau_code)} ? {String(m.target_bureau_code)}</span>
                      <span><strong>Status:</strong> {String(m.status)}</span>
                    </div>
                    {Boolean(m.matching_explanation) && (
                      <p style={{ margin: "4px 0", fontSize: 12, color: "#334155", background: "#f8fafc", padding: "6px 8px", borderRadius: 4 }}>
                        <strong>AI Matching Explanation:</strong> {String(m.matching_explanation)}
                      </p>
                    )}
                    {Boolean(m.recommended_coordination_action) && (
                      <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "#1e40af" }}>
                        <strong>Recommended Coordination Action:</strong> {String(m.recommended_coordination_action)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          <p style={{ fontSize: 11, color: "#a0aec0" }}>
            Note: All AI insights are rule-based with sentence-transformer semantic similarity. Requires human review before action.
          </p>
        </div>
      )}
    </section>
  );
}

// ======= AI Screening Tab =======
type Submission = {
  id: number;
  submission_ref: string;
  institution_name: string | null;
  permanent_id: string | null;
  category: string | null;
  subject: string | null;
  screening_outcome: string | null;
  screening_status: string;
  admin_override: string | null;
  is_synthetic_demo: boolean;
  demo_scenario_id: string | null;
  expected_demo_outcome: string | null;
  created_at: string | null;
};

type SubmissionDetail = Submission & {
  description: string | null;
  incident_date: string | null;
  screening_result: {
    failures?: Array<{
      criterion_id: string;
      failure_category: string;
      extracted_evidence: string;
      expected: string;
      actual: string;
      explanation: string;
      suggested_correction: string;
    }>;
    human_review_triggers?: Array<Record<string, string>>;
    outcome_explanation?: string;
    disclaimer?: string;
    institution_resolved?: string | null;
    document_screening?: Record<string, unknown> | null;
  } | null;
  admin_override_reason: string | null;
};

function AiScreeningPage({ token, notice, fail }: { token: string; notice: (m: string) => void; fail: (m: string) => void }) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [selected, setSelected] = useState<SubmissionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterOutcome, setFilterOutcome] = useState("");
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoResult, setDemoResult] = useState<Record<string, unknown> | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [overriding, setOverriding] = useState(false);

  // Manual screening form state
  const [showForm, setShowForm] = useState(false);
  const [formSaving, setFormSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const loadList = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filterOutcome) params.set("outcome", filterOutcome);
      const result = await api<{ submissions: Submission[]; total: number }>(`/api/ai/submissions?${params}`, { token });
      setSubmissions(result.submissions || []);
    } catch (x) { fail((x as Error).message); }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadList(); }, [token, filterOutcome]);

  const openDetail = async (ref: string) => {
    try {
      const d = await api<SubmissionDetail>(`/api/ai/submissions/${ref}`, { token });
      setSelected(d);
      setOverrideReason("");
    } catch (x) { fail((x as Error).message); }
  };

  const runDemo = async () => {
    setDemoRunning(true);
    try {
      const result = await api<Record<string, unknown>>("/api/ai/run-synthetic-demonstrations", { token, method: "POST" });
      setDemoResult(result);
      await loadList();
      notice(`${(result.total_processed as number) || 18} synthetic demonstrations processed and stored across form and document pipelines.`);
    } catch (x) { fail((x as Error).message); }
    finally { setDemoRunning(false); }
  };

  const doOverride = async (ref: string, action: "APPROVE" | "REJECT") => {
    setOverriding(true);
    try {
      await api(`/api/ai/submissions/${ref}/override`, { token, method: "PATCH", body: JSON.stringify({ override: action, reason: overrideReason }) });
      notice(`Submission ${action === "APPROVE" ? "approved" : "rejected"} by admin.`);
      await loadList();
      if (selected?.submission_ref === ref) await openDetail(ref);
    } catch (x) { fail((x as Error).message); }
    finally { setOverriding(false); }
  };

  const submitManual = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setFormSaving(true); setFormError("");
    try {
      const fileInput = form.querySelector('input[type="file"]') as HTMLInputElement;
      let result: Record<string, unknown>;
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        const res = await fetch("http://127.0.0.1:8000/api/ai/screen-with-documents", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || body.error?.message || "Screening failed");
        }
        result = await res.json();
      } else {
        const get = (k: string) => String(fd.get(k) || "").trim();
        result = await api<Record<string, unknown>>("/api/ai/screen-submission", {
          token, method: "POST",
          body: JSON.stringify({
            permanent_id: get("permanent_id"), subject: get("subject"),
            description: get("description"), category: get("category"),
            incident_date: get("incident_date") || undefined, contact_info: get("contact_info") || undefined,
          }),
        });
      }
      notice(`Screening complete. Outcome: ${result.screening_outcome}`);
      setShowForm(false);
      await loadList();
    } catch (x) { setFormError((x as Error).message); }
    finally { setFormSaving(false); }
  };

  const outcomeColor = (o: string | null) => ({
    PASSED: "#276749", REJECTED_AT_INTAKE: "#c53030", CORRECTION_REQUIRED: "#c05621", NEEDS_HUMAN_REVIEW: "#744210"
  }[o || ""] || "#718096");

  const outcomeOptions = ["PASSED", "REJECTED_AT_INTAKE", "CORRECTION_REQUIRED", "NEEDS_HUMAN_REVIEW"];

  return (
    <div>
      {/* Header controls */}
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <select value={filterOutcome} onChange={e => setFilterOutcome(e.target.value)} aria-label="Filter by outcome">
          <option value="">All Outcomes</option>
          {outcomeOptions.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        <button onClick={() => void loadList()}>Refresh</button>
        <button className="btn-outline" onClick={() => { setShowForm(!showForm); setFormError(""); }}>
          {showForm ? "Cancel" : "+ Screen New Submission"}
        </button>
        <button
          style={{ background: demoRunning ? "#718096" : "#6366f1", color: "#fff", border: "none" }}
          disabled={demoRunning}
          onClick={() => void runDemo()}
        >
          {demoRunning ? "Running..." : "▶ Run 10 Synthetic Demonstrations"}
        </button>
      </div>

      {/* Manual screening form */}
      {showForm && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <h3>Screen a Complaint Submission</h3>
          <p style={{ fontSize: 13, color: "#718096" }}>
            The complaint will be run through AI screening criteria before case registration.
          </p>
          <form className="formgrid" onSubmit={submitManual} noValidate>
            <label>Institution Permanent ID *<input name="permanent_id" placeholder="e.g. DEMO-AICTE-0001" required /></label>
            <label>Category *
              <select name="category" required>
                <option value="">Select category</option>
                {["Academic","Financial","Infrastructure","Faculty","Accreditation","Affiliation","Admission","Conduct","Examination","Other"].map(c => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label>Subject *<input name="subject" minLength={10} required /></label>
            <label className="wide">Complaint Description *<textarea name="description" required /></label>
            <label className="wide">Upload Evidence Document (PDF, Image, Text)<input name="files" type="file" multiple /><small>Supports real PDF, PNG, JPG, or TXT complaint evidence documents.</small></label>
            <label>Incident Date<input name="incident_date" type="date" /></label>
            <label>Contact Info<input name="contact_info" type="email" /></label>
            {formError && <p className="error wide">{formError}</p>}
            <button disabled={formSaving}>{formSaving ? "Screening..." : "Submit for Screening"}</button>
          </form>
        </section>
      )}

      {/* Demo results summary */}
      {demoResult && (
        <section className="panel" style={{ marginBottom: 16, borderLeft: "4px solid #6366f1" }}>
          <p className="eyebrow" style={{ color: "#6366f1" }}>SYNTHETIC DEMONSTRATION RESULTS</p>
          <div className="cards">
            {Object.entries(demoResult.summary as Record<string, unknown> || {}).map(([k, v]) => (
              <article key={k}><p>{k.replaceAll("_", " ")}</p><strong>{String(v)}</strong></article>
            ))}
          </div>
          <p style={{ fontSize: 11, color: "#a0aec0" }}>All records are synthetic demonstration material — not real complaints.</p>
        </section>
      )}

      {/* Submissions list */}
      <section className="panel">
        <h3 style={{ marginTop: 0 }}>Complaint Submissions ({submissions.length})</h3>
        {loading && <p className="loading">Loading...</p>}
        {!loading && submissions.length === 0 && (
          <p className="empty-neutral">No submissions found. Run the synthetic demonstrations to populate data.</p>
        )}
        {submissions.length > 0 && (
          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Ref</th><th>Institution</th><th>Category</th><th>Subject</th>
                  <th>Outcome</th><th>Override</th><th>Demo</th><th>Submitted</th><th />
                </tr>
              </thead>
              <tbody>
                {submissions.map(s => (
                  <tr key={s.id} style={selected?.id === s.id ? { background: "#edf4fe" } : undefined}>
                    <td><code style={{ fontSize: 11 }}>{s.submission_ref}</code></td>
                    <td style={{ maxWidth: 160, whiteSpace: "normal" }}>{s.institution_name || s.permanent_id || "—"}</td>
                    <td>{s.category || "—"}</td>
                    <td style={{ maxWidth: 200, whiteSpace: "normal" }}>{s.subject || "—"}</td>
                    <td>
                      <span style={{
                        padding: "2px 8px", borderRadius: 9999, fontSize: 11, fontWeight: 600,
                        background: outcomeColor(s.screening_outcome) + "22",
                        color: outcomeColor(s.screening_outcome),
                      }}>
                        {s.screening_outcome || "PENDING"}
                      </span>
                    </td>
                    <td>{s.admin_override ? <span className="badge">{s.admin_override}</span> : "—"}</td>
                    <td>{s.is_synthetic_demo ? <span style={{ fontSize: 11, color: "#6366f1" }}>SYNTH</span> : "—"}</td>
                    <td><small>{s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}</small></td>
                    <td><button className="btn-sm" onClick={() => void openDetail(s.submission_ref)}>View</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Detail panel */}
      {selected && (
        <section className="panel" style={{ marginTop: 16, borderLeft: `4px solid ${outcomeColor(selected.screening_outcome)}` }}>
          <div className="detailhead">
            <div>
              <p className="eyebrow">SCREENING DETAIL</p>
              <h3 style={{ margin: 0 }}>{selected.submission_ref}
                <span style={{
                  marginLeft: 10, fontSize: 13, padding: "2px 10px", borderRadius: 9999,
                  background: outcomeColor(selected.screening_outcome) + "22",
                  color: outcomeColor(selected.screening_outcome),
                }}>
                  {selected.screening_outcome || "PENDING"}
                </span>
              </h3>
            </div>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>

          {selected.is_synthetic_demo && (
            <div style={{ background: "#fefce8", border: "1px solid #f59e0b", borderRadius: 6, padding: "6px 12px", marginBottom: 12, fontSize: 12 }}>
               <strong>Synthetic Demo</strong> — Scenario: {selected.demo_scenario_id} · Expected: {selected.expected_demo_outcome}
            </div>
          )}

          <div className="cards">
            <article><p>Institution</p><strong>{selected.institution_name || selected.permanent_id || "—"}</strong></article>
            <article><p>Category</p><strong>{selected.category || "—"}</strong></article>
            <article><p>Incident Date</p><strong>{selected.incident_date || "—"}</strong></article>
            {selected.screening_result?.institution_resolved && (
              <article><p>Resolved Institution</p><strong>{selected.screening_result.institution_resolved}</strong></article>
            )}
          </div>

          <div style={{ margin: "12px 0" }}>
            <strong>Subject:</strong> <span>{selected.subject || "—"}</span>
          </div>
          {selected.description && (
            <div style={{ marginBottom: 12 }}>
              <strong>Description:</strong>
              <p style={{ background: "#f7fafc", padding: "8px 12px", borderRadius: 4, fontSize: 13, marginTop: 4 }}>
                {selected.description}
              </p>
            </div>
          )}

          {selected.screening_result?.outcome_explanation && (
            <div style={{ background: outcomeColor(selected.screening_outcome) + "11", padding: "8px 12px", borderRadius: 6, marginBottom: 12 }}>
              <strong>Outcome Explanation:</strong> {selected.screening_result.outcome_explanation}
            </div>
          )}

          {/* Document Screening Analysis */}
          {selected.screening_result?.document_screening && (
            <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 13 }}>Uploaded Evidence Analysis ({((selected.screening_result.document_screening as any).document_analyses || []).length} Document(s)):</strong>
              {Array.isArray((selected.screening_result.document_screening as any).document_analyses) &&
              (selected.screening_result.document_screening as any).document_analyses.length > 0 ? (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                  {((selected.screening_result.document_screening as any).document_analyses as any[]).map((da, i) => (
                    <div key={i} style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 6, padding: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <strong>📄 {String(da.filename)}</strong>
                        <span className="badge">{String(da.category || da.status)}</span>
                      </div>
                      {da.confidence && (
                        <p style={{ margin: "2px 0", fontSize: 12, color: "#64748b" }}>
                          Confidence: {Math.round(Number(da.confidence) * 100)}% · SHA256: <code>{String(da.sha256)}</code>
                        </p>
                      )}
                      {da.text_snippet && (
                        <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "#334155", background: "#ffffff", padding: "6px 8px", borderRadius: 4 }}>
                          Snippet: {String(da.text_snippet)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: 13, color: "#64748b", margin: "4px 0" }}>No attached documents for this submission.</p>
              )}
            </div>
          )}

          {/* Failures */}
          {(selected.screening_result?.failures || []).length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <strong style={{ color: "#c53030" }}>[FAIL] Failed Criteria ({selected.screening_result!.failures!.length})</strong>
              {selected.screening_result!.failures!.map((f, i) => (
                <div key={i} style={{ background: "#fff5f5", border: "1px solid #feb2b2", borderRadius: 6, padding: "10px 14px", marginTop: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <strong style={{ fontSize: 13 }}>{f.criterion_id.replaceAll("_", " ")}</strong>
                    <code style={{ fontSize: 11, color: "#c53030", background: "#fed7d7", padding: "1px 6px", borderRadius: 4 }}>{f.failure_category}</code>
                  </div>
                  <p style={{ margin: "4px 0", fontSize: 13 }}><strong>Evidence:</strong> {f.extracted_evidence}</p>
                  <p style={{ margin: "4px 0", fontSize: 13 }}><strong>Explanation:</strong> {f.explanation}</p>
                  {f.suggested_correction && (
                    <p style={{ margin: "4px 0", fontSize: 13, color: "#276749" }}>
                      <strong>Correction:</strong> {f.suggested_correction}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Human review triggers */}
          {(selected.screening_result?.human_review_triggers || []).length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <strong style={{ color: "#744210" }}>⚠ Human Review Required</strong>
              {selected.screening_result!.human_review_triggers!.map((t, i) => (
                <div key={i} style={{ background: "#fffbeb", border: "1px solid #f59e0b", borderRadius: 6, padding: "10px 14px", marginTop: 8 }}>
                  <p style={{ margin: "2px 0", fontSize: 13 }}><strong>Trigger:</strong> {t.criterion_id as string}</p>
                  <p style={{ margin: "2px 0", fontSize: 13 }}>{t.explanation as string}</p>
                </div>
              ))}
            </div>
          )}

          {/* Admin override */}
          {selected.admin_override ? (
            <div style={{ background: "#f0fff4", border: "1px solid #9ae6b4", borderRadius: 6, padding: "8px 12px" }}>
              <strong>Admin Override: {selected.admin_override}</strong>
              {selected.admin_override_reason && <p style={{ fontSize: 13, margin: "4px 0" }}>Reason: {selected.admin_override_reason}</p>}
            </div>
          ) : (
            <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12, marginTop: 12 }}>
              <strong style={{ fontSize: 13 }}>Admin Override:</strong>
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
                <label style={{ flex: 1, minWidth: 200 }}>
                  Reason
                  <input value={overrideReason} onChange={e => setOverrideReason(e.target.value)} placeholder="Reason for override..." />
                </label>
                <button
                  disabled={overriding}
                  style={{ background: "#276749", color: "#fff", border: "none" }}
                  onClick={() => void doOverride(selected.submission_ref, "APPROVE")}
                >
                  Approve
                </button>
                <button
                  disabled={overriding}
                  style={{ background: "#c53030", color: "#fff", border: "none" }}
                  onClick={() => void doOverride(selected.submission_ref, "REJECT")}
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          {selected.screening_result?.disclaimer && (
            <p style={{ fontSize: 11, color: "#a0aec0", marginTop: 12 }}>Note: {selected.screening_result.disclaimer}</p>
          )}
        </section>
      )}
    </div>
  );
}

export function App() {
  const [token, setToken] = useState(sessionStorage.getItem("caseconnect_token") || ""), [tab, setTab] = useState<Tab>("Overview"), [rows, setRows] = useState<Row[]>([]), [summary, setSummary] = useState<Record<string, unknown>>({}), [bureaus, setBureaus] = useState<Bureau[]>([]), [user, setUser] = useState<User | null>(null), [query, setQuery] = useState(""), [filters, setFilters] = useState({ region: "", category: "", status: "" }), [reportFilters, setReportFilters] = useState({ region: "", category: "", status: "" }), [reportOptions, setReportOptions] = useState<{ regions: string[]; categories: string[] }>({ regions: [], categories: [] }), [context, setContext] = useState<CaseContext | null>(null), [profile, setProfile] = useState<Profile | null>(null), [overlap, setOverlap] = useState<Row | null>(null), [error, setError] = useState(""), [notice, setNotice] = useState(""), [loading, setLoading] = useState(false);
  const reportRequest = useRef(0), overviewRequest = useRef(0);
  const fail = (message: string) => { if (message) { setNotice(""); setError(message); } }; const done = (message: string) => { setError(""); setNotice(message); };
  const navigateCase = async (caseId: string, replace = false) => { try { setLoading(true); setError(""); const loaded = await api<CaseContext>(`/api/cases/${encodeURIComponent(caseId)}/context`, { token }); setContext(loaded); setProfile(null); setTab("Cases"); window.history[replace ? "replaceState" : "pushState"]({}, "", `/cases/${encodeURIComponent(caseId)}`); } catch (x) { fail((x as Error).message); setContext(null); } finally { setLoading(false); } };
  const loadOverview = async (activeFilters = filters) => {
    if (!token) return;
    const request = ++overviewRequest.current;
    try {
      setLoading(true);
      const params = new URLSearchParams(Object.entries(activeFilters).filter(([, value]) => value));
      const result = await api<Record<string, unknown>>(`/api/analytics/summary?${params}`, { token });
      if (request === overviewRequest.current) {
        setSummary(result);
        setRows([]);
      }
    } catch (x) {
      if (request === overviewRequest.current) fail((x as Error).message);
    } finally {
      if (request === overviewRequest.current) setLoading(false);
    }
  };
  const load = async () => {
    if (!token) return;
    if (tab === "Overview") {
      await loadOverview(filters);
      return;
    }
    const request = tab === "Reports" ? ++reportRequest.current : 0;
    try {
      setLoading(true);
      if (tab === "Reports") {
        const params = new URLSearchParams(Object.entries(reportFilters).filter(([, value]) => value));
        const result = await api<Record<string, unknown>>(`/api/analytics/summary?${params}`, { token });
        if (request === reportRequest.current) {
          sessionStorage.setItem("caseconnect_report_filters", params.toString());
          setSummary(result);
          setRows([]);
        }
        return;
      }
      if (tab === "Cases") {
        const params = new URLSearchParams({ page_size: "100" });
        if (query) params.set("case_id", query.trim());
        const result = await api<{ items: Case[] }>(`/api/cases?${params}`, { token });
        setRows(result.items);
        return;
      }
      const params = new URLSearchParams();
      if (query) params.set(tab === "Institutions" ? "search" : "case_id", query);
      if (tab === "Institutions" && filters.region) params.set("region", filters.region);
      const result = await api<unknown>((paths[tab] || "") + (params.size ? `?${params}` : ""), { token });
      setRows(Array.isArray(result) ? result as Row[] : (result as { items?: Row[] }).items || []);
    } catch (x) {
      if (request === 0 || request === reportRequest.current) fail((x as Error).message);
    } finally {
      if (request === 0 || request === reportRequest.current) setLoading(false);
    }
  };
  useEffect(() => { if (!token) return; Promise.all([api<User>("/api/auth/me", { token }), api<Bureau[]>("/api/reference/bureaus", { token })]).then(([me, directory]) => { setUser(me); setBureaus(directory); const match = /^\/cases\/([^/]+)$/.exec(window.location.pathname); if (match) void navigateCase(decodeURIComponent(match[1]), true); }).catch(x => { sessionStorage.removeItem("caseconnect_token"); setToken(""); fail((x as Error).message); }); }, [token]);
  useEffect(() => { if (token && !context) void load(); }, [tab, token]);
  useEffect(() => { if (token) api<{ regions: string[]; categories: string[] }>("/api/analytics/filter-options", { token }).then(setReportOptions).catch(x => fail((x as Error).message)); }, [token]);
  useEffect(() => { const handler = () => { const match = /^\/cases\/([^/]+)$/.exec(window.location.pathname); if (match && token) void navigateCase(decodeURIComponent(match[1]), true); else setContext(null); }; window.addEventListener("popstate", handler); return () => window.removeEventListener("popstate", handler); }, [token]);
  const refreshContext = async () => { if (context) await navigateCase(context.case.case_id, true); await load(); };
  const openInstitution = async (id: number) => { try { setProfile(await api<Profile>(`/api/institutions/${id}/profile`, { token })); setContext(null); setTab("Institutions"); window.history.pushState({}, "", "/"); } catch (x) { fail((x as Error).message); } };
  const selectTab = (next: Tab) => { setTab(next); setContext(null); setProfile(null); setOverlap(null); window.history.pushState({}, "", "/"); };
  const post = async (path: string, body?: unknown) => { try { await api(path, { token, method: "POST", body: body ? JSON.stringify(body) : undefined }); done("Server confirmed the action."); await load(); } catch (x) { fail((x as Error).message); } };
  if (!token) return window.location.pathname === "/" ? <Landing /> : <Login login={value => { sessionStorage.setItem("caseconnect_token", value); setToken(value); }} />;
  if (user?.role === "Institution Representative") return <InstitutionPortal token={token} signOut={() => { sessionStorage.removeItem("caseconnect_token"); setToken(""); window.history.pushState({}, "", "/"); }} />;
  const overviewFiltersUi = (
    <div className="toolbar">
      <label>
        State / Region
        <select
          aria-label="State / Region"
          value={filters.region}
          onChange={event => setFilters({ ...filters, region: event.target.value })}
        >
          <option value="">All Regions</option>
          {reportOptions.regions.map(item => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </label>
      <label>
        Category
        <select
          aria-label="Category"
          value={filters.category}
          onChange={event => setFilters({ ...filters, category: event.target.value })}
        >
          <option value="">All Categories</option>
          {reportOptions.categories.map(item => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      </label>
      <label>
        Case Status
        <select
          aria-label="Case Status"
          value={filters.status}
          onChange={event => setFilters({ ...filters, status: event.target.value })}
        >
          <option value="">All Statuses</option>
          <option value="Pending">Pending</option>
          {statuses.map(item => (
            <option key={item} value={item}>{item}</option>
          ))}
          <option value="Overdue">Overdue</option>
        </select>
      </label>
      <button onClick={() => void loadOverview(filters)}>Apply Filters</button>
      {(filters.region || filters.category || filters.status) && (
        <button
          type="button"
          className="btn-outline"
          onClick={() => {
            const reset = { region: "", category: "", status: "" };
            setFilters(reset);
            void loadOverview(reset);
          }}
        >
          Clear Filters
        </button>
      )}
    </div>
  );
  const reportsFiltersUi = <div className="toolbar"><label>State / Region<select aria-label="State / Region" value={reportFilters.region} onChange={event => setReportFilters({ ...reportFilters, region: event.target.value })}><option value="">All Regions</option>{reportOptions.regions.map(item => <option key={item} value={item}>{item}</option>)}</select></label><label>Category<select aria-label="Category" value={reportFilters.category} onChange={event => setReportFilters({ ...reportFilters, category: event.target.value })}><option value="">All Categories</option>{reportOptions.categories.map(item => <option key={item} value={item}>{item}</option>)}</select></label><label>Case Status<select aria-label="Case Status" value={reportFilters.status} onChange={event => setReportFilters({ ...reportFilters, status: event.target.value })}><option value="">All Statuses</option><option value="Pending">Pending</option>{statuses.map(item => <option key={item}>{item}</option>)}<option value="Overdue">Overdue</option></select></label><button onClick={() => void load()}>Apply Filters</button></div>;
  const filtersUi = tab === "Reports" ? reportsFiltersUi : overviewFiltersUi;
  return (
    <div className="shell">
      <aside>
        <div className="brand">AICTE<br /><strong>CaseConnect</strong></div>
        {tabs.map(item => <button className={tab === item ? "active" : ""} onClick={() => selectTab(item)} key={item}>{item}</button>)}
        <button onClick={() => { sessionStorage.removeItem("caseconnect_token"); setToken(""); window.history.pushState({}, "", "/"); }}>Sign out</button>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">CASE MANAGEMENT / {tab.toUpperCase()}</p>
            <h1>{tab}</h1>
            <small>{user ? `${user.full_name} · ${user.role}` : "Loading account..."}</small>
          </div>
          <span className="badge">Prototype</span>
        </header>
        {loading && <p className="loading">Loading...</p>}
        {error && <p className="error">{error}</p>}
        {notice && <p className="notice">{notice}</p>}
        {(tab === "Overview" || tab === "Reports") && (
          <>
            {filtersUi}
            <div className="cards">
              {Object.entries(summary).filter(([, value]) => typeof value === "number").map(([key, value]) => (
                <article key={key}><p>{key.replaceAll("_", " ")}</p><strong>{String(value)}</strong></article>
              ))}
            </div>
            <div className="charts">
              <Chart title="Status workload" data={(summary.by_status || {}) as Record<string, number>} />
              <Chart title="Ageing" data={(summary.ageing || {}) as Record<string, number>} />
              <Chart title="Monthly received" data={(summary.monthly_trend || {}) as Record<string, number>} />
            </div>
            {tab === "Overview" && <AiIntelligencePanel token={token} />}
            {tab === "Reports" && (
              <div className="actions">
                {["cases.csv", "bureau-summary.csv", "region-summary.csv", "ageing.csv", "overlaps.csv"].map(file => (
                  <button key={file} onClick={() => download(`/api/analytics/${file}`, token)}>{file.replace(".csv", " export")}</button>
                ))}
              </div>
            )}
          </>
        )}
        {tab === "Cases" && (
          context ? (
            <CaseDetail
              context={context}
              token={token}
              bureaus={bureaus}
              back={() => { setContext(null); window.history.pushState({}, "", "/"); void load(); }}
              reload={refreshContext}
              openInstitution={openInstitution}
              notice={done}
              fail={fail}
            />
          ) : (
            <>
              <CaseForm bureaus={bureaus} token={token} fail={fail} created={item => { done(`Case ${item.case_id} was created.`); void navigateCase(item.case_id); }} />
              <section className="panel">
                <div className="detailhead">
                  <div>
                    <h2>Cases dashboard</h2>
                    <p>Open a case by its reference or search for an exact Case ID.</p>
                  </div>
                </div>
                <div className="toolbar">
                  <input aria-label="Case ID" placeholder="Enter Case ID" value={query} onChange={event => setQuery(event.target.value)} />
                  <button onClick={() => void load()}>Search cases</button>
                  <button onClick={() => { setQuery(""); void load(); }}>Clear</button>
                </div>
                <CasesTable rows={rows as Case[]} open={caseId => void navigateCase(caseId)} />
              </section>
            </>
          )
        )}
        {tab === "Institutions" && (
          profile ? (
            <section className="panel">
              <div className="detailhead">
                <div>
                  <h2>{profile.name}</h2>
                  <p>Permanent ID: {profile.permanent_id || "Not provided"} · {profile.permanent_id_verified ? "Demonstration data flag: verified" : "Not officially verified"}</p>
                </div>
                <button onClick={() => setProfile(null)}>Back to directory</button>
              </div>
              <div className="cards">
                <article><p>Associated cases</p><strong>{profile.total_cases}</strong></article>
                {Object.entries(profile.cases_by_status).map(([key, value]) => (
                  <article key={key}><p>{key}</p><strong>{value}</strong></article>
                ))}
              </div>

              <h3>Consolidated complaint history</h3>
              {profile.cases && profile.cases.length > 0 ? (
                <CasesTable rows={profile.cases} open={caseId => void navigateCase(caseId)} />
              ) : (
                <p className="empty-neutral">No associated cases recorded for this institution.</p>
              )}

              <h3>Associated Institution Accounts</h3>
              {profile.accounts && profile.accounts.length > 0 ? (
                <div className="table">
                  <table>
                    <thead>
                      <tr>
                        <th>Full Name</th>
                        <th>Email Address</th>
                        <th>Role</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profile.accounts.map(acc => (
                        <tr key={acc.id}>
                          <td><strong>{acc.full_name}</strong></td>
                          <td>{acc.email}</td>
                          <td><span className="badge">{acc.role}</span></td>
                          <td><span className="badge badge-resolved">{acc.is_active ? "Active" : "Inactive"}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-neutral">No institution accounts are associated with this institution.</p>
              )}

              <h3>Related overlap records</h3>
              {profile.related_overlaps && profile.related_overlaps.length > 0 ? (
                <Rows rows={profile.related_overlaps} />
              ) : (
                <p className="empty-neutral">No related overlap records for this institution.</p>
              )}

              <h3>Related coordination requests</h3>
              {profile.related_coordination && profile.related_coordination.length > 0 ? (
                <Rows rows={profile.related_coordination} />
              ) : (
                <p className="empty-neutral">No related coordination requests for this institution.</p>
              )}
            </section>
          ) : (
            <section className="panel">
              <div className="detailhead">
                <div>
                  <h2>Institutions Directory</h2>
                  <p>Search institutions by name or Permanent ID (e.g. DEMO-AICTE-0003), or filter by region.</p>
                </div>
              </div>
              <div className="toolbar">
                <input
                  placeholder="Search name or Permanent ID"
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                />
                <select
                  aria-label="Filter Region"
                  value={filters.region}
                  onChange={event => setFilters({ ...filters, region: event.target.value })}
                >
                  <option value="">All Regions</option>
                  {reportOptions.regions.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <button onClick={() => void load()}>Search</button>
                {(query || filters.region) && (
                  <button
                    type="button"
                    className="btn-outline"
                    onClick={() => {
                      setQuery("");
                      setFilters({ ...filters, region: "" });
                      void load();
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
              <Rows
                rows={rows}
                select={item => void openInstitution(Number(item.id))}
                emptyMessage="No institutions match this search."
              />
            </section>
          )
        )}
        {tab === "Overlaps" && (
          <>
            <h2>Potential overlapping cases — human review required</h2>
            <button onClick={() => void post("/api/overlaps/refresh")}>Refresh suggestions</button>
            <Rows rows={rows} select={setOverlap} />
            {overlap && (
              <section className="panel">
                <p><strong>Score:</strong> {String(overlap.similarity_score)} · {String(overlap.reasons)}</p>
                <div className="actions">
                  <button onClick={() => void post(`/api/overlaps/${overlap.id}/review`, { status: "Confirmed Related", remarks: "Confirmed after human review" })}>Confirm related</button>
                  <button onClick={() => void post(`/api/overlaps/${overlap.id}/review`, { status: "Dismissed", remarks: "Dismissed after human review" })}>Dismiss</button>
                </div>
              </section>
            )}
          </>
        )}
        {tab === "Alerts" && (
          <>
            <button onClick={() => void post("/api/monitoring/run")}>Run prototype monitor</button>
            <AlertPanel rows={rows} token={token} refresh={load} notice={done} fail={fail} emptyMessage="No accessible alerts recorded." />
          </>
        )}
        {tab === "Audit" && <Rows rows={rows} />}
        {tab === "AI Screening" && <AiScreeningPage token={token} notice={done} fail={fail} />}
        {tab === "SLA Management" && <SlaManagementPage token={token} notice={done} fail={fail} selectCase={caseId => { void navigateCase(caseId); }} bureaus={bureaus} />}
      </main>
    </div>
  );
}
