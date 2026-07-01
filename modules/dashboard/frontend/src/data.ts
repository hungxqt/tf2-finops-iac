import { dashboardSummarySchema, runtimeConfigSchema, type DashboardSummary, type RuntimeConfig } from "./schema";
import { DEFAULT_DATA_PREFIX, IS_LOCAL_DEV, RUNTIME_CONFIG_PATH, SUMMARY_FILE_NAME } from "./config";

async function fetchJson(path: string): Promise<unknown> {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} while loading ${path}`);
  }
  return response.json();
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  try {
    const payload = await fetchJson(RUNTIME_CONFIG_PATH);
    return runtimeConfigSchema.parse(payload);
  } catch (error) {
    if (IS_LOCAL_DEV) {
      return { data_prefix: DEFAULT_DATA_PREFIX };
    }
    throw error;
  }
}

export async function loadDashboardSummary(): Promise<DashboardSummary> {
  const config = await loadRuntimeConfig();
  const prefix = config.data_prefix || DEFAULT_DATA_PREFIX;
  const normalizedPrefix = prefix.endsWith("/") ? prefix : `${prefix}/`;

  try {
    const payload = await fetchJson(`${normalizedPrefix}${SUMMARY_FILE_NAME}`);
    return dashboardSummarySchema.parse(payload);
  } catch (error) {
    if (IS_LOCAL_DEV) {
      const { sampleDashboardData } = await import("./sampleData");
      return sampleDashboardData;
    }
    throw error;
  }
}

/**
 * Sends an ad-hoc manual-trigger request to the backend API Gateway endpoint
 * that calls StepFunctions:StartExecution with { is_ad_hoc: true }.
 *
 * In local dev (no trigger_api_url configured in runtime config), the function
 * simulates a successful trigger after a short delay so the button UX can be
 * exercised without AWS credentials.
 *
 * Returns the execution ARN on success.
 * Throws a descriptive Error on failure (quota exceeded, network error, etc.).
 */
export async function triggerAdHocRun(
  tenantId: string | undefined,
  accountId: string | undefined
): Promise<{ execution_arn: string }> {
  const config = await loadRuntimeConfig();
  const url = config.trigger_api_url;

  if (!url) {
    // Local-dev simulation: pretend the execution started after 1.5s.
    if (IS_LOCAL_DEV) {
      await new Promise((r) => setTimeout(r, 1500));
      return { execution_arn: `arn:aws:states:ap-southeast-1:123456789012:execution:tf2-finops-sandbox-workflow:adhoc-${Date.now()}` };
    }
    throw new Error("trigger_api_url is not configured in dashboard_runtime_config.json");
  }

  const body = JSON.stringify({
    is_ad_hoc: true,
    ...(tenantId   ? { tenant_id:  tenantId }  : {}),
    ...(accountId  ? { account_id: accountId } : {})
  });

  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body
  });

  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;

  if (!response.ok) {
    // Surface structured error from the backend (quota, policy, etc.)
    const cause = (payload as { message?: string; error?: string }).message
      || (payload as { message?: string; error?: string }).error
      || `HTTP ${response.status}`;
    throw new Error(cause);
  }

  return payload as { execution_arn: string };
}
