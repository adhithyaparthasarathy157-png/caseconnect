import { FormEvent, useEffect, useState } from "react";
import { api, download } from "./api";
import { formatDateTime } from "./dateTime";

export type Bureau = { id: number; code: string; name: string };

export type SlaRecordItem = {
  id: number;
  case_id: number;
  case_ref: string;
  institution_name: string;
  category: string;
  priority: string;
  current_bureau_code: string;
  current_bureau_id: number | null;
  assigned_officer_name: string | null;
  policy_id: number;
  policy_name: string;
  policy_version: number;
  start_time: string | null;
  original_deadline: string | null;
  current_deadline: string | null;
  target_duration_days: number;
  calendar_type: string;
  status: string;
  elapsed_duration_hours: number;
  remaining_duration_hours: number;
  consumed_percentage: number;
  is_paused: boolean;
  escalation_level: number;
  completion_time: string | null;
  completed_within_sla: boolean | null;
  last_evaluated_at: string | null;
};

export type SlaDashboardSummary = {
  total_active_records: number;
  on_track_count: number;
  warning_count: number;
  at_risk_count: number;
  breached_count: number;
  paused_count: number;
  completed_count: number;
  completed_within_sla_count: number;
  compliance_percentage: number;
  active_compliance_percentage: number;
  active_in_sla_percentage?: number;
  active_healthy_percentage?: number;
  total_escalations_count: number;
  generated_at: string;
};

export type SlaPolicy = {
  id: number;
  name: string;
  category: string;
  priority: string | null;
  bureau_id: number | null;
  target_duration_days: number;
  calendar_type: string;
  warning_threshold_pct: number;
  at_risk_threshold_pct: number;
  escalation_config: Record<string, unknown> | null;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
};

export type SlaPolicyVersion = {
  id: number;
  policy_id: number;
  version: number;
  snapshot: Record<string, unknown>;
  change_reason: string | null;
  created_at: string;
};

export type BureauSlaMetric = {
  bureau_id: number;
  bureau_code: string;
  bureau_name: string;
  total_cases: number;
  pending_cases: number;
  on_track: number;
  warning: number;
  at_risk: number;
  breached: number;
  paused: number;
  completed: number;
  compliance_percentage: number;
  avg_disposal_days: number;
  avg_overdue_days: number;
  escalation_count: number;
};

export type SlaEscalationItem = {
  id: string;
  sla_record_id: number;
  case_id: number;
  case_ref?: string;
  escalation_level: number;
  trigger_type: string;
  target_role: string | null;
  reason: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  created_at: string;
};

export type SlaRiskItem = {
  case_id: string;
  case_numeric_id: number;
  institution_name: string;
  category: string;
  priority: string;
  current_bureau: string;
  sla_consumed_pct: number;
  days_overdue: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  contributing_factors: string[];
  recommended_action: string;
  model_type: string;
  evaluated_at: string;
};

export type SlaPauseItem = {
  id: number;
  sla_record_id: number;
  paused_at: string;
  pause_reason: string;
  pause_notes: string | null;
  resumed_at: string | null;
  resume_notes: string | null;
  duration_seconds: number | null;
};

export type SlaEventItem = {
  id: string;
  sla_record_id: number;
  case_id: number;
  event_type: string;
  remarks: string | null;
  created_at: string;
};

export const VALID_PAUSE_REASONS = [
  "Awaiting Institutional Clarification / Response",
  "Pending Expert Committee / Scrutiny Inspection",
  "Court Stay / Legal Proceedings",
  "Inter-Bureau Jurisdiction Determination",
  "Official Document Verification in Progress",
  "External Regulatory Review",
  "Other Administrative Requirement",
];

export function getSlaStatusBadgeClass(status: string): string {
  switch (status?.toUpperCase()) {
    case "ON_TRACK":
      return "badge-sla-on-track";
    case "WARNING":
      return "badge-sla-warning";
    case "AT_RISK":
      return "badge-sla-at-risk";
    case "BREACHED":
      return "badge-sla-breached";
    case "PAUSED":
      return "badge-sla-paused";
    case "COMPLETED":
      return "badge-sla-completed";
    default:
      return "badge";
  }
}

export function getRiskBadgeClass(level: string): string {
  switch (level?.toUpperCase()) {
    case "CRITICAL":
      return "badge-risk-critical";
    case "HIGH":
      return "badge-risk-high";
    case "MEDIUM":
      return "badge-risk-medium";
    case "LOW":
      return "badge-risk-low";
    default:
      return "badge";
  }
}

export function formatDurationHours(hours: number): string {
  if (hours <= 0) return "0h";
  const d = Math.floor(hours / 24);
  const h = Math.round(hours % 24);
  if (d > 0) return `${d}d ${h}h`;
  return `${h}h`;
}

// ============================================================================
// Case Detail SLA Panel
// ============================================================================

