"use client";

import { useMemo, useState } from "react";

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
    isRecord(v) &&
    typeof v.run_id === "number" &&
    "plan" in v &&
    "ctx" in v
  );
}

function isExecuteStepOkResponse(v: unknown): v is ExecuteStepOkResponse {
  return (
    isRecord(v) &&
    typeof v.run_id === "number" &&
    typeof v.status === "string" &&
    ("executed_step_id" in v)
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
    // backend devolvió texto/HTML en vez de JSON
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
  // data: { result: { screenshot_url: "/artifacts/..." } }
  if (!isRecord(data)) return null;
  const result = data.result;
  if (!isRecord(result)) return null;

  const url = result.screenshot_url;
  return typeof url === "string" ? url : null;
}

export default function Home() {
  const apiBase = useMemo(() => getApiBase(), []);

  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);

  const [runId, setRunId] = useState<number | null>(null);

  const [createResult, setCreateResult] = useState<UiResult<ApiOkResponse> | null>(null);
  const [stepResult, setStepResult] = useState<UiResult<ExecuteStepOkResponse> | null>(null);
  const [runDetails, setRunDetails] = useState<UiResult<RunDetailsOkResponse> | null>(null);

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
        setCreateResult({ error: "Respuesta inválida del API (faltan campos esperados)." });
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

  async function refreshRun() {
    if (!runId) return;

    setLoading(true);
    setRunDetails(null);

    try {
      const res = await fetch(`${apiBase}/runs/${runId}`, { method: "GET" });
      const data = await safeReadJson(res);

      if (!res.ok) {
        setRunDetails({ error: toErrorMessage(data, res.status) });
        return;
      }

      if (!isRunDetailsOkResponse(data)) {
        setRunDetails({ error: "Respuesta inválida del API al leer el run." });
        return;
      }

      setRunDetails(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setRunDetails({ error: message });
    } finally {
      setLoading(false);
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
        setStepResult({ error: "Respuesta inválida del API al ejecutar el step." });
        return;
      }

      setStepResult(data);
      // refresca logs automáticamente para que aparezca screenshot_url al momento
      await refreshRun();
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
      const res = await fetch(`${apiBase}/runs/${runId}/close-ui-session`, { method: "POST" });
      const data = await safeReadJson(res);

      if (!res.ok) {
        setStepResult({ error: toErrorMessage(data, res.status) });
        return;
      }

      // refresca estado por si acaso
      await refreshRun();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setStepResult({ error: message });
    } finally {
      setLoading(false);
    }
  }

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

  return (
    <main className="min-h-screen p-6 flex justify-center">
      <div className="w-full max-w-3xl">
        <h1 className="text-3xl font-bold">NovaFlow Ops</h1>
        <p className="text-sm text-gray-600 mt-2">
          Turn natural-language tasks into verified browser actions (Nova 2 + Embeddings + Playwright).
        </p>

        <p className="text-xs text-gray-500 mt-2">
          API: <span className="font-mono">{apiBase}</span>
        </p>

        <label className="block text-sm font-medium mt-6">Task</label>
        <textarea
          className="w-full mt-2 border rounded-md p-3 focus:outline-none focus:ring-2"
          rows={6}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder='Example: "Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot."'
        />

        <div className="mt-3 flex gap-2 flex-wrap">
          <button
            onClick={createRun}
            disabled={!task.trim() || loading}
            className="px-4 py-2 rounded-md bg-black text-white disabled:opacity-50"
          >
            {loading ? "Working..." : "Create run"}
          </button>

          <button
            onClick={executeNextStep}
            disabled={!runId || loading}
            className="px-4 py-2 rounded-md bg-indigo-600 text-white disabled:opacity-50"
          >
            Execute next UI step
          </button>

          <button
            onClick={refreshRun}
            disabled={!runId || loading}
            className="px-4 py-2 rounded-md bg-gray-200 text-gray-900 disabled:opacity-50"
          >
            Refresh logs
          </button>

          <button
            onClick={closeUiSession}
            disabled={!runId || loading}
            className="px-4 py-2 rounded-md bg-gray-200 text-gray-900 disabled:opacity-50"
          >
            Close UI session
          </button>

          {runId && (
            <span className="text-sm text-gray-700 self-center">
              Run: <strong>{runId}</strong>
            </span>
          )}
        </div>

        {screenshotLinks.length > 0 && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold mb-2">Screenshots</h2>
            <ul className="list-disc ml-5 text-sm">
              {screenshotLinks.map((u) => (
                <li key={u}>
                  <a
                    className="text-blue-600 underline"
                    href={`${apiBase}${u}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {apiBase}
                    {u}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {(createResult || stepResult || runDetails) && (
          <div className="mt-6 grid gap-4">
            {createResult && (
              <div>
                <h2 className="text-sm font-semibold mb-2">Create run response</h2>
                <pre className="text-xs bg-gray-100 p-3 rounded-md overflow-auto">
                  {safeStringify(createResult)}
                </pre>
              </div>
            )}

            {stepResult && (
              <div>
                <h2 className="text-sm font-semibold mb-2">Last step result</h2>
                <pre className="text-xs bg-gray-100 p-3 rounded-md overflow-auto">
                  {safeStringify(stepResult)}
                </pre>
              </div>
            )}

            {runDetails && (
              <div>
                <h2 className="text-sm font-semibold mb-2">Run details</h2>
                <pre className="text-xs bg-gray-100 p-3 rounded-md overflow-auto">
                  {safeStringify(runDetails)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
