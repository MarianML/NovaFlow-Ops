"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";

type UiError = { error: string };

type ApiOkResponse = {
  run_id: number;
  plan: unknown;
  ctx: unknown;
};

type ExecuteStepOkResponse = {
  run_id: number;
  status: string;
  executed_step_id: string | null;
};

type RunLogItem = {
  ts: string;
  level: string;
  message: string;
  data: unknown;
};

type RunDetailsOkResponse = {
  run: {
    id: number;
    task: string;
    status: string;
    plan: unknown;
  };
  logs: RunLogItem[];
};

type UiResult<T> = T | UiError;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function isApiOkResponse(v: unknown): v is ApiOkResponse {
  return (
    isRecord(v) && typeof v.run_id === "number" && "plan" in v && "ctx" in v
  );
}

function isExecuteStepOkResponse(v: unknown): v is ExecuteStepOkResponse {
  return (
    isRecord(v) &&
    typeof v.run_id === "number" &&
    typeof v.status === "string" &&
    "executed_step_id" in v
  );
}

function isRunLogItem(v: unknown): v is RunLogItem {
  return (
    isRecord(v) &&
    typeof v.ts === "string" &&
    typeof v.level === "string" &&
    typeof v.message === "string" &&
    "data" in v
  );
}

function isRunDetailsOkResponse(v: unknown): v is RunDetailsOkResponse {
  if (!isRecord(v)) return false;
  const run = v.run;
  const logs = v.logs;

  if (!isRecord(run)) return false;
  if (typeof run.id !== "number") return false;
  if (typeof run.task !== "string") return false;
  if (typeof run.status !== "string") return false;
  if (!("plan" in run)) return false;

  if (!Array.isArray(logs)) return false;
  if (!logs.every(isRunLogItem)) return false;

  return true;
}

function toErrorMessage(data: unknown, status: number): string {
  if (isRecord(data)) {
    const detail = typeof data.detail === "string" ? data.detail : undefined;
    const error = typeof data.error === "string" ? data.error : undefined;
    return detail ?? error ?? `HTTP ${status}`;
  }
  if (typeof data === "string" && data.trim()) return data;
  return `HTTP ${status}`;
}

async function safeReadJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    // Backend returned text/HTML instead of JSON
    return { error: text };
  }
}

function getApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

function safeStringify(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function getScreenshotUrlFromLogData(data: unknown): string | null {
  // Expected shape: { result: { screenshot_url: "/artifacts/..." } }
  if (!isRecord(data)) return null;
  const result = data.result;
  if (!isRecord(result)) return null;

  const url = result.screenshot_url;
  return typeof url === "string" ? url : null;
}

async function downloadViaBlob(url: string, filename: string) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const blob = await res.blob();

  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}

async function copyToClipboard(text: string) {
  // Clipboard API works on localhost and secure contexts
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback (older browsers)
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      return true;
    } catch {
      return false;
    }
  }
}

