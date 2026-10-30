import { FormEvent, useEffect, useState } from "react";

import { api } from "./api";
import { dateOnlyForApi, formatDateOnly } from "./dateTime";

type Row = Record<string, unknown>;
type HistoryEvent = { id: string; action_type: string; remarks: string | null; created_at: string };
type AlertRow = { id: string; title: string; message: string; case_id?: string | number | null; case_reference?: string | null; created_at: string; resolved_at: string | null };
type Application = Row & { case_id: string; subject: string; category: string; receipt_date: string; status: string; updated_at: string; description: string; priority: string };
type ApplicationDetail = { case: Application; institution: Row; history: HistoryEvent[]; alerts: AlertRow[] };
type DocumentRow = { case_id: string; category: string; external_reference: string; submission_date: string; status: string; document_type: string; access_tier: string };
type PortalTab = "Overview" | "My Applications" | "Submit Application" | "Alerts & Action Required" | "Documents" | "Institution Profile";

type ScreeningFailure = {
  criterion_id: string;
  failure_category: string;
  extracted_evidence: string;
  expected: string;
  actual: string;
  explanation: string;
  suggested_correction: string;
};

export function InstitutionPortal({ token, signOut }: { token: string; signOut: () => void }) {
  const [tab, setTab] = useState<PortalTab>("Overview"),
    [overview, setOverview] = useState<Row>({}),
    [applications, setApplications] = useState<Application[]>([]),
    [alerts, setAlerts] = useState<AlertRow[]>([]),
    [documents, setDocuments] = useState<DocumentRow[]>([]),
    [institution, setInstitution] = useState<Row | null>(null),
    [selected, setSelected] = useState<ApplicationDetail | null>(null),
    [query, setQuery] = useState(""),
    [statusFilter, setStatusFilter] = useState(""),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [notice, setNotice] = useState(""),
    [screeningResult, setScreeningResult] = useState<{
      outcome: string;
      explanation: string;
      failures: ScreeningFailure[];
    } | null>(null);

  const fail = (message: string) => { setNotice(""); setError(message); };
  const done = (message: string) => { setError(""); setNotice(message); };

  const load = async () => {
    try {
      setLoading(true); setError("");
      if (tab === "Overview") setOverview(await api("/api/portal/overview", { token }));
      if (tab === "My Applications") {
        const params = new URLSearchParams();
        if (query) params.set("case_id", query.trim());
        if (statusFilter) params.set("status", statusFilter);
        setApplications(await api(`/api/portal/applications${params.size ? `?${params}` : ""}`, { token }));
      }
      if (tab === "Alerts & Action Required") setAlerts(await api("/api/portal/alerts", { token }));
      if (tab === "Documents") setDocuments(await api("/api/portal/documents", { token }));
      if (tab === "Institution Profile") setInstitution(await api("/api/portal/institution", { token }));
    } catch (x) { fail((x as Error).message); } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, [tab]);

  const open = async (caseId: string, updateUrl = true) => {
    try {
      setLoading(true); setError("");
      const detail = await api<ApplicationDetail>(`/api/portal/applications/${encodeURIComponent(caseId)}`, { token });
      setSelected(detail);
      setTab("My Applications");
      if (updateUrl) {
        window.history.pushState({}, "", `/applications/${encodeURIComponent(detail.case.case_id)}`);
      }
    } catch (x) {
      const err = x as Error;
      if (err.message && err.message.toLowerCase().includes("not found")) {
        fail("Application not found. This application does not exist or does not belong to your institution.");
      } else {
        fail(`Unable to load application: ${err.message || "Server unavailable"}`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const handleUrl = () => {
      const match = /^\/(?:applications|cases)\/([^/]+)$/.exec(window.location.pathname);
      if (match) {
        void open(decodeURIComponent(match[1]), false);
      }
    };
    handleUrl();
    window.addEventListener("popstate", handleUrl);
    return () => window.removeEventListener("popstate", handleUrl);
  }, [token]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget, data = new FormData(form), get = (key: string) => String(data.get(key) || "").trim();
    if (get("subject").length < 4) return setError("Subject must be at least 4 characters.");
    if (!get("description")) return setError("Application details are required.");
    try {
      const receipt_date = dateOnlyForApi(get("receipt_date"), "Submission Date");
      setLoading(true); setError(""); setScreeningResult(null);

      // Pre-fetch institution permanent ID if not loaded
      let currentInst = institution;
      if (!currentInst) {
        currentInst = await api<Row>("/api/portal/institution", { token });
        setInstitution(currentInst);
      }
      const permanentId = String(currentInst?.permanent_id || "");

      // Execute AI Pre-Scrutiny Intake Screening (Supporting both JSON and Real File Uploads)
      let screening: {
        screening_outcome: string;
        outcome_explanation: string;
        failures?: ScreeningFailure[];
      };

      const fileInput = form.querySelector('input[type="file"]') as HTMLInputElement;
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        const fd = new FormData();
        fd.append("permanent_id", permanentId);
        fd.append("subject", get("subject"));
        fd.append("description", get("description"));
        fd.append("category", get("category"));
        fd.append("incident_date", receipt_date);
        for (let i = 0; i < fileInput.files.length; i++) {
          fd.append("files", fileInput.files[i]);
        }
        const res = await fetch("http://127.0.0.1:8000/api/ai/screen-with-documents", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || body.error?.message || "Screening failed");
        }
        screening = await res.json();
      } else {
        screening = await api<{
          screening_outcome: string;
          outcome_explanation: string;
          failures?: ScreeningFailure[];
        }>("/api/ai/screen-submission", {
          token, method: "POST",
          body: JSON.stringify({
            permanent_id: permanentId,
            subject: get("subject"),
            description: get("description"),
            category: get("category"),
            incident_date: receipt_date,
          }),
        });
      }

      if (screening.screening_outcome !== "PASSED") {
        setScreeningResult({
          outcome: screening.screening_outcome,
          explanation: screening.outcome_explanation,
          failures: screening.failures || [],
        });
        setError(`AI Pre-Scrutiny flagged issues (${screening.screening_outcome}). Review the analysis below.`);
        setLoading(false);
        return;
      }

      // If screening passes, register application
      const created = await api<Application>("/api/cases", {
        token, method: "POST",
        body: JSON.stringify({
          receipt_date,
          source_channel: get("source_channel"),
          category: get("category"),
          priority: "Medium",
          subject: get("subject"),
          description: get("description"),
        }),
      });
      done(`? AI Pre-Scrutiny Passed! Application ${created.case_id} registered successfully.`);
      form.reset();
      setScreeningResult(null);
      await open(created.case_id);
    } catch (x) { fail((x as Error).message); } finally { setLoading(false); }
  };

  const tabs: PortalTab[] = ["Overview", "My Applications", "Submit Application", "Alerts & Action Required", "Documents", "Institution Profile"];

  return (
    <div className="shell">
      <aside>
        <div className="brand">AICTE<br /><strong>CaseConnect</strong></div>
        {tabs.map(item => (
          <button
            className={tab === item ? "active" : ""}
            onClick={() => { setSelected(null); setError(""); setNotice(""); setTab(item); }}
            key={item}
          >
            {item}
          </button>
        ))}
        <button onClick={signOut}>Sign Out</button>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">INSTITUTION USER PORTAL</p>
            <h1>{tab}</h1>
            <small>Authorized self-service workspace strictly isolated to your registered institution.</small>
          </div>
          <span className="badge">Institution Rep</span>
        </header>

        {loading && <p className="loading">Loading?</p>}
        {error && <p className="error">{error}</p>}
        {notice && <p className="notice">{notice}</p>}

        {tab === "Overview" && (
          <>
            <div className="cards">
              <article><p>Total Applications</p><strong>{String(overview.total_applications ?? 0)}</strong></article>
              <article><p>Under Review</p><strong>{String(overview.under_review ?? 0)}</strong></article>
              <article><p>Action Required</p><strong>{String(overview.action_required ?? 0)}</strong></article>
              <article><p>Approved / Disposed</p><strong>{String(overview.approved ?? 0)}</strong></article>
              <article><p>Closed / Rejected</p><strong>{String(overview.rejected ?? 0)}</strong></article>
            </div>

            <section className="panel">
              <h2>Recent Applications</h2>
              <ApplicationTable rows={(overview.recent_applications || []) as Application[]} open={open} />
            </section>

            {Array.isArray(overview.recent_activity) && overview.recent_activity.length > 0 && (
              <section className="panel">
                <h2>Recent Processing Activity</h2>
                <div className="table"><table>
                  <thead><tr><th>Action</th><th>Remarks / Details</th><th>Date &amp; Time</th></tr></thead>
                  <tbody>
                    {(overview.recent_activity as HistoryEvent[]).map(ev => (
                      <tr key={ev.id}>
                        <td><span className="badge">{ev.action_type.replaceAll("_", " ")}</span></td>
                        <td>{ev.remarks || "?"}</td>
                        <td>{String(ev.created_at).slice(0, 16).replace("T", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              </section>
            )}
          </>
        )}

        {tab === "My Applications" && (
          <section className="panel">
            <div className="toolbar">
              <input
                placeholder="Search Application ID"
                value={query}
                onChange={event => setQuery(event.target.value)}
              />
              <select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
                <option value="">All Statuses</option>
                <option value="Received">Received</option>
                <option value="Under Review">Under Review</option>
                <option value="Under Process">Under Process</option>
                <option value="Pending Institution Response">Pending Institution Response</option>
                <option value="Transferred">Transferred</option>
                <option value="Escalated">Escalated</option>
                <option value="Disposed">Disposed</option>
                <option value="Closed">Closed</option>
              </select>
              <button onClick={() => void load()}>Search</button>
              {(query || statusFilter) && (
                <button onClick={() => { setQuery(""); setStatusFilter(""); void load(); }}>Clear</button>
              )}
            </div>

            {selected ? (
              <ApplicationDetailView
                detail={selected}
                token={token}
                back={() => { setSelected(null); window.history.pushState({}, "", "/"); }}
                reload={() => open(selected.case.case_id)}
                notice={done}
                fail={fail}
              />
            ) : (
              <ApplicationTable rows={applications} open={open} />
            )}
          </section>
        )}

        {tab === "Submit Application" && (
          <form className="panel formgrid" onSubmit={submit} noValidate>
            <div className="formtitle">
              <h2>Submit Application / Grievance</h2>
              <p>Submissions undergo automated AI pre-scrutiny intake checks before formal registration.</p>
            </div>
            {screeningResult && (
              <div className="wide" style={{
                background: screeningResult.outcome === "REJECTED_AT_INTAKE" ? "#fff5f5" : "#fffbeb",
                border: `1px solid ${screeningResult.outcome === "REJECTED_AT_INTAKE" ? "#feb2b2" : "#fbd38d"}`,
                borderRadius: 8,
                padding: 16,
                marginBottom: 16,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <h3 style={{ margin: 0, color: screeningResult.outcome === "REJECTED_AT_INTAKE" ? "#c53030" : "#b7791f" }}>
                    {screeningResult.outcome === "REJECTED_AT_INTAKE" ? "? AI Intake Pre-Scrutiny: Rejection" : "?? AI Intake Pre-Scrutiny: Correction Required"}
                  </h3>
                  <span className="badge">{screeningResult.outcome}</span>
                </div>
                <p style={{ margin: "4px 0 12px 0", fontSize: 14 }}>{screeningResult.explanation}</p>
                {screeningResult.failures.length > 0 && (
                  <div>
                    <strong>Flagged Criteria ({screeningResult.failures.length}):</strong>
                    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                      {screeningResult.failures.map((f, i) => (
                        <div key={i} style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 6, padding: 10 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                            <strong>{f.criterion_id.replaceAll("_", " ")}</strong>
                            <code style={{ fontSize: 12, color: "#c53030" }}>{f.failure_category}</code>
                          </div>
                          <p style={{ margin: "2px 0", fontSize: 13 }}><strong>Extracted Evidence:</strong> {f.extracted_evidence}</p>
                          <p style={{ margin: "2px 0", fontSize: 13 }}><strong>Explanation:</strong> {f.explanation}</p>
                          {f.suggested_correction && (
                            <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "#276749" }}>
                              <strong>Suggested Correction:</strong> {f.suggested_correction}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <p style={{ fontSize: 12, color: "#718096", marginTop: 12, marginBottom: 0 }}>
                  Please address the flagged items in the form below and resubmit.
                </p>
              </div>
            )}
            <label>Submission Date *<input name="receipt_date" type="date" required /></label>
            <label>Subject *<input name="subject" minLength={10} placeholder="Clear, specific subject (min 10 characters)" required /></label>
            <label>Category *
              <select name="category" defaultValue="Academic" required>
                {["Academic", "Financial", "Infrastructure", "Faculty", "Accreditation", "Affiliation", "Admission", "Conduct", "Examination", "Other"].map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>Source Channel *<input name="source_channel" defaultValue="Institution Portal" required /></label>
            <label className="wide">Upload Evidence Document (PDF, Image, Text)<input name="evidence_file" type="file" /><small>Attach official fee receipt, circular, appointment order, or representation proof for AI intake validation.</small></label>
            <label className="wide">Application / Grievance Details *<textarea name="description" rows={5} placeholder="Provide complete factual details (minimum 20 words for AI screening intake compliance)..." required /></label>
            <button disabled={loading}>{loading ? "Checking with AI & Submitting?" : "Submit with Pre-Scrutiny"}</button>
          </form>
        )}

        {tab === "Alerts & Action Required" && (
          <section className="panel">
            <h2>Alerts &amp; Action Notices</h2>
            {alerts.length ? (
              <div className="table"><table>
                <thead><tr><th>Alert Notice</th><th>Application</th><th>Issued Date</th><th>Current State</th><th /></tr></thead>
                <tbody>{alerts.map(item => (
                  <tr key={item.id}>
                    <td><strong>{item.title}</strong><br /><small>{item.message}</small></td>
                    <td>
                      {item.case_reference ? (
                        <code>{item.case_reference}</code>
                      ) : item.case_id ? (
                        <code>Case #{String(item.case_id)}</code>
                      ) : (
                        "?"
                      )}
                    </td>
                    <td>{String(item.created_at).slice(0, 10)}</td>
                    <td><span className="badge">{item.resolved_at ? "Resolved" : "Action required"}</span></td>
                    <td>
                      {(item.case_reference || item.case_id) && (
                        <button onClick={() => void open(String(item.case_reference || item.case_id))}>Open Application</button>
                      )}
                    </td>
                  </tr>
                ))}</tbody>
              </table></div>
            ) : <p className="empty">No active alerts or action items require your attention.</p>}
          </section>
        )}

        {tab === "Documents" && (
          <section className="panel">
            <h2>Application Document Dockets</h2>
            <p><small>Listing authenticated document dockets and application filings for your institution.</small></p>
            {documents.length ? (
              <div className="table"><table>
                <thead><tr><th>Case Reference</th><th>Document Type</th><th>Category</th><th>Submission Date</th><th>Status</th><th>Access Level</th><th /></tr></thead>
                <tbody>{documents.map(doc => (
                  <tr key={doc.case_id}>
                    <td><code>{doc.case_id}</code></td>
                    <td>{doc.document_type}</td>
                    <td>{doc.category}</td>
                    <td>{formatDateOnly(doc.submission_date)}</td>
                    <td><span className="badge">{doc.status}</span></td>
                    <td><small>{doc.access_tier}</small></td>
                    <td><button onClick={() => void open(doc.case_id)}>View Case</button></td>
                  </tr>
                ))}</tbody>
              </table></div>
            ) : <p className="empty">No document dockets found for your institution.</p>}
          </section>
        )}

        {tab === "Institution Profile" && institution && (
          <section className="panel">
            <h2>{String(institution.name)}</h2>
            <div className="cards">
              <article><p>Institution ID</p><strong>{String(institution.id)}</strong></article>
              <article><p>Permanent ID</p><strong>{String(institution.permanent_id || "Not provided")}</strong></article>
              <article><p>Region</p><strong>{String(institution.region || "?")}</strong></article>
              <article><p>Status</p><strong>{String(institution.status || "?")}</strong></article>
            </div>
            <p style={{ marginTop: 20 }}>
              <small>
                This profile is bound to your authorized login. Institution details are managed by the AICTE Regional Bureau.
                Synthetic demonstration data only ? not official AICTE records.
              </small>
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

function ApplicationTable({ rows, open }: { rows: Application[]; open: (id: string) => void }) {
  if (!rows.length) return <p className="empty">No applications found matching this view.</p>;
  return (
    <div className="table"><table>
      <thead><tr><th>Application ID</th><th>Subject</th><th>Submission Date</th><th>Stage / Status</th><th>Last Updated</th><th /></tr></thead>
      <tbody>{rows.map(item => (
        <tr key={item.case_id}>
          <td><button className="linkbutton" onClick={() => open(item.case_id)}>{item.case_id}</button></td>
          <td className="subject">{item.subject}</td>
          <td>{formatDateOnly(item.receipt_date)}</td>
          <td><span className="badge">{item.status}</span></td>
          <td>{String(item.updated_at).slice(0, 10)}</td>
          <td><button onClick={() => open(item.case_id)}>View Details</button></td>
        </tr>
      ))}</tbody>
    </table></div>
  );
}

function ApplicationDetailView({
  detail,
  token,
  back,
  reload,
  notice,
  fail,
}: {
  detail: ApplicationDetail;
  token: string;
  back: () => void;
  reload: () => Promise<void>;
  notice: (msg: string) => void;
  fail: (msg: string) => void;
}) {
  const item = detail.case;
  const [responseRemarks, setResponseRemarks] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleClarification = async (e: FormEvent) => {
    e.preventDefault();
    if (responseRemarks.trim().length < 2) return fail("Please enter at least 2 characters for your response.");
    try {
      setSubmitting(true);
      await api(`/api/portal/applications/${encodeURIComponent(item.case_id)}/respond`, {
        token,
        method: "POST",
        body: JSON.stringify({ remarks: responseRemarks.trim() }),
      });
      setResponseRemarks("");
      notice("Clarification submitted to the reviewing bureau successfully.");
      await reload();
    } catch (x) {
      fail((x as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="detail">
      <div className="detailhead">
        <div>
          <p className="eyebrow">APPLICATION DETAIL</p>
          <h2>{item.case_id} <span className="badge">{item.status}</span></h2>
          <p>{item.subject}</p>
        </div>
        <button onClick={back}>Back to Applications</button>
      </div>

      <div className="cards">
        <article><p>Submission Date</p><strong>{formatDateOnly(item.receipt_date)}</strong></article>
        <article><p>Category</p><strong>{item.category}</strong></article>
        <article><p>Current Stage</p><strong>{item.status}</strong></article>
        <article><p>Priority</p><strong>{item.priority}</strong></article>
      </div>

      <p className="description">{item.description}</p>

      {/* Clarification / Response form when action is required */}
      <section className="panel" style={{ marginTop: 24, background: "#f8fbff", borderColor: "#cde1f7" }}>
        <h3>Submit Clarification / Correction Response</h3>
        <p><small>Provide an explanation or respond to officer queries regarding this application docket.</small></p>
        <form onSubmit={handleClarification}>
          <textarea
            value={responseRemarks}
            onChange={e => setResponseRemarks(e.target.value)}
            placeholder="Type your clarification or correction response here..."
            rows={3}
            style={{ width: "100%", padding: 10, borderRadius: 6, border: "1px solid #b9d5f5", boxSizing: "border-box" }}
            required
          />
          <div style={{ marginTop: 8 }}>
            <button disabled={submitting}>
              {submitting ? "Submitting Response?" : "Submit Clarification to AICTE"}
            </button>
          </div>
        </form>
      </section>

      <h3>Application Event Timeline</h3>
      {detail.history.length ? (
        <div className="table"><table>
          <thead><tr><th>Action</th><th>Remarks / Notes</th><th>Timestamp</th></tr></thead>
          <tbody>{detail.history.map(event => (
            <tr key={event.id}>
              <td><span className="badge">{event.action_type.replaceAll("_", " ")}</span></td>
              <td>{event.remarks || "?"}</td>
              <td>{String(event.created_at).slice(0, 16).replace("T", " ")}</td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <p className="empty">No timeline events recorded yet.</p>}

      <h3>Related Alerts &amp; Deficiency Notices</h3>
      {detail.alerts.length ? (
        <div className="table"><table>
          <thead><tr><th>Notice</th><th>Issued Date</th><th>State</th></tr></thead>
          <tbody>{detail.alerts.map(alert => (
            <tr key={alert.id}>
              <td><strong>{alert.title}</strong><br /><small>{alert.message}</small></td>
              <td>{String(alert.created_at).slice(0, 10)}</td>
              <td><span className="badge">{alert.resolved_at ? "Resolved" : "Pending Action"}</span></td>
            </tr>
          ))}</tbody>
        </table></div>
      ) : <p className="empty">No notices or deficiencies issued for this application.</p>}

      {detail.history.some(e => e.action_type === "transferred") && (
        <p className="empty"><small>Notice: This application has been routed between bureaus for inter-disciplinary assessment.</small></p>
      )}

      <div className="actions">
        <button onClick={() => void reload()}>Refresh Application Status</button>
      </div>
    </section>
  );
}
