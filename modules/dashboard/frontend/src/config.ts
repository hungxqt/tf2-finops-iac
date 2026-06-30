export const IS_LOCAL_DEV = import.meta.env.DEV;

export const RUNTIME_CONFIG_PATH =
  import.meta.env.VITE_DASHBOARD_RUNTIME_CONFIG_PATH || "/dashboard_runtime_config.json";

export const DEFAULT_DATA_PREFIX =
  import.meta.env.VITE_DASHBOARD_DATA_PREFIX || "summaries/";

export const SUMMARY_FILE_NAME =
  import.meta.env.VITE_DASHBOARD_SUMMARY_FILE || "dashboard-summary.json";