function formatTs(ts: string): string {
  // Keep it simple: show HH:MM:SS if ISO-like, else raw
  const d = new Date(ts);
  if (!Number.isNaN(d.getTime())) {
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  return ts;
}

function extractFirstHttpUrl(text: string): string | null {
  const m = text.match(/https?:\/\/[^\s]+/i);
  return m ? m[0] : null;
}

function safeHost(urlStr: string): string | null {
  try {
    return new URL(urlStr).host.toLowerCase();
  } catch {
    return null;
  }
}

export default function Home() {
  const apiBase = useMemo(() => getApiBase(), []);

  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [runId, setRunId] = useState<number | null>(null);

  const [createResult, setCreateResult] =
    useState<UiResult<ApiOkResponse> | null>(null);
  const [stepResult, setStepResult] =
    useState<UiResult<ExecuteStepOkResponse> | null>(null);
  const [runDetails, setRunDetails] =
    useState<UiResult<RunDetailsOkResponse> | null>(null);

  const [autoRefresh, setAutoRefresh] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [showScrollTop, setShowScrollTop] = useState(false);

  // Read the demo starting URL from backend health (falls back to the known demo site)
  const [demoUrl, setDemoUrl] = useState<string>(
    "https://the-internet.herokuapp.com/",
  );

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const res = await fetch(`${apiBase}/health`, { cache: "no-store" });
        if (!res.ok) return;

        const data = await safeReadJson(res);

        // Try a few common shapes without breaking if the backend changes slightly.
        const u =
          (isRecord(data) &&
            typeof data.demo_starting_url === "string" &&
            data.demo_starting_url) ||
          (isRecord(data) &&
            typeof data.demoStartingUrl === "string" &&
            data.demoStartingUrl) ||
          (isRecord(data) &&
            isRecord(data.settings) &&
            typeof data.settings.DEMO_STARTING_URL === "string" &&
            data.settings.DEMO_STARTING_URL) ||
          null;

        if (!cancelled && typeof u === "string" && u.startsWith("http")) {
          setDemoUrl(u);
        }
      } catch {
        // Keep fallback demoUrl
      }
    }

    loadHealth();
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  useEffect(() => {
    let ticking = false;

    const onScroll = () => {
      if (ticking) return;
      ticking = true;

      window.requestAnimationFrame(() => {
        setShowScrollTop(window.scrollY > 320);
        ticking = false;
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll(); // initialize

    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Demo-safe examples: they must target the configured demo site.
  const examples = useMemo(
    () => [
      {
        label: "Login + screenshot",
        value:
          "Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot.",
      },
      {
        label: "Navigate + verify",
        value:
          "Go to A/B Testing, verify the page contains the text 'A/B Test', then take a screenshot.",
      },
      {
        label: "Fill form",
        value:
          "Go to Form Authentication, fill the username and password fields, verify the Login button is visible, then take a screenshot.",
      },
    ],
    [],
  );

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 1800);
  }

  async function createRun() {
    setLoading(true);
    setCreateResult(null);
    setStepResult(null);
    setRunDetails(null);

    try {
      const res = await fetch(`${apiBase}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task, top_k: 4 }),
      });

      const data = await safeReadJson(res);

      if (!res.ok) {
        setCreateResult({ error: toErrorMessage(data, res.status) });
        return;
      }

      if (!isApiOkResponse(data)) {
        setCreateResult({
          error: "Invalid API response (missing expected fields).",
        });
        return;
      }

      setRunId(data.run_id);
      setCreateResult(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setCreateResult({ error: message });
    } finally {
      setLoading(false);
    }
  }

  async function refreshRun(opts?: { silent?: boolean }) {
    if (!runId) return;

    if (opts?.silent) setRefreshing(true);
    else {
      setLoading(true);
      setRunDetails(null);
    }

    try {
      const res = await fetch(`${apiBase}/runs/${runId}`, { method: "GET" });
      const data = await safeReadJson(res);

      if (!res.ok) {
        setRunDetails({ error: toErrorMessage(data, res.status) });
        return;
      }

      if (!isRunDetailsOkResponse(data)) {
        setRunDetails({
          error: "Invalid API response when reading run details.",
        });
        return;
      }

      setRunDetails(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setRunDetails({ error: message });
    } finally {
      if (opts?.silent) setRefreshing(false);
      else setLoading(false);
    }
  }

  async function executeNextStep() {
    if (!runId) return;

    setLoading(true);
    setStepResult(null);

    try {
      const res = await fetch(`${apiBase}/runs/${runId}/execute-next-ui-step`, {
        method: "POST",
      });
      const data = await safeReadJson(res);

      if (!res.ok) {
        setStepResult({ error: toErrorMessage(data, res.status) });
        return;
      }

      if (!isExecuteStepOkResponse(data)) {
        setStepResult({
          error: "Invalid API response when executing the next step.",
        });
        return;
      }

      setStepResult(data);
      await refreshRun({ silent: true });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setStepResult({ error: message });
    } finally {
      setLoading(false);
    }
  }

  async function closeUiSession() {
    if (!runId) return;

    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/runs/${runId}/close-ui-session`, {
        method: "POST",
      });
      const data = await safeReadJson(res);

      if (!res.ok) {
        setStepResult({ error: toErrorMessage(data, res.status) });
        return;
      }

      await refreshRun({ silent: true });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setStepResult({ error: message });
    } finally {
      setLoading(false);
    }
  }

  function resetRun() {
    setRunId(null);
    setCreateResult(null);
    setStepResult(null);
    setRunDetails(null);
    setAutoRefresh(false);
  }

  // Auto-refresh polling (silent)
  useEffect(() => {
    if (!autoRefresh || !runId) return;

    const id = window.setInterval(() => {
      refreshRun({ silent: true }).catch(() => {
        // Ignore polling errors
      });
    }, 2000);

    return () => window.clearInterval(id);
  }, [autoRefresh, runId]); // eslint-disable-line react-hooks/exhaustive-deps

  const screenshotLinks = useMemo(() => {
    if (!runDetails || "error" in runDetails) return [];

    const urls: string[] = [];
    for (const l of runDetails.logs) {
      if (l.message !== "UI step executed") continue;
      const url = getScreenshotUrlFromLogData(l.data);
      if (url) urls.push(url);
    }
    return urls;
  }, [runDetails]);

  const latestScreenshotPath =
    screenshotLinks.length > 0
      ? screenshotLinks[screenshotLinks.length - 1]
      : null;

  const latestScreenshotUrl = latestScreenshotPath
    ? `${apiBase}${latestScreenshotPath}`
    : null;

  const canCreate = task.trim().length > 0 && !loading;
  const canRunActions = !!runId && !loading;

  const statusText = useMemo(() => {
    if (!runId) return "No run";
    if (runDetails && !("error" in runDetails))
      return runDetails.run.status || "Unknown";
    if (stepResult && !("error" in stepResult))
      return stepResult.status || "Unknown";
    return loading ? "Working..." : "Unknown";
  }, [runId, runDetails, stepResult, loading]);

  const humanLogs = useMemo(() => {
    if (!runDetails || "error" in runDetails) return [];
    // Show newest first, keep it readable
    return [...runDetails.logs].reverse();
  }, [runDetails]);

  // URL warning logic: if user mentions a URL that is NOT the configured demo host, warn them.
  const typedUrl = useMemo(() => extractFirstHttpUrl(task), [task]);
  const typedHost = useMemo(
    () => (typedUrl ? safeHost(typedUrl) : null),
    [typedUrl],
  );
  const demoHost = useMemo(() => safeHost(demoUrl), [demoUrl]);

  const showUrlWarning = useMemo(() => {
    if (!typedHost || !demoHost) return false;
    return typedHost !== demoHost;
  }, [typedHost, demoHost]);

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-10 py-8 sm:py-10 flex justify-center">
      <div className="w-full max-w-7xl space-y-6">
        {/* Header (reduced height, same colors) */}
        <header className="card-glass px-4 sm:px-6 py-4">
          <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr_auto] items-center gap-4">
            {/* Left: logo */}
            <div className="flex items-center">
              <Image
                src="/novaflowops-logo-1400x400.png"
                alt="NovaFlow Ops"
                width={1600}
                height={457}
                priority
                className="w-auto h-30 sm:h-25 md:h-40 opacity-95"
              />
            </div>

            {/* Center: subtitle */}
            <div className="text-center px-2">
              <p className="text-sm sm:text-base md:text-lg muted leading-relaxed mx-auto max-w-[80ch] font-bold">
                Turn natural language tasks into verified browser actions
              </p>
              <p className="text-sm sm:text-base md:text-lg muted leading-relaxed mx-auto max-w-[80ch] font-bold">
                (Nova 2 Lite + Titan Embeddings + Playwright).
              </p>
            </div>
          </div>
        </header>

        {/* Two-column layout on desktop */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0">
          {/* Left: Task + actions */}
          <section className="card-glass min-w-0">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <div className="text-sm font-semibold">Task</div>
                <div className="text-xs muted mt-1">
                  Use an example or write your own natural language instruction.
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  className="btn3d btn3d-ghost text-xs px-3 py-2"
                  type="button"
                  onClick={() => setTask("")}
                  disabled={loading}
                >
                  Clear
                </button>

                <button
                  className="btn3d btn3d-ghost text-xs px-3 py-2"
                  type="button"
                  onClick={() => {
                    resetRun();
                    showToast("Run reset");
                  }}
                  disabled={loading}
                >
                  New run
                </button>
              </div>
            </div>

            {/* Examples */}
            <div className="mt-4 flex gap-2 flex-wrap">
              {examples.map((ex) => (
                <button
                  key={ex.label}
                  className="btn3d btn3d-ghost text-xs px-3 py-2"
                  type="button"
                  onClick={() => setTask(ex.value)}
                  disabled={loading}
                >
                  {ex.label}
                </button>
              ))}
            </div>

            <textarea
              className="input-pro mt-4"
              rows={8}
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder='Example: "Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot."'
            />

            <p className="mt-2 text-xs text-slate-500">
              Note: For demo stability, runs start from{" "}
              <code className="px-1 py-0.5 rounded bg-slate-800/30">
                DEMO_STARTING_URL
              </code>
              . Use tasks that target the configured demo site.
            </p>

            {showUrlWarning && (
              <div className="mt-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                This demo runs against{" "}
                <code className="px-1 py-0.5 rounded bg-black/30">
                  {demoUrl}
                </code>
                . Your task mentions{" "}
                <code className="px-1 py-0.5 rounded bg-black/30">
                  {typedUrl}
                </code>
                , which may be ignored by the runner.
              </div>
            )}

            <div className="mt-4 flex gap-3 flex-wrap items-center">
              <button
                onClick={createRun}
                disabled={!canCreate}
                className="btn3d btn3d-ghost"
              >
                {loading ? "Working..." : "Create run"}
              </button>

              <button
                onClick={executeNextStep}
                disabled={!canRunActions}
                className="btn3d btn3d-primary"
              >
                Execute next UI step
              </button>

              <button
                onClick={() => refreshRun()}
                disabled={!runId || loading}
                className="btn3d btn3d-ghost"
              >
                Refresh logs
              </button>

              <button
                onClick={closeUiSession}
                disabled={!canRunActions}
                className="btn3d btn3d-danger"
              >
                Close UI session
              </button>
            </div>

            {/* Debug JSON */}
            {(createResult || stepResult) && (
              <div className="mt-6 grid gap-4">
                {createResult && (
                  <div>
                    <h2 className="text-sm font-semibold mb-2">
                      Create run response
                    </h2>
                    <pre className="text-xs bg-black/10 p-3 rounded-md overflow-auto max-w-full whitespace-pre-wrap break-word">
                      {safeStringify(createResult)}
                    </pre>
                  </div>
                )}

                {stepResult && (
                  <div>
                    <h2 className="text-sm font-semibold mb-2">
                      Last step result
                    </h2>
                    <pre className="text-xs bg-black/10 p-3 rounded-md overflow-auto max-w-full whitespace-pre-wrap break-word">
                      {safeStringify(stepResult)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Right: Status + artifacts + logs */}
          <div className="space-y-6 min-w-0">
            {/* Status card */}
            <section className="card-glass">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">Run status</div>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="muted" aria-hidden="true">
                      ●
                    </span>
                    <span className="text-sm">{statusText}</span>
                    {refreshing && (
                      <span className="text-xs muted">(refreshing)</span>
                    )}
                  </div>

                  {runId && (
                    <div className="mt-2 text-xs muted">
                      Run ID: <span className="font-mono">{runId}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <button
                    className="btn3d btn3d-ghost text-xs px-3 py-2"
                    type="button"
                    onClick={async () => {
                      if (!runId) return;
                      const ok = await copyToClipboard(String(runId));
                      showToast(ok ? "Run ID copied" : "Copy failed");
                    }}
                    disabled={!runId}
                  >
                    Copy Run ID
                  </button>

                  <button
                    className="btn3d btn3d-ghost text-xs px-3 py-2"
                    type="button"
                    onClick={() => setAutoRefresh((v) => !v)}
                    disabled={!runId}
                  >
                    {autoRefresh ? "Auto-refresh: ON" : "Auto-refresh: OFF"}
                  </button>
                </div>
              </div>
            </section>

            {/* Artifacts card */}
            <section className="card-glass">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">Artifacts</div>
                  <div className="text-xs muted mt-1">
                    Screenshots will appear here when available.
                  </div>
                </div>
              </div>

              <div className="mt-4">
                {latestScreenshotUrl ? (
                  <div className="artifacts">
                    <div className="thumb">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={latestScreenshotUrl} alt="Latest screenshot" />
                      <div>
                        <div className="font-semibold">Latest screenshot</div>
                        <div className="text-xs muted">
                          {runId ? `screenshot-${runId}.png` : "screenshot.png"}
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-3 flex-wrap">
                      <button
                        className="btn3d btn3d-ghost"
                        onClick={() =>
                          window.open(
                            latestScreenshotUrl,
                            "_blank",
                            "noopener,noreferrer",
                          )
                        }
                        type="button"
                      >
                        Open
                      </button>

                      <button
                        className="btn3d btn3d-primary"
                        onClick={async () => {
                          const name = runId
                            ? `screenshot-${runId}.png`
                            : "screenshot.png";
                          await downloadViaBlob(latestScreenshotUrl, name);
                        }}
                        type="button"
                      >
                        Download
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm muted">
                    No screenshots yet. Execute UI steps and a preview will show
                    up here.
                  </div>
                )}
              </div>
            </section>

            {/* Logs card */}
            <section className="card-glass">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">Logs</div>
                  <div className="text-xs muted mt-1">
                    Readable timeline (newest first).
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <button
                    className="btn3d btn3d-ghost text-xs px-3 py-2"
                    type="button"
                    onClick={() => refreshRun({ silent: true })}
                    disabled={!runId}
                  >
                    Refresh
                  </button>
                </div>
              </div>

              <div className="mt-4">
                {!runId ? (
                  <div className="text-sm muted">Create a run to see logs.</div>
                ) : runDetails && "error" in runDetails ? (
                  <div className="text-sm">
                    <div className="font-semibold">Error</div>
                    <div className="muted mt-1">{runDetails.error}</div>
                  </div>
                ) : runDetails && !("error" in runDetails) ? (
                  <div className="rounded-md bg-black/10 p-3 max-h-90 overflow-auto">
                    {humanLogs.length === 0 ? (
                      <div className="text-sm muted">No logs yet.</div>
                    ) : (
                      <ul className="space-y-2">
                        {humanLogs.slice(0, 120).map((l, idx) => (
                          <li key={`${l.ts}-${idx}`} className="text-xs">
                            <div className="flex gap-2">
                              <span className="muted w-19.5 shrink-0">
                                {formatTs(l.ts)}
                              </span>
                              <span className="muted w-13.5 shrink-0">
                                {l.level.toUpperCase()}
                              </span>
                              <span className="flex-1">{l.message}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <div className="text-sm muted">Waiting for run details…</div>
                )}
              </div>

              {/* Raw run details */}
              {runDetails && (
                <div className="mt-4">
                  <details>
                    <summary className="text-xs muted cursor-pointer">
                      Show raw run details (JSON)
                    </summary>
                    <pre className="text-xs bg-black/10 p-3 rounded-md overflow-auto mt-2 break-word">
                      {safeStringify(runDetails)}
                    </pre>
                  </details>
                </div>
              )}
            </section>
          </div>
        </div>

        {/* Toast */}
        {toast && (
          <div className="fixed bottom-5 left-1/2 -translate-x-1/2">
            <div className="badge">{toast}</div>
          </div>
        )}

        {/* Scroll-to-top */}
        {showScrollTop && (
          <button
            type="button"
            className="btn3d btn3d-primary fixed bottom-6 right-6 z-50 rounded-full w-12 h-12 p-0 flex items-center justify-center"
            aria-label="Scroll to top"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                d="M12 5L5 12M12 5L19 12M12 5V21"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>
    </main>
  );
}
