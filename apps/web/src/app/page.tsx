"use client";

import { useState } from "react";

type TaskResponse = {
  runId?: string;
  task?: string;
  error?: string;
};

export default function Home() {
  const [task, setTask] = useState("");
  const [result, setResult] = useState<TaskResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function runTask() {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("http://localhost:8000/task", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
      });
      const data = await res.json();
      setResult(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setResult({ error: message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-6 flex justify-center">
      <div className="w-full max-w-2xl">
        <h1 className="text-3xl font-bold">NovaFlow Ops</h1>
        <p className="text-sm text-gray-600 mt-2">
          Turn natural-language tasks into verified browser actions (Nova 2 +
          Embeddings + Nova Act).
        </p>

        <label className="block text-sm font-medium mt-6">Task</label>
        <textarea
          className="w-full mt-2 border rounded-md p-3 focus:outline-none focus:ring-2"
          rows={6}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder='Example: "Reply to 3 reviews using our brand tone and log them as leads."'
        />

        <button
          onClick={runTask}
          disabled={!task.trim() || loading}
          className="mt-3 px-4 py-2 rounded-md bg-black text-white disabled:opacity-50"
        >
          {loading ? "Running..." : "Run"}
        </button>

        {result && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold mb-2">Result</h2>
            <pre className="text-xs bg-gray-100 p-3 rounded-md overflow-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </main>
  );
}