export function CaseSlaPanel({
  caseId,
  token,
  notice,
  fail,
  reload,
}: {
  caseId: string;
  token: string;
  notice: (msg: string) => void;
  fail: (msg: string) => void;
  reload: () => Promise<void>;
}) {
  const [record, setRecord] = useState<SlaRecordItem & { pauses?: SlaPauseItem[] } | null>(null);
  const [events, setEvents] = useState<SlaEventItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showPauseModal, setShowPauseModal] = useState(false);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [pauseReason, setPauseReason] = useState(VALID_PAUSE_REASONS[0]);
  const [pauseNotes, setPauseNotes] = useState("");
  const [resumeNotes, setResumeNotes] = useState("");

  const loadSlaData = async () => {
    try {
      setLoading(true);
      const rec = await api<SlaRecordItem & { pauses?: SlaPauseItem[] }>(`/api/sla/records/${encodeURIComponent(caseId)}`, { token });
      setRecord(rec);
      const evts = await api<SlaEventItem[]>(`/api/sla/records/${encodeURIComponent(caseId)}/events`, { token });
      setEvents(evts);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId && token) {
      void loadSlaData();
    }
  }, [caseId, token]);

  const handlePause = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/api/sla/records/${encodeURIComponent(caseId)}/pause`, {
        token,
        method: "POST",
        body: JSON.stringify({ reason: pauseReason, notes: pauseNotes }),
      });
      setShowPauseModal(false);
      setPauseNotes("");
      notice("SLA clock successfully paused.");
      await loadSlaData();
      await reload();
    } catch (err) {
      fail((err as Error).message);
    }
  };

  const handleResume = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/api/sla/records/${encodeURIComponent(caseId)}/resume`, {
        token,
        method: "POST",
        body: JSON.stringify({ notes: resumeNotes }),
      });
      setShowResumeModal(false);
      setResumeNotes("");
      notice("SLA clock resumed. Deadline recalculated.");
      await loadSlaData();
      await reload();
    } catch (err) {
      fail((err as Error).message);
    }
  };

  if (loading && !record) {
    return <p className="loading">Loading live SLA tracking data...</p>;
  }

  if (!record) {
    return (
      <div className="empty-neutral">
        <p>No active SLA record mapped to this complaint.</p>
        <button
          onClick={async () => {
            try {
              await api(`/api/sla/records/${encodeURIComponent(caseId)}/recalculate`, {
                token,
                method: "POST",
                body: JSON.stringify({ reason: "Manual SLA policy initialization" }),
              });
              notice("SLA tracking initialized.");
              await loadSlaData();
            } catch (err) {
              fail((err as Error).message);
            }
          }}
        >
          Initialize SLA Tracking
        </button>
      </div>
    );
  }

  const consumedPct = Math.min(100, Math.max(0, record.consumed_percentage || 0));
  const isOverdue = record.remaining_duration_hours < 0 && record.status !== "COMPLETED";

  // Visual fill color based on status
  let fillColor = "#16a34a"; // green
  if (record.status === "WARNING") fillColor = "#d97706"; // amber
  else if (record.status === "AT_RISK") fillColor = "#ea580c"; // orange
  else if (record.status === "BREACHED") fillColor = "#dc2626"; // red
  else if (record.status === "PAUSED") fillColor = "#0284c7"; // blue
  else if (record.status === "COMPLETED") fillColor = "#64748b"; // gray

  return (
    <div style={{ marginTop: "16px", padding: "16px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <span style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748b", fontWeight: 700 }}>
            Policy: {record.policy_name || "Standard Policy"} (v{record.policy_version})
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
            <span className={getSlaStatusBadgeClass(record.status)}>{record.status}</span>
            <span style={{ fontSize: "12px", color: "#475569" }}>
              {record.calendar_type === "business_days" ? "Working Days (Mon-Fri)" : "Calendar Days"} • Target: {record.target_duration_days} days
            </span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          {!record.is_paused && record.status !== "COMPLETED" && (
            <button className="btn-sm btn-outline" onClick={() => setShowPauseModal(true)}>
              Pause SLA
            </button>
          )}
          {record.is_paused && (
            <button className="btn-sm" style={{ background: "#059669" }} onClick={() => setShowResumeModal(true)}>
              Resume SLA
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar & Countdown */}
      <div style={{ margin: "14px 0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", fontWeight: 600, color: "#334155" }}>
          <span>Elapsed: {formatDurationHours(record.elapsed_duration_hours)} ({Math.round(consumedPct)}% consumed)</span>
          <span>
            {isOverdue ? (
              <strong style={{ color: "#dc2626" }}>Overdue by {formatDurationHours(Math.abs(record.remaining_duration_hours))}</strong>
            ) : (
              <span>Remaining: {formatDurationHours(record.remaining_duration_hours)}</span>
            )}
          </span>
        </div>
        <div className="sla-progress-track">
          <div className="sla-progress-fill" style={{ width: `${consumedPct}%`, backgroundColor: fillColor }} />
        </div>
      </div>

      {/* SLA Metric Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "10px", marginTop: "12px" }}>
        <div style={{ padding: "8px 12px", background: "#ffffff", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "11px", color: "#64748b" }}>Start Time</p>
          <strong style={{ fontSize: "12px", color: "#0f172a" }}>{record.start_time ? formatDateTime(record.start_time) : "-"}</strong>
        </div>
        <div style={{ padding: "8px 12px", background: "#ffffff", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "11px", color: "#64748b" }}>Current Deadline</p>
          <strong style={{ fontSize: "12px", color: isOverdue ? "#dc2626" : "#0f172a" }}>
            {record.current_deadline ? formatDateTime(record.current_deadline) : "-"}
          </strong>
        </div>
        <div style={{ padding: "8px 12px", background: "#ffffff", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "11px", color: "#64748b" }}>Escalation Tier</p>
          <strong style={{ fontSize: "12px", color: record.escalation_level > 0 ? "#b91c1c" : "#0f172a" }}>
            {record.escalation_level > 0 ? `Level ${record.escalation_level}` : "None"}
          </strong>
        </div>
        <div style={{ padding: "8px 12px", background: "#ffffff", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "11px", color: "#64748b" }}>Completion Status</p>
          <strong style={{ fontSize: "12px", color: record.completed_within_sla ? "#16a34a" : (record.completed_within_sla === false ? "#dc2626" : "#475569") }}>
            {record.completed_within_sla === true ? "Within SLA" : record.completed_within_sla === false ? "Breached SLA" : "In Progress"}
          </strong>
        </div>
      </div>

      {/* Pause History */}
      {record.pauses && record.pauses.length > 0 && (
        <details style={{ marginTop: "14px", background: "#ffffff" }}>
          <summary style={{ fontSize: "12px" }}>Pause History ({record.pauses.length} records)</summary>
          <div className="table" style={{ marginTop: "8px" }}>
            <table>
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>Paused At</th>
                  <th>Resumed At</th>
                  <th>Duration</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {record.pauses.map(p => (
                  <tr key={p.id}>
                    <td><strong>{p.pause_reason}</strong></td>
                    <td>{formatDateTime(p.paused_at)}</td>
                    <td>{p.resumed_at ? formatDateTime(p.resumed_at) : <span style={{ color: "#0284c7" }}>Active</span>}</td>
                    <td>{p.duration_seconds ? formatDurationHours(p.duration_seconds / 3600) : "-"}</td>
                    <td style={{ fontSize: "11px" }}>{p.pause_notes || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* Event Timeline */}
      {events.length > 0 && (
        <details style={{ marginTop: "8px", background: "#ffffff" }}>
          <summary style={{ fontSize: "12px" }}>SLA Audit Events ({events.length})</summary>
          <div className="table" style={{ marginTop: "8px" }}>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Type</th>
                  <th>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {events.map(ev => (
                  <tr key={ev.id}>
                    <td>{formatDateTime(ev.created_at)}</td>
                    <td><span className="badge">{ev.event_type}</span></td>
                    <td style={{ fontSize: "12px" }}>{ev.remarks || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* Pause Modal */}
      {showPauseModal && (
        <div className="sla-modal-overlay">
          <div className="sla-modal-box">
            <div className="sla-modal-header">
              <h3>Pause SLA Tracking</h3>
              <button className="sla-modal-close" onClick={() => setShowPauseModal(false)}>×</button>
            </div>
            <form onSubmit={handlePause}>
              <div style={{ display: "grid", gap: "12px" }}>
                <label>
                  Authorized Pause Reason *
                  <select
                    value={pauseReason}
                    onChange={e => setPauseReason(e.target.value)}
                    required
                    style={{ marginTop: "4px" }}
                  >
                    {VALID_PAUSE_REASONS.map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Administrative Notes / Docket Reference
                  <textarea
                    rows={3}
                    value={pauseNotes}
                    onChange={e => setPauseNotes(e.target.value)}
                    placeholder="Enter formal justification, inquiry dispatch notice, or court reference..."
                    style={{ marginTop: "4px" }}
                  />
                </label>
              </div>
              <div className="sla-modal-actions">
                <button type="button" className="btn-outline" onClick={() => setShowPauseModal(false)}>Cancel</button>
                <button type="submit" style={{ background: "#d97706" }}>Confirm Pause</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Resume Modal */}
      {showResumeModal && (
        <div className="sla-modal-overlay">
          <div className="sla-modal-box">
            <div className="sla-modal-header">
              <h3>Resume SLA Tracking</h3>
              <button className="sla-modal-close" onClick={() => setShowResumeModal(false)}>×</button>
            </div>
            <form onSubmit={handleResume}>
              <div style={{ display: "grid", gap: "12px" }}>
                <p style={{ margin: 0, fontSize: "13px", color: "#475569" }}>
                  Resuming SLA tracking will shift the current deadline forward by the exact paused duration.
                </p>
                <label>
                  Resume Notes / Institutional Response Summary
                  <textarea
                    rows={3}
                    value={resumeNotes}
                    onChange={e => setResumeNotes(e.target.value)}
                    placeholder="Enter reply received summary or scrutiny findings..."
                    style={{ marginTop: "4px" }}
                  />
                </label>
              </div>
              <div className="sla-modal-actions">
                <button type="button" className="btn-outline" onClick={() => setShowResumeModal(false)}>Cancel</button>
                <button type="submit" style={{ background: "#059669" }}>Confirm Resume</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main SLA Management Page
// ============================================================================

export function SlaManagementPage({
  token,
  notice,
  fail,
  selectCase,
  bureaus,
}: {
  token: string;
  notice: (msg: string) => void;
  fail: (msg: string) => void;
  selectCase: (caseId: string) => void;
  bureaus: Bureau[];
}) {
  const [subtab, setSubtab] = useState<"monitoring" | "policies" | "bureaus" | "escalations" | "risk">("monitoring");
  const [summary, setSummary] = useState<SlaDashboardSummary | null>(null);
  const [records, setRecords] = useState<SlaRecordItem[]>([]);
  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [bureauMetrics, setBureauMetrics] = useState<BureauSlaMetric[]>([]);
  const [escalations, setEscalations] = useState<SlaEscalationItem[]>([]);
  const [riskItems, setRiskItems] = useState<SlaRiskItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Filters for Monitoring
  const [statusFilter, setStatusFilter] = useState("");
  const [bureauFilter, setBureauFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);

  // Policy Modals
  const [showCreatePolicyModal, setShowCreatePolicyModal] = useState(false);
  const [showEditPolicyModal, setShowEditPolicyModal] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<SlaPolicy | null>(null);
  const [policyVersions, setPolicyVersions] = useState<SlaPolicyVersion[]>([]);
  const [showVersionsModal, setShowVersionsModal] = useState(false);

  // Escalation Acknowledge Modal
  const [selectedEscalation, setSelectedEscalation] = useState<SlaEscalationItem | null>(null);
  const [ackRemarks, setAckRemarks] = useState("");

  const loadSummary = async () => {
    try {
      const data = await api<SlaDashboardSummary>("/api/sla/dashboard", { token });
      setSummary(data);
    } catch (e) {
      fail((e as Error).message);
    }
  };

  const loadRecords = async (targetPage = page) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (statusFilter) params.append("status", statusFilter);
      if (bureauFilter) params.append("bureau_id", bureauFilter);
      if (searchQuery) params.append("search", searchQuery);
      params.append("page", String(targetPage));
      params.append("page_size", "15");

      const res = await api<{ items: SlaRecordItem[]; total: number; page: number }>(`/api/sla/records?${params.toString()}`, { token });
      setRecords(res.items);
      setTotalRecords(res.total);
      setPage(res.page);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadPolicies = async () => {
    try {
      setLoading(true);
      const list = await api<SlaPolicy[]>("/api/sla/policies", { token });
      setPolicies(list);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadBureauMetrics = async () => {
    try {
      setLoading(true);
      const list = await api<BureauSlaMetric[]>("/api/sla/analytics/bureaus", { token });
      setBureauMetrics(list);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadEscalations = async () => {
    try {
      setLoading(true);
      const list = await api<SlaEscalationItem[]>("/api/sla/escalations", { token });
      setEscalations(list);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadRiskItems = async () => {
    try {
      setLoading(true);
      const data = await api<{ high_risk_cases: SlaRiskItem[]; total_assessed: number }>("/api/sla/risk/dashboard", { token });
      setRiskItems(data.high_risk_cases || []);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    if (token) {
      void loadSummary();
      if (subtab === "monitoring") void loadRecords(1);
      else if (subtab === "policies") void loadPolicies();
      else if (subtab === "bureaus") void loadBureauMetrics();
      else if (subtab === "escalations") void loadEscalations();
      else if (subtab === "risk") void loadRiskItems();
    }
  }, [subtab, token]);

  const handleRunEvaluation = async () => {
    try {
      setLoading(true);
      const res = await api<{ evaluated: number; warnings: number; at_risk: number; breached: number; escalations: number }>("/api/sla/evaluate", {
        token,
        method: "POST",
      });
      notice(`SLA evaluation complete: ${res.evaluated} cases evaluated, ${res.breached} breached, ${res.escalations} new escalations triggered.`);
      void loadSummary();
      void loadRecords(1);
    } catch (e) {
      fail((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleExportCsv = async () => {
    try {
      await download("/api/sla/reports/export-csv", token);
      notice("SLA monitoring CSV downloaded successfully.");
    } catch (e) {
      fail((e as Error).message);
    }
  };

  const handleAcknowledgeEscalation = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedEscalation) return;
    try {
      await api(`/api/sla/escalations/${selectedEscalation.id}/acknowledge`, {
        token,
        method: "POST",
        body: JSON.stringify({ remarks: ackRemarks }),
      });
      notice("Escalation formally acknowledged.");
      setSelectedEscalation(null);
      setAckRemarks("");
      void loadEscalations();
    } catch (err) {
      fail((err as Error).message);
    }
  };

  return (
    <section className="panel">
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <p className="eyebrow">INTEGRATED SLA & PENDENCY INTELLIGENCE</p>
          <h2 style={{ margin: "2px 0 0" }}>SLA Command Centre</h2>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button className="btn-outline" onClick={handleExportCsv}>
            Export CSV
          </button>
          <button onClick={handleRunEvaluation} disabled={loading}>
            {loading ? "Evaluating..." : "Run Live Evaluation"}
          </button>
        </div>
      </div>

      {/* KPI Cards Strip */}
      {summary && (
        <div className="sla-kpi-grid">
          <div className="sla-kpi-card">
            <p>Active Tracked</p>
            <strong>{summary.total_active_records}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #16a34a" }}>
            <p>On Track</p>
            <strong style={{ color: "#16a34a" }}>{summary.on_track_count}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #d97706" }}>
            <p>Warning (75%)</p>
            <strong style={{ color: "#d97706" }}>{summary.warning_count}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #ea580c" }}>
            <p>At Risk (90%)</p>
            <strong style={{ color: "#ea580c" }}>{summary.at_risk_count}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #dc2626" }}>
            <p>Breached</p>
            <strong style={{ color: "#dc2626" }}>{summary.breached_count}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #0284c7" }}>
            <p>Paused</p>
            <strong style={{ color: "#0284c7" }}>{summary.paused_count}</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #4f46e5" }}>
            <p>Disposal Compliance</p>
            <strong style={{ color: "#4f46e5" }}>{summary.compliance_percentage}%</strong>
          </div>
          <div className="sla-kpi-card" style={{ borderLeft: "4px solid #10b981" }}>
            <p>Active In-SLA Rate</p>
            <strong style={{ color: "#10b981" }}>{summary.active_compliance_percentage}%</strong>
          </div>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="sla-subnav">
        <button className={subtab === "monitoring" ? "active" : ""} onClick={() => setSubtab("monitoring")}>
          SLA Monitoring
        </button>
        <button className={subtab === "policies" ? "active" : ""} onClick={() => setSubtab("policies")}>
          Policy Administration
        </button>
        <button className={subtab === "bureaus" ? "active" : ""} onClick={() => setSubtab("bureaus")}>
          Bureau Performance
        </button>
        <button className={subtab === "escalations" ? "active" : ""} onClick={() => setSubtab("escalations")}>
          Escalations ({summary?.total_escalations_count || 0})
        </button>
        <button className={subtab === "risk" ? "active" : ""} onClick={() => setSubtab("risk")}>
          AI Pendency Risk
        </button>
      </div>

      {/* SUBTAB 1: SLA MONITORING */}
      {subtab === "monitoring" && (
        <div>
          {/* Filters Bar */}
          <div className="toolbar" style={{ flexWrap: "wrap", marginBottom: "12px" }}>
            <select
              value={statusFilter}
              onChange={e => {
                setStatusFilter(e.target.value);
                setPage(1);
                void loadRecords(1);
              }}
              style={{ maxWidth: "180px" }}
            >
              <option value="">All SLA Statuses</option>
              <option value="ON_TRACK">On Track</option>
              <option value="WARNING">Warning</option>
              <option value="AT_RISK">At Risk</option>
              <option value="BREACHED">Breached</option>
              <option value="PAUSED">Paused</option>
              <option value="COMPLETED">Completed</option>
            </select>

            <select
              value={bureauFilter}
              onChange={e => {
                setBureauFilter(e.target.value);
                setPage(1);
                void loadRecords(1);
              }}
              style={{ maxWidth: "200px" }}
            >
              <option value="">All Bureaus</option>
              {bureaus.map(b => (
                <option key={b.id} value={b.id}>{b.code} - {b.name}</option>
              ))}
            </select>

            <input
              type="text"
              placeholder="Search by Case ID, Institution, or Subject..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { setPage(1); void loadRecords(1); } }}
              style={{ flex: 1, minWidth: "220px" }}
            />

            <button onClick={() => { setPage(1); void loadRecords(1); }}>
              Filter
            </button>
          </div>

          {/* Monitoring Table */}
          {records.length === 0 ? (
            <p className="empty-neutral">No complaint cases match the current SLA filter.</p>
          ) : (
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Case Ref</th>
                    <th>Institution</th>
                    <th>Bureau</th>
                    <th>Priority</th>
                    <th>Deadline</th>
                    <th>Target</th>
                    <th>Consumed %</th>
                    <th>SLA Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map(r => (
                    <tr key={r.id}>
                      <td>
                        <button className="linkbutton" onClick={() => selectCase(r.case_ref)}>
                          <strong>{r.case_ref}</strong>
                        </button>
                      </td>
                      <td style={{ maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {r.institution_name}
                      </td>
                      <td><span className="badge">{r.current_bureau_code}</span></td>
                      <td>{r.priority}</td>
                      <td>
                        <span style={{ color: r.remaining_duration_hours < 0 && r.status !== "COMPLETED" ? "#dc2626" : "inherit" }}>
                          {r.current_deadline ? formatDateTime(r.current_deadline) : "-"}
                        </span>
                      </td>
                      <td>{r.target_duration_days}d</td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ fontSize: "11px", fontWeight: 600 }}>{Math.round(r.consumed_percentage)}%</span>
                          <div style={{ width: "45px", height: "6px", background: "#e2e8f0", borderRadius: "3px", overflow: "hidden" }}>
                            <div
                              style={{
                                width: `${Math.min(100, r.consumed_percentage)}%`,
                                height: "100%",
                                background: r.status === "BREACHED" ? "#dc2626" : r.status === "AT_RISK" ? "#ea580c" : r.status === "WARNING" ? "#d97706" : "#16a34a",
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td><span className={getSlaStatusBadgeClass(r.status)}>{r.status}</span></td>
                      <td>
                        <button className="btn-sm btn-outline" onClick={() => selectCase(r.case_ref)}>
                          View Case
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "14px" }}>
            <span style={{ fontSize: "12px", color: "#64748b" }}>
              Total: {totalRecords} records (Page {page} of {Math.max(1, Math.ceil(totalRecords / 15))})
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn-sm btn-outline"
                disabled={page <= 1}
                onClick={() => { const p = page - 1; setPage(p); void loadRecords(p); }}
              >
                Previous
              </button>
              <button
                className="btn-sm btn-outline"
                disabled={page >= Math.ceil(totalRecords / 15)}
                onClick={() => { const p = page + 1; setPage(p); void loadRecords(p); }}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 2: POLICY ADMINISTRATION */}
      {subtab === "policies" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <div className="disclaimer-pill" style={{ margin: 0 }}>
              Illustrative demonstration policies for prototyping. Administer institutional SLA thresholds here.
            </div>
            <button onClick={() => setShowCreatePolicyModal(true)}>
              + Create Policy
            </button>
          </div>

          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Policy Name</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>Target Days</th>
                  <th>Calendar</th>
                  <th>Thresholds (Warn/Risk)</th>
                  <th>Ver</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map(p => (
                  <tr key={p.id}>
                    <td><strong>{p.name}</strong></td>
                    <td>{p.category}</td>
                    <td>{p.priority || <em style={{ color: "#94a3b8" }}>All</em>}</td>
                    <td>{p.target_duration_days} days</td>
                    <td>{p.calendar_type === "business_days" ? "Working Days" : "Calendar"}</td>
                    <td>{p.warning_threshold_pct}% / {p.at_risk_threshold_pct}%</td>
                    <td><span className="badge">v{p.version}</span></td>
                    <td>
                      <span className={p.is_active ? "badge-resolved" : "badge-sla-completed"}>
                        {p.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-sm btn-outline"
                          onClick={() => {
                            setSelectedPolicy(p);
                            setShowEditPolicyModal(true);
                          }}
                        >
                          Edit
                        </button>
                        <button
                          className="btn-sm btn-outline"
                          onClick={async () => {
                            try {
                              const versions = await api<SlaPolicyVersion[]>(`/api/sla/policies/${p.id}/versions`, { token });
                              setSelectedPolicy(p);
                              setPolicyVersions(versions);
                              setShowVersionsModal(true);
                            } catch (err) {
                              fail((err as Error).message);
                            }
                          }}
                        >
                          History
                        </button>
                        <button
                          className="btn-sm btn-outline"
                          style={{ color: p.is_active ? "#dc2626" : "#16a34a" }}
                          onClick={async () => {
                            try {
                              const endpoint = p.is_active ? `/api/sla/policies/${p.id}/deactivate` : `/api/sla/policies/${p.id}/activate`;
                              await api(endpoint, { token, method: "POST" });
                              notice(`Policy '${p.name}' ${p.is_active ? "deactivated" : "activated"}.`);
                              void loadPolicies();
                            } catch (err) {
                              fail((err as Error).message);
                            }
                          }}
                        >
                          {p.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Create Policy Modal */}
          {showCreatePolicyModal && (
            <div className="sla-modal-overlay">
              <div className="sla-modal-box">
                <div className="sla-modal-header">
                  <h3>Create Configurable SLA Policy</h3>
                  <button className="sla-modal-close" onClick={() => setShowCreatePolicyModal(false)}>×</button>
                </div>
                <form
                  onSubmit={async e => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    try {
                      await api("/api/sla/policies", {
                        token,
                        method: "POST",
                        body: JSON.stringify({
                          name: form.get("name"),
                          category: form.get("category"),
                          priority: form.get("priority") || null,
                          target_duration_days: Number(form.get("target_duration_days")),
                          calendar_type: form.get("calendar_type"),
                          warning_threshold_pct: Number(form.get("warning_threshold_pct")),
                          at_risk_threshold_pct: Number(form.get("at_risk_threshold_pct")),
                          is_active: true,
                        }),
                      });
                      setShowCreatePolicyModal(false);
                      notice("SLA policy created successfully.");
                      void loadPolicies();
                    } catch (err) {
                      fail((err as Error).message);
                    }
                  }}
                >
                  <div style={{ display: "grid", gap: "10px" }}>
                    <label>
                      Policy Name *
                      <input name="name" required minLength={3} placeholder="e.g., Campus Anti-Ragging Expedited SLA" />
                    </label>
                    <label>
                      Complaint Category *
                      <input name="category" required placeholder="e.g., Grievance, Faculty, Infrastructure, Approval" />
                    </label>
                    <label>
                      Priority Scope (Optional)
                      <select name="priority">
                        <option value="">Apply to all priorities</option>
                        <option value="Critical">Critical</option>
                        <option value="High">High</option>
                        <option value="Medium">Medium</option>
                        <option value="Low">Low</option>
                      </select>
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <label>
                        Target Duration (Days) *
                        <input name="target_duration_days" type="number" min={1} max={365} defaultValue={15} required />
                      </label>
                      <label>
                        Calendar Type *
                        <select name="calendar_type" defaultValue="business_days">
                          <option value="business_days">Working Days (Mon-Fri)</option>
                          <option value="calendar_days">Calendar Days</option>
                        </select>
                      </label>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <label>
                        Warning Threshold (%)
                        <input name="warning_threshold_pct" type="number" min={10} max={95} defaultValue={75} required />
                      </label>
                      <label>
                        At-Risk Threshold (%)
                        <input name="at_risk_threshold_pct" type="number" min={20} max={99} defaultValue={90} required />
                      </label>
                    </div>
                  </div>
                  <div className="sla-modal-actions">
                    <button type="button" className="btn-outline" onClick={() => setShowCreatePolicyModal(false)}>Cancel</button>
                    <button type="submit">Create Policy</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Edit Policy Modal */}
          {showEditPolicyModal && selectedPolicy && (
            <div className="sla-modal-overlay">
              <div className="sla-modal-box">
                <div className="sla-modal-header">
                  <h3>Edit Policy: {selectedPolicy.name} (v{selectedPolicy.version})</h3>
                  <button className="sla-modal-close" onClick={() => setShowEditPolicyModal(false)}>×</button>
                </div>
                <form
                  onSubmit={async e => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    try {
                      await api(`/api/sla/policies/${selectedPolicy.id}`, {
                        token,
                        method: "PUT",
                        body: JSON.stringify({
                          name: form.get("name"),
                          target_duration_days: Number(form.get("target_duration_days")),
                          warning_threshold_pct: Number(form.get("warning_threshold_pct")),
                          at_risk_threshold_pct: Number(form.get("at_risk_threshold_pct")),
                          change_reason: form.get("change_reason") || "Policy parameters adjusted",
                        }),
                      });
                      setShowEditPolicyModal(false);
                      notice(`Policy updated to v${selectedPolicy.version + 1}.`);
                      void loadPolicies();
                    } catch (err) {
                      fail((err as Error).message);
                    }
                  }}
                >
                  <div style={{ display: "grid", gap: "10px" }}>
                    <label>
                      Policy Name
                      <input name="name" defaultValue={selectedPolicy.name} required />
                    </label>
                    <label>
                      Target Duration (Days)
                      <input name="target_duration_days" type="number" min={1} max={365} defaultValue={selectedPolicy.target_duration_days} required />
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <label>
                        Warning Threshold (%)
                        <input name="warning_threshold_pct" type="number" defaultValue={selectedPolicy.warning_threshold_pct} required />
                      </label>
                      <label>
                        At-Risk Threshold (%)
                        <input name="at_risk_threshold_pct" type="number" defaultValue={selectedPolicy.at_risk_threshold_pct} required />
                      </label>
                    </div>
                    <label>
                      Revision Reason / Executive Note *
                      <textarea name="change_reason" required placeholder="Mandatory audit justification for revising policy thresholds..." rows={3} />
                    </label>
                  </div>
                  <div className="sla-modal-actions">
                    <button type="button" className="btn-outline" onClick={() => setShowEditPolicyModal(false)}>Cancel</button>
                    <button type="submit">Save & Version Snapshot</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Versions History Modal */}
          {showVersionsModal && selectedPolicy && (
            <div className="sla-modal-overlay">
              <div className="sla-modal-box" style={{ maxWidth: "750px" }}>
                <div className="sla-modal-header">
                  <h3>Immutable Version Audit: {selectedPolicy.name}</h3>
                  <button className="sla-modal-close" onClick={() => setShowVersionsModal(false)}>×</button>
                </div>
                {policyVersions.length === 0 ? (
                  <p className="empty-neutral">No historical revisions recorded for this policy (currently at v1).</p>
                ) : (
                  <div className="table">
                    <table>
                      <thead>
                        <tr>
                          <th>Version</th>
                          <th>Recorded At</th>
                          <th>Target Days</th>
                          <th>Thresholds</th>
                          <th>Audit Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {policyVersions.map(v => (
                          <tr key={v.id}>
                            <td><span className="badge">v{v.version}</span></td>
                            <td>{formatDateTime(v.created_at)}</td>
                            <td>{(v.snapshot as any)?.target_duration_days || "-"}d</td>
                            <td>{(v.snapshot as any)?.warning_threshold_pct}% / {(v.snapshot as any)?.at_risk_threshold_pct}%</td>
                            <td style={{ fontSize: "11px" }}>{v.change_reason || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="sla-modal-actions">
                  <button className="btn-outline" onClick={() => setShowVersionsModal(false)}>Close</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUBTAB 3: BUREAU PERFORMANCE */}
      {subtab === "bureaus" && (
        <div>
          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Bureau</th>
                  <th>Total Active</th>
                  <th>On Track</th>
                  <th>Warning</th>
                  <th>At Risk</th>
                  <th>Breached</th>
                  <th>Paused</th>
                  <th>Compliance %</th>
                  <th>Avg Disposal</th>
                  <th>Escalations</th>
                </tr>
              </thead>
              <tbody>
                {bureauMetrics.map(bm => (
                  <tr key={bm.bureau_id}>
                    <td>
                      <strong>{bm.bureau_code}</strong> - {bm.bureau_name}
                    </td>
                    <td>{bm.pending_cases}</td>
                    <td style={{ color: "#16a34a", fontWeight: 600 }}>{bm.on_track}</td>
                    <td style={{ color: "#d97706", fontWeight: 600 }}>{bm.warning}</td>
                    <td style={{ color: "#ea580c", fontWeight: 600 }}>{bm.at_risk}</td>
                    <td style={{ color: "#dc2626", fontWeight: 600 }}>{bm.breached}</td>
                    <td>{bm.paused}</td>
                    <td>
                      <span className="badge" style={{ background: bm.compliance_percentage >= 80 ? "#dcfce7" : "#fee2e2", color: bm.compliance_percentage >= 80 ? "#166534" : "#991b1b" }}>
                        {bm.compliance_percentage}%
                      </span>
                    </td>
                    <td>{bm.avg_disposal_days}d</td>
                    <td>
                      {bm.escalation_count > 0 ? (
                        <span style={{ color: "#b91c1c", fontWeight: 700 }}>{bm.escalation_count}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUBTAB 4: ESCALATIONS CENTRE */}
      {subtab === "escalations" && (
        <div>
          {escalations.length === 0 ? (
            <p className="empty-neutral">No active escalations recorded. All cases are within manageable SLA parameters.</p>
          ) : (
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Escalation Level</th>
                    <th>Case Ref</th>
                    <th>Target Authority / Role</th>
                    <th>Trigger Reason</th>
                    <th>Triggered At</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map(esc => (
                    <tr key={esc.id}>
                      <td>
                        <span className={esc.escalation_level >= 3 ? "badge-sla-breached" : esc.escalation_level === 2 ? "badge-sla-at-risk" : "badge-sla-warning"}>
                          Tier {esc.escalation_level}
                        </span>
                      </td>
                      <td>
                        <button className="linkbutton" onClick={() => selectCase(esc.case_ref || String(esc.case_id))}>
                          <strong>{esc.case_ref || `Case #${esc.case_id}`}</strong>
                        </button>
                      </td>
                      <td>{esc.target_role || "Authority"}</td>
                      <td style={{ maxWidth: "260px", fontSize: "12px" }}>{esc.reason}</td>
                      <td>{formatDateTime(esc.created_at)}</td>
                      <td>
                        <span className={esc.acknowledged ? "badge-resolved" : "badge-sla-breached"}>
                          {esc.acknowledged ? "Acknowledged" : "Pending Action"}
                        </span>
                      </td>
                      <td>
                        {!esc.acknowledged && (
                          <button
                            className="btn-sm btn-outline"
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setAckRemarks("");
                            }}
                          >
                            Acknowledge
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Acknowledge Escalation Modal */}
          {selectedEscalation && (
            <div className="sla-modal-overlay">
              <div className="sla-modal-box">
                <div className="sla-modal-header">
                  <h3>Acknowledge Tier {selectedEscalation.escalation_level} Escalation</h3>
                  <button className="sla-modal-close" onClick={() => setSelectedEscalation(null)}>×</button>
                </div>
                <form onSubmit={handleAcknowledgeEscalation}>
                  <div style={{ display: "grid", gap: "10px" }}>
                    <p style={{ margin: 0, fontSize: "13px", color: "#334155" }}>
                      <strong>Reason:</strong> {selectedEscalation.reason}
                    </p>
                    <label>
                      Administrative Acknowledgment Remarks *
                      <textarea
                        rows={3}
                        required
                        value={ackRemarks}
                        onChange={e => setAckRemarks(e.target.value)}
                        placeholder="Detail the supervisory intervention or directive dispatched to expedite case resolution..."
                      />
                    </label>
                  </div>
                  <div className="sla-modal-actions">
                    <button type="button" className="btn-outline" onClick={() => setSelectedEscalation(null)}>Cancel</button>
                    <button type="submit">Submit Formal Acknowledgment</button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUBTAB 5: AI PENDENCY RISK */}
      {subtab === "risk" && (
        <div>
          <div className="disclaimer-pill" style={{ marginBottom: "14px" }}>
            Deterministic rule-based AI pendency heuristic. Provides proactive early warning indicators without altering official statutory deadlines.
          </div>

          {riskItems.length === 0 ? (
            <p className="empty-neutral">No active complaints currently exhibit elevated pendency risk.</p>
          ) : (
            <div style={{ display: "grid", gap: "12px" }}>
              {riskItems.map(item => (
                <div
                  key={item.case_id}
                  style={{
                    background: "#ffffff",
                    border: "1px solid #e2e8f0",
                    borderLeft: `5px solid ${item.risk_level === "CRITICAL" ? "#dc2626" : item.risk_level === "HIGH" ? "#ea580c" : item.risk_level === "MEDIUM" ? "#d97706" : "#16a34a"}`,
                    borderRadius: "8px",
                    padding: "16px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <button className="linkbutton" onClick={() => selectCase(item.case_id)}>
                          <strong style={{ fontSize: "15px" }}>{item.case_id}</strong>
                        </button>
                        <span className={getRiskBadgeClass(item.risk_level)}>{item.risk_level} RISK ({item.risk_score}/100)</span>
                        <span className="badge">{item.current_bureau}</span>
                      </div>
                      <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#334155" }}>
                        <strong>{item.institution_name}</strong> • Category: {item.category} • Priority: {item.priority}
                      </p>
                    </div>
                    <button className="btn-sm btn-outline" onClick={() => selectCase(item.case_id)}>
                      Open Case
                    </button>
                  </div>

                  <div style={{ marginTop: "12px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                    <div>
                      <p style={{ margin: "0 0 6px", fontSize: "12px", fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
                        Contributing Friction Factors:
                      </p>
                      <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "12px", color: "#334155" }}>
                        {item.contributing_factors.map((f, idx) => (
                          <li key={idx}>{f}</li>
                        ))}
                      </ul>
                    </div>

                    <div style={{ padding: "10px 14px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                      <p style={{ margin: "0 0 4px", fontSize: "12px", fontWeight: 700, color: "#1e63b7", textTransform: "uppercase" }}>
                        Recommended Actionable Intervention:
                      </p>
                      <p style={{ margin: 0, fontSize: "13px", color: "#0f172a", lineHeight: 1.4 }}>
                        {item.recommended_action}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
