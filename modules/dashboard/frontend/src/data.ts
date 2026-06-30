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
