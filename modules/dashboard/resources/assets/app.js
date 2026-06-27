(function () {
  "use strict";

  var runtimeConfig = {};
  var state = {
    dashboard: null,
    filtered: null,
    selectedAnomalyId: null
  };

  var sampleDashboardData = {
    environment: "sandbox",
    viewer_role: "finance",
    generated_at: "2026-06-26T09:00:00Z",
    containment_locked: true,
    lock_reason: "error_budget_exceeded_threshold",
    lock_since: "2026-06-24T08:00:00Z",
    error_budget_remaining_pct: 0.8,
    spend_trend: [
      ["2026-03-29", 812, 790, false],
      ["2026-04-05", 844, 805, false],
      ["2026-04-12", 862, 821, false],
      ["2026-04-19", 905, 836, false],
      ["2026-04-26", 932, 852, false],
      ["2026-05-03", 948, 867, false],
      ["2026-05-10", 973, 882, false],
      ["2026-05-17", 998, 896, false],
      ["2026-05-24", 1036, 910, true],
      ["2026-05-31", 1072, 925, false],
      ["2026-06-07", 1128, 941, false],
      ["2026-06-14", 1216, 958, true],
      ["2026-06-21", 1264, 976, true],
      ["2026-06-26", 1194, 988, false]
    ],
    anomalies: [
      {
        anomaly_id: "ANM-2026-0623A",
        severity: "CRITICAL",
        account_id: "200000000010",
        account_name: "ml-research",
        service: "AmazonEC2",
        squad: "squad-prediction-models",
        owner_tag_status: "valid",
        confidence_score: 0.94,
        data_confidence: "HIGH",
        evidence_window_start: "2026-06-22T00:00:00Z",
        evidence_window_end: "2026-06-23T23:59:59Z",
        cost_delta_usd_per_day: 427.5,
        explanation: "GPU training instances ran continuously above the expected baseline and exceeded the approved experiment window."
      },
      {
        anomaly_id: "ANM-2026-0621B",
        severity: "WARNING",
        account_id: "200000000011",
        account_name: "staging",
        service: "AmazonRDS",
        squad: "central-cdo",
        owner_tag_status: "missing owner",
        confidence_score: 0.76,
        data_confidence: "LOW",
        evidence_window_start: "2026-06-20T00:00:00Z",
        evidence_window_end: "2026-06-21T23:59:59Z",
        cost_delta_usd_per_day: 118.2,
        explanation: "Database spend rose while CloudWatch utilization was incomplete, so the platform stayed in alert-only mode."
      },
      {
        anomaly_id: "ANM-2026-0618C",
        severity: "LOW",
        account_id: "200000000012",
        account_name: "prod-core",
        service: "AmazonCloudFront",
        squad: "squad-web",
        owner_tag_status: "valid",
        confidence_score: 0.68,
        data_confidence: "HIGH",
        evidence_window_start: "2026-06-18T00:00:00Z",
        evidence_window_end: "2026-06-18T23:59:59Z",
        cost_delta_usd_per_day: 49.4,
        explanation: "Traffic-adjusted cost increased slowly and remains below the immediate Finance escalation threshold."
      }
    ],
    impacted: [
      { name: "squad-prediction-models", type: "Squad", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
      { name: "AmazonEC2", type: "Service", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
      { name: "ml-research", type: "Account", spend_delta_usd_per_day: 427.5, owner_tag_status: "valid" },
      { name: "central-cdo", type: "Squad", spend_delta_usd_per_day: 118.2, owner_tag_status: "missing owner" }
    ],
    containment: [
      {
        audit_id: "ANM-2026-0623A",
        resource_id: "i-0fbgpu00000004",
        account_id: "200000000010",
        squad: "squad-prediction-models",
        action_type: "tag-for-review",
        execution_mode: "dry-run",
        status: "PENDING_APPROVAL",
        containment_locked: true,
        error_budget_remaining_pct: 0.8,
        audit_record_uri: "s3://company-cdo-200000000010-telemetry/audit/year=2026/month=06/ANM-2026-0623A.json",
        actions_log: [
          { timestamp: "2026-06-23T17:05:46Z", action: "tag-for-review", status: "DRY_RUN_COMPLETED", actor: "finops-ai-engine-role" }
        ]
      },
      {
        audit_id: "ANM-2026-0621B",
        resource_id: "db-staging-analytics",
        account_id: "200000000011",
        squad: "central-cdo",
        action_type: "tag-for-review",
        execution_mode: "dry-run",
        status: "ESCALATED",
        containment_locked: false,
        error_budget_remaining_pct: 74.2,
        audit_record_uri: "s3://company-cdo-200000000010-telemetry/audit/year=2026/month=06/ANM-2026-0621B.json",
        actions_log: [
          { timestamp: "2026-06-21T14:00:00Z", action: "tag-for-review", status: "ALERT_ONLY", actor: "finops-router" }
        ]
      }
    ],
    approvals: [
      {
        approval_id: "APR-2026-0623A",
        audit_id: "ANM-2026-0623A",
        environment: "sandbox",
        requested_action: "quota-cap",
        execution_mode: "apply",
        status: "PENDING_APPROVAL",
        owner: "squad-prediction-models",
        justification: "Non-production GPU quota cap needs human approval before apply-mode enforcement.",
        requested_at: "2026-06-23T17:12:00Z"
      }
    ],
    alert_previews: [
      {
        audience: "Finance",
        channel: "SNS or SES",
        anomaly_id: "ANM-2026-0623A",
        summary: "Critical cost spike above $100/day with complete ingestion.",
        data_confidence: "HIGH",
        action_visibility: "No action buttons or CLI commands",
        audit_link_label: "CloudFront audit record"
      },
      {
        audience: "Engineering",
        channel: "Slack digest or Jira ticket",
        anomaly_id: "ANM-2026-0623A",
        summary: "Owner squad receives resource, environment, tag status, and proposed rollback path.",
        data_confidence: "HIGH",
        action_visibility: "Short-lived Verify and Rollback links when policy allows",
        audit_link_label: "Authenticated action links"
      }
    ],
    audit_diffs: [
      {
        audit_id: "ANM-2026-0623A",
        before: ["finops:review absent", "quota unchanged", "owner tag valid"],
        after: ["finops:review=pending", "quota cap proposed", "audit retained 90 days"],
        correlation_id: "corr-uuid-4444-5555-6666",
        idempotency_key: "tenant-uuid-1111-2222-3333:2026-06-22:daily_batch"
      }
    ],
    admin_settings: [
      { name: "Finance group", value: "finops-finance-readonly", status: "read-only" },
      { name: "Engineering group", value: "finops-engineering-operator", status: "operator actions" },
      { name: "CDO admin group", value: "finops-cdo-admin", status: "admin controls" },
      { name: "Synthetic data visibility", value: "enabled for sandbox review", status: "admin managed" }
    ]
  };

  function $(id) {
    return document.getElementById(id);
  }

  function currency(value, suffix) {
    var formatted = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: value >= 100 ? 0 : 1
    }).format(Number(value || 0));
    return suffix ? formatted + suffix : formatted;
  }

  function asPercent(value) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Number(value || 0)) + "%";
  }

  function labelForDataConfidence(value) {
    if (value === "HIGH") {
      return "Complete ingestion";
    }
    if (value === "LOW") {
      return "Telemetry delay";
    }
    return "Unknown";
  }

  function canOperate() {
    var role = String((state.dashboard && state.dashboard.viewer_role) || "finance").toLowerCase();
    return role === "engineering" || role === "cdo" || role === "admin";
  }

  async function fetchJson(path) {
    var response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }
    return response.json();
  }

  async function loadDashboard() {
    try {
      runtimeConfig = await fetchJson("dashboard_runtime_config.json");
    } catch (error) {
      runtimeConfig = { data_prefix: "summaries/" };
    }

    var prefix = runtimeConfig.data_prefix || "summaries/";
    try {
      state.dashboard = await fetchJson(prefix + "dashboard-summary.json");
    } catch (error) {
      state.dashboard = sampleDashboardData;
      $("actionStatus").textContent = "Using bundled synthetic sample until dashboard-summary.json is published.";
    }
    state.selectedAnomalyId = (state.dashboard.anomalies[0] || {}).anomaly_id || null;
    populateFilters();
    applyFilters();
  }

  function populateFilters() {
    var data = state.dashboard;
    var filters = [
      ["accountFilter", "account_id"],
      ["serviceFilter", "service"],
      ["squadFilter", "squad"]
    ];
    filters.forEach(function (entry) {
      var select = $(entry[0]);
      var key = entry[1];
      var values = Array.from(new Set(data.anomalies.map(function (item) { return item[key]; }).filter(Boolean))).sort();
      select.innerHTML = '<option value="all">All</option>' + values.map(function (value) {
        return '<option value="' + value + '">' + value + "</option>";
      }).join("");
      select.addEventListener("change", applyFilters);
    });
    $("rangeFilter").addEventListener("change", applyFilters);
  }

  function applyFilters() {
    var data = state.dashboard;
    var account = $("accountFilter").value;
    var service = $("serviceFilter").value;
    var squad = $("squadFilter").value;
    var days = Number($("rangeFilter").value || 90);
    var trend = data.spend_trend.slice(-Math.max(2, Math.ceil(days / 7)));
    var anomalies = data.anomalies.filter(function (item) {
      return (account === "all" || item.account_id === account) &&
        (service === "all" || item.service === service) &&
        (squad === "all" || item.squad === squad);
    });
    state.filtered = {
      spend_trend: trend,
      anomalies: anomalies,
      impacted: data.impacted,
      containment: data.containment
    };
    renderAll();
  }

  function renderAll() {
    renderHeader();
    renderSummary();
    renderTrend();
    renderAnomalies();
    renderDetail();
    renderImpact();
    renderContainment();
    renderApprovals();
    renderAlertPreviews();
    renderAuditDiffs();
    renderAdminSettings();
  }

  function renderHeader() {
    $("environmentBadge").textContent = state.dashboard.environment || "environment";
    $("lastUpdated").textContent = "Updated " + new Date(state.dashboard.generated_at || Date.now()).toLocaleString();
    var role = String(state.dashboard.viewer_role || "finance").replace("-", " ");
    $("viewerRole").textContent = canOperate() ? role + " operator" : "finance read-only";
  }

  function renderSummary() {
    var trend = state.filtered.spend_trend;
    var anomalies = state.filtered.anomalies;
    var actual = trend.reduce(function (sum, row) { return sum + Number(row[1] || 0); }, 0);
    var baseline = trend.reduce(function (sum, row) { return sum + Number(row[2] || 0); }, 0);
    var waste = anomalies.reduce(function (sum, item) { return sum + Number(item.cost_delta_usd_per_day || 0); }, 0);
    var critical = anomalies.filter(function (item) { return item.severity === "CRITICAL"; }).length;
    var lowConfidence = anomalies.some(function (item) { return item.data_confidence === "LOW"; });
    $("totalSpend").textContent = currency(actual);
    $("spendDelta").textContent = currency(actual - baseline) + " over expected baseline";
    $("openAnomalies").textContent = anomalies.length;
    $("criticalAnomalies").textContent = critical + " critical";
    $("wasteImpact").textContent = currency(waste, "/day");
    $("dataConfidence").textContent = lowConfidence ? "Some telemetry delayed" : "Complete ingestion";
    $("errorBudget").textContent = asPercent(state.dashboard.error_budget_remaining_pct);
    $("lockState").textContent = state.dashboard.containment_locked ? "LOCKED_MODE active" : "Containment guardrail clear";
    var banner = $("lockBanner");
    if (state.dashboard.containment_locked) {
      banner.classList.remove("hidden");
      banner.textContent = "LOCKED_MODE: " + (state.dashboard.lock_reason || "containment locked") + " since " +
        new Date(state.dashboard.lock_since || Date.now()).toLocaleString() + ". All actions remain dry-run.";
    } else {
      banner.classList.add("hidden");
    }
  }

  function renderTrend() {
    var canvas = $("spendCanvas");
    var parent = canvas.parentElement;
    var pixelRatio = window.devicePixelRatio || 1;
    canvas.width = parent.clientWidth * pixelRatio;
    canvas.height = parent.clientHeight * pixelRatio;
    var ctx = canvas.getContext("2d");
    ctx.scale(pixelRatio, pixelRatio);
    var width = parent.clientWidth;
    var height = parent.clientHeight;
    var rows = state.filtered.spend_trend;
    var padding = { top: 24, right: 24, bottom: 38, left: 58 };
    var values = rows.flatMap(function (row) { return [Number(row[1]), Number(row[2])]; });
    var min = Math.max(0, Math.min.apply(null, values) * 0.9);
    var max = Math.max.apply(null, values) * 1.08;
    var x = function (index) {
      if (rows.length === 1) {
        return padding.left;
      }
      return padding.left + (index / (rows.length - 1)) * (width - padding.left - padding.right);
    };
    var y = function (value) {
      return height - padding.bottom - ((value - min) / (max - min || 1)) * (height - padding.top - padding.bottom);
    };
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "#d9e1ea";
    ctx.lineWidth = 1;
    ctx.font = "12px Segoe UI, Arial";
    ctx.fillStyle = "#617083";
    for (var i = 0; i < 4; i += 1) {
      var gy = padding.top + i * ((height - padding.top - padding.bottom) / 3);
      ctx.beginPath();
      ctx.moveTo(padding.left, gy);
      ctx.lineTo(width - padding.right, gy);
      ctx.stroke();
      var labelValue = max - i * ((max - min) / 3);
      ctx.fillText(currency(labelValue), 8, gy + 4);
    }
    drawLine(ctx, rows, x, y, 2, "#0f8b5f", true);
    drawArea(ctx, rows, x, y, height - padding.bottom);
    drawLine(ctx, rows, x, y, 1, "#2563eb", false);
    rows.forEach(function (row, index) {
      if (row[3]) {
        ctx.fillStyle = "#c53030";
        ctx.beginPath();
        ctx.arc(x(index), y(Number(row[1])), 6, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    ctx.fillStyle = "#617083";
    ctx.fillText(rows[0][0], padding.left, height - 12);
    ctx.textAlign = "right";
    ctx.fillText(rows[rows.length - 1][0], width - padding.right, height - 12);
    ctx.textAlign = "left";
  }

  function drawLine(ctx, rows, x, y, valueIndex, color, dashed) {
    ctx.beginPath();
    rows.forEach(function (row, index) {
      var px = x(index);
      var py = y(Number(row[valueIndex]));
      if (index === 0) {
        ctx.moveTo(px, py);
      } else {
        ctx.lineTo(px, py);
      }
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = dashed ? 2 : 3;
    ctx.setLineDash(dashed ? [8, 6] : []);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  function drawArea(ctx, rows, x, y, floor) {
    ctx.beginPath();
    rows.forEach(function (row, index) {
      var px = x(index);
      var py = y(Number(row[1]));
      if (index === 0) {
        ctx.moveTo(px, floor);
        ctx.lineTo(px, py);
      } else {
        ctx.lineTo(px, py);
      }
    });
    ctx.lineTo(x(rows.length - 1), floor);
    ctx.closePath();
    ctx.fillStyle = "rgba(37, 99, 235, 0.12)";
    ctx.fill();
  }

  function renderAnomalies() {
    var container = $("anomalyList");
    container.innerHTML = state.filtered.anomalies.map(function (item) {
      return '<button class="anomaly-row" data-anomaly-id="' + item.anomaly_id + '">' +
        '<strong>' + item.anomaly_id + " | " + item.service + "</strong>" +
        '<span>' + item.account_name + " | " + item.squad + " | " + currency(item.cost_delta_usd_per_day, "/day") + "</span>" +
        '<span class="pill ' + item.severity.toLowerCase() + '">' + item.severity + "</span>" +
        "</button>";
    }).join("");
    Array.from(container.querySelectorAll("button")).forEach(function (button) {
      button.addEventListener("click", function () {
        state.selectedAnomalyId = button.dataset.anomalyId;
        renderDetail();
      });
    });
  }

  function renderDetail() {
    var item = state.filtered.anomalies.find(function (entry) { return entry.anomaly_id === state.selectedAnomalyId; }) ||
      state.filtered.anomalies[0];
    if (!item) {
      return;
    }
    state.selectedAnomalyId = item.anomaly_id;
    var confidence = Math.round(Number(item.confidence_score || 0) * 100);
    $("selectedAnomalyId").textContent = item.anomaly_id + " | " + item.account_name;
    $("severityPill").textContent = item.severity;
    $("severityPill").className = "pill " + item.severity.toLowerCase();
    $("confidenceText").textContent = confidence + "%";
    $("confidenceFill").style.width = confidence + "%";
    $("detailDataConfidence").textContent = labelForDataConfidence(item.data_confidence) + " (" + item.data_confidence + ")";
    $("evidenceWindow").textContent = new Date(item.evidence_window_start).toLocaleDateString() + " to " +
      new Date(item.evidence_window_end).toLocaleDateString();
    $("costDelta").textContent = currency(item.cost_delta_usd_per_day, "/day");
    $("explanation").textContent = item.explanation;
  }

  function renderImpact() {
    var max = Math.max.apply(null, state.dashboard.impacted.map(function (item) { return item.spend_delta_usd_per_day; }));
    $("impactList").innerHTML = state.dashboard.impacted.map(function (item) {
      var pct = Math.round((item.spend_delta_usd_per_day / max) * 100);
      var tag = item.owner_tag_status === "valid" ? "owner tag valid" : item.owner_tag_status;
      var tagClass = item.owner_tag_status === "valid" ? "" : "tag-warning";
      return '<div class="impact-row">' +
        '<div><strong>' + item.name + '</strong><span>' + item.type + '</span></div>' +
        '<div>' + currency(item.spend_delta_usd_per_day, "/day") + '<div class="bar"><span style="width:' + pct + '%"></span></div></div>' +
        '<div class="' + tagClass + '">' + tag + '</div>' +
        '</div>';
    }).join("");
  }

  function renderContainment() {
    $("containmentTable").innerHTML = state.dashboard.containment.map(function (item) {
      var disabled = !canOperate() || item.containment_locked || item.execution_mode === "dry-run";
      var log = (item.actions_log || []).map(function (entry) {
        return entry.action + ": " + entry.status;
      }).join("; ");
      return "<tr>" +
        "<td><strong>" + item.audit_id + "</strong><br><small>" + log + "</small></td>" +
        "<td>" + item.resource_id + "<br><small>" + item.account_id + "</small></td>" +
        "<td>" + item.squad + "</td>" +
        "<td>" + item.execution_mode + "</td>" +
        "<td>" + item.status + "</td>" +
        "<td>" + asPercent(item.error_budget_remaining_pct) + "</td>" +
        '<td><a href="' + auditLink(item.audit_record_uri) + '">record</a></td>' +
        '<td><div class="action-buttons">' +
        '<button class="primary" data-action="verify" data-audit-id="' + item.audit_id + '"' + (!canOperate() ? " disabled" : "") + ">Verify</button>" +
        '<button class="danger" data-action="rollback" data-audit-id="' + item.audit_id + '"' + (disabled ? " disabled" : "") + ">Rollback</button>" +
        "</div></td>" +
        "</tr>";
    }).join("");
    Array.from(document.querySelectorAll("[data-action]")).forEach(function (button) {
      button.addEventListener("click", function () {
        sendAction(button.dataset.action, button.dataset.auditId);
      });
    });
  }

  function auditLink(uri) {
    if (String(uri || "").indexOf("s3://") === 0) {
      return "#";
    }
    return uri || "#";
  }

  async function sendAction(action, auditId) {
    $("actionStatus").textContent = "Submitting " + action + " for " + auditId + "...";
    var endpoint = action === "verify" ? "/v1/verify" : "/v1/audit/" + encodeURIComponent(auditId) + "/rollback";
    var body = action === "verify" ? {
      audit_id: auditId,
      execution_report: { source: "dashboard", result: "operator_requested_verify" }
    } : {
      reason: "Operator requested rollback from dashboard",
      rolled_back_by: "operator@company.internal",
      rollback_executed_at: new Date().toISOString(),
      rollback_status: "SUCCESS"
    };
    try {
      var response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        var text = await response.text();
        throw new Error(contractError(response.status, text));
      }
      var result = await response.json();
      $("actionStatus").textContent = action === "verify"
        ? "Verify returned next action: " + (result.next_action || "DONE")
        : "Rollback audit recorded: " + (result.audit_recorded === true ? "yes" : "pending");
    } catch (error) {
      $("actionStatus").textContent = error.message;
    }
  }

  function contractError(status, text) {
    var known = [
      "ERR_INVALID_SCHEMA",
      "ERR_IDEMPOTENCY_MISMATCH",
      "ERR_REPLAY_DETECTED",
      "ERR_CROSS_TENANT_DENIED",
      "ERR_ANOMALY_NOT_FOUND",
      "ERR_DUP_IDEMPOTENCY",
      "ERR_CONTAINMENT_NOT_SUPPORTED",
      "ERR_RATE_LIMITED",
      "ERR_LLM_TIMEOUT",
      "ERR_SERVICE_DOWN"
    ];
    var match = known.find(function (code) { return text.indexOf(code) >= 0; });
    if (match) {
      return match + " from API. No automatic containment was triggered.";
    }
    return "API request failed with HTTP " + status + ". No automatic containment was triggered.";
  }

  function renderApprovals() {
    var approvals = state.dashboard.approvals || [];
    var container = $("approvalList");
    if (!container) {
      return;
    }
    $("approvalGuard").textContent = canOperate() ? "operator review" : "finance read-only";
    container.innerHTML = approvals.map(function (item) {
      var disabled = !canOperate() || state.dashboard.containment_locked || item.execution_mode !== "apply";
      return '<div class="approval-row">' +
        '<div><strong>' + item.approval_id + '</strong><span>' + item.audit_id + ' | ' + item.environment + '</span></div>' +
        '<div><span class="pill warning">' + item.status + '</span><p>' + item.justification + '</p></div>' +
        '<div class="action-buttons">' +
        '<button class="primary" data-local-action="approve" data-approval-id="' + item.approval_id + '"' + (disabled ? ' disabled' : '') + '>Approve</button>' +
        '<button data-local-action="snooze" data-approval-id="' + item.approval_id + '"' + (!canOperate() ? ' disabled' : '') + '>Snooze</button>' +
        '<button class="danger" data-local-action="reject" data-approval-id="' + item.approval_id + '"' + (!canOperate() ? ' disabled' : '') + '>Reject</button>' +
        '</div>' +
        '</div>';
    }).join("");
    Array.from(document.querySelectorAll("[data-local-action]")).forEach(function (button) {
      button.addEventListener("click", function () {
        $("actionStatus").textContent = button.dataset.localAction + " recorded for " + button.dataset.approvalId + ".";
      });
    });
  }

  function renderAlertPreviews() {
    var previews = state.dashboard.alert_previews || [];
    var container = $("alertPreviewList");
    if (!container) {
      return;
    }
    container.innerHTML = previews.map(function (item) {
      var audienceClass = item.audience.toLowerCase() === "finance" ? "success" : "low";
      return '<div class="alert-preview">' +
        '<div><span class="pill ' + audienceClass + '">' + item.audience + '</span><strong>' + item.channel + '</strong></div>' +
        '<p>' + item.summary + '</p>' +
        '<dl class="mini-list"><div><dt>Data</dt><dd>' + labelForDataConfidence(item.data_confidence) + '</dd></div>' +
        '<div><dt>Controls</dt><dd>' + item.action_visibility + '</dd></div>' +
        '<div><dt>Audit</dt><dd>' + item.audit_link_label + '</dd></div></dl>' +
        '</div>';
    }).join("");
  }

  function renderAuditDiffs() {
    var diffs = state.dashboard.audit_diffs || [];
    var container = $("auditDiffList");
    if (!container) {
      return;
    }
    container.innerHTML = diffs.map(function (item) {
      return '<div class="audit-diff-row">' +
        '<strong>' + item.audit_id + '</strong>' +
        '<div class="diff-columns"><div><span>Before</span>' + renderDiffTags(item.before, 'removed') + '</div>' +
        '<div><span>After</span>' + renderDiffTags(item.after, 'added') + '</div></div>' +
        '<small>Correlation: ' + item.correlation_id + '</small><small>Idempotency: ' + item.idempotency_key + '</small>' +
        '</div>';
    }).join("");
  }

  function renderDiffTags(values, mode) {
    return '<div class="diff-tags">' + (values || []).map(function (value) {
      return '<span class="diff-tag ' + mode + '">' + value + '</span>';
    }).join('') + '</div>';
  }

  function renderAdminSettings() {
    var settings = state.dashboard.admin_settings || [];
    var container = $("adminSettingsList");
    if (!container) {
      return;
    }
    var isAdmin = String(state.dashboard.viewer_role || "finance").toLowerCase() === "admin" || String(state.dashboard.viewer_role || "finance").toLowerCase() === "cdo";
    $("adminGuard").textContent = isAdmin ? "admin" : "restricted";
    container.innerHTML = settings.map(function (item) {
      return '<div class="setting-row">' +
        '<div><strong>' + item.name + '</strong><span>' + item.value + '</span></div>' +
        '<span class="pill neutral">' + item.status + '</span>' +
        '<button' + (isAdmin ? '' : ' disabled') + '>Manage</button>' +
        '</div>';
    }).join("");
  }

  window.addEventListener("resize", function () {
    if (state.filtered) {
      renderTrend();
    }
  });
  loadDashboard();
}());

