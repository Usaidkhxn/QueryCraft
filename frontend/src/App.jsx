import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

const chartColors = [
  "#ffcc00",
  "#57150b",
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#7c3aed",
  "#0891b2",
  "#ea580c",
  "#4b5563",
  "#be185d",
  "#0f766e",
  "#9333ea",
  "#ca8a04",
  "#0369a1",
  "#b91c1c",
];

function friendlyLabel(value) {
  if (!value) return "";

  return String(value)
    .replace(/\.[^.]+$/, "")
    .replace(/raw_/gi, "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .replace(/\bGasb\b/g, "GASB")
    .replace(/\bSat\b/g, "SAT")
    .replace(/\bAct\b/g, "ACT")
    .replace(/\bIpeds\b/g, "IPEDS")
    .replace(/\bSql\b/g, "SQL")
    .replace(/\bNj\b/g, "NJ");
}

function stripMetricPrefix(value) {
  if (!value) return "";
  const text = String(value);
  if (text.includes("|")) return text.split("|").pop().trim();
  return text;
}

function extractMetricFromSql(sql) {
  if (!sql) return null;
  const match = sql.match(/metric_family\s*=\s*'([^']+)'/i);
  return match ? match[1] : null;
}

function extractMetricPathFromSql(sql) {
  if (!sql) return null;
  const match = sql.match(/metric_path\s*(?:=|LIKE)\s*'?%?([^'%]+)%?'?/i);
  return match ? match[1] : null;
}

function extractCategoryOneFromSql(sql) {
  if (!sql) return null;
  const match = sql.match(/category_1\s*=\s*'([^']+(?:''[^']+)*)'/i);
  return match ? match[1].replace(/''/g, "'") : null;
}

function extractYearFromSql(sql) {
  if (!sql) return null;
  const match = sql.match(/year_int\s*=\s*(\d{4})/i);
  return match ? match[1] : null;
}

function metricLabelFromMessage(msg) {
  const sql = msg.sql || "";
  const question = (msg.question || "").toLowerCase();
  const year = extractYearFromSql(sql);
  const metricFamily = extractMetricFromSql(sql);
  const metricPath = extractMetricPathFromSql(sql);
  const categoryOne = extractCategoryOneFromSql(sql);

  let label = "";

  if (metricFamily === "total_enrollment") {
    label = "Total Enrollment";
  } else if (metricFamily === "student_financial_aid") {
    label = metricPath ? friendlyLabel(metricPath) : "Student Financial Aid";
  } else if (metricFamily === "graduation_rate_bachelors_by_race_ethnicity") {
    label =
      question.includes("total completer") || categoryOne === "Total completers"
        ? "Total Completers"
        : "Graduation Rate";
  } else if (metricPath) {
    label = friendlyLabel(stripMetricPrefix(metricPath));
  } else if (metricFamily) {
    label = friendlyLabel(metricFamily);
  } else {
    label = "Value";
  }

  if (year) label += ` (${year})`;

  return label;
}

function columnLabel(col, msg) {
  const lower = String(col).toLowerCase();

  if (lower === "institution_name") return "Institution Name";
  if (lower === "unit_id") return "Unit ID";
  if (lower === "year_int") return "Year";
  if (lower === "year_label") return "Year";
  if (lower === "metric_family") return "Metric Family";
  if (lower === "metric_path") return "Metric";
  if (lower === "category_1") return "Measure";
  if (lower === "category_2") return "Race / Ethnicity";
  if (lower === "category_3") return "Group";
  if (lower === "race") return "Race / Ethnicity";
  if (lower === "race_ethnicity") return "Race / Ethnicity";
  if (lower === "admissions_measure") return "Admissions Measure";
  if (lower === "graduation_measure") return "Graduation Measure";
  if (lower === "value_numeric") return metricLabelFromMessage(msg);
  if (lower === "value_text") return metricLabelFromMessage(msg);

  return friendlyLabel(col);
}

function shouldShowAsPercent(msg) {
  const sql = (msg?.sql || "").toLowerCase();
  const question = (msg?.question || "").toLowerCase();

  return (
    sql.includes("graduation_rate_bachelors_by_race_ethnicity") ||
    question.includes("graduation rate") ||
    question.includes("percent") ||
    question.includes("percentage")
  );
}

function formatCell(value, col, msg) {
  if (value === null || value === undefined) return "";

  const lower = String(col).toLowerCase();

  if (lower === "year_int" || lower === "year_label") return String(value);

  if (
    lower === "metric_path" ||
    lower === "category_1" ||
    lower === "category_2" ||
    lower === "race" ||
    lower === "race_ethnicity" ||
    lower === "admissions_measure" ||
    lower === "graduation_measure"
  ) {
    return friendlyLabel(stripMetricPrefix(value));
  }

  const num = Number(value);

  if (!Number.isNaN(num) && String(value).trim() !== "") {
    if (shouldShowAsPercent(msg) && num >= 0 && num <= 1) {
      return `${(num * 100).toFixed(1)}%`;
    }

    return num.toLocaleString();
  }

  return String(value);
}

function formatTooltipValue(value, msg) {
  const num = Number(value);

  if (!Number.isNaN(num)) {
    if (shouldShowAsPercent(msg) && num >= 0 && num <= 1) {
      return `${(num * 100).toFixed(1)}%`;
    }

    return num.toLocaleString();
  }

  return String(value);
}

function CustomTooltip({ active, payload, label, msg }) {
  if (!active || !payload || payload.length === 0) return null;

  const item = payload[0];

  return (
    <div className="qc-custom-tooltip">
      <div className="qc-tooltip-label">{friendlyLabel(label)}</div>
      <div className="qc-tooltip-row">
        <span>{friendlyLabel(stripMetricPrefix(item.name || item.dataKey))}</span>
        <b>{formatTooltipValue(item.value, msg)}</b>
      </div>
    </div>
  );
}

function LeftLegend({ items }) {
  return (
    <div className="qc-left-legend">
      {items.map((item, index) => (
        <div key={`${item}-${index}`} className="qc-left-legend-item">
          <span
            className="qc-left-legend-color"
            style={{ background: chartColors[index % chartColors.length] }}
          ></span>
          <span>{friendlyLabel(stripMetricPrefix(item))}</span>
        </div>
      ))}
    </div>
  );
}

function makeSessionTitle(text) {
  if (!text) return "New chat";
  return text.length > 35 ? text.slice(0, 35) + "..." : text;
}

function createNewSession() {
  return {
    id: crypto.randomUUID(),
    title: "New chat",
    createdAt: new Date().toISOString(),
    messages: [
      {
        role: "assistant",
        reply:
          "Hi, I’m QueryCraft. Upload an Excel file, upload a ZIP of Excel files, or ingest a local folder. Then ask questions like: “Show total enrollment for all institutions in 2024.”",
      },
    ],
  };
}

function getInitialAppState() {
  let initialSessions;

  try {
    const savedSessions = localStorage.getItem("querycraft_sessions");
    initialSessions = savedSessions
      ? JSON.parse(savedSessions)
      : [createNewSession()];
  } catch {
    initialSessions = [createNewSession()];
  }

  const savedActiveId = localStorage.getItem("querycraft_active_session");

  const validActiveId = initialSessions.some(
    (session) => session.id === savedActiveId
  )
    ? savedActiveId
    : initialSessions[0].id;

  return {
    initialSessions,
    initialActiveSessionId: validActiveId,
  };
}

function detectRequestedChart(question = "") {
  const q = question.toLowerCase();

  if (q.includes("heatmap") || q.includes("heat map")) return "heatmap";
  if (q.includes("donut") || q.includes("doughnut")) return "donut";
  if (q.includes("pie")) return "pie";
  if (q.includes("grouped") || q.includes("compare") || q.includes("comparison")) {
    return "grouped";
  }
  if (q.includes("line") || q.includes("trend") || q.includes("over time")) {
    return "line";
  }
  if (q.includes("bar") || q.includes("rank") || q.includes("highest")) {
    return "bar";
  }

  return "auto";
}

function getNumericColumn(rows) {
  if (!rows || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);

  if (columns.includes("value_numeric")) return "value_numeric";

  return columns.find((col) => {
    if (String(col).toLowerCase().includes("year")) return false;

    return rows.some((row) => {
      const value = Number(row[col]);
      return row[col] !== null && row[col] !== "" && !Number.isNaN(value);
    });
  });
}

function getYearColumn(rows) {
  if (!rows || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);

  if (columns.includes("year_int")) return "year_int";
  if (columns.includes("year_label")) return "year_label";

  return columns.find((col) => String(col).toLowerCase().includes("year"));
}

function getCategoryColumn(rows) {
  if (!rows || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);

  const preferred = [
    "race_ethnicity",
    "race",
    "institution_name",
    "admissions_measure",
    "graduation_measure",
    "metric_path",
    "category_2",
    "category_1",
    "category_3",
    "metric_family",
    "source_file",
  ];

  for (const col of preferred) {
    if (columns.includes(col)) return col;
  }

  return columns.find((col) => typeof rows[0][col] === "string") || columns[0];
}

function getSeriesColumn(rows, yearCol, numericCol) {
  if (!rows || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);

  const candidates = [
    "institution_name",
    "race_ethnicity",
    "race",
    "admissions_measure",
    "graduation_measure",
    "metric_path",
    "category_2",
    "category_1",
    "category_3",
  ].filter((col) => columns.includes(col) && col !== yearCol && col !== numericCol);

  return candidates[0] || null;
}

function dedupeRows(rows, keyColumns) {
  const seen = new Set();

  return rows.filter((row) => {
    const key = keyColumns.map((col) => String(row[col] ?? "")).join("||");

    if (seen.has(key)) return false;

    seen.add(key);
    return true;
  });
}

function isMultiYearInstitutionTrend(rows) {
  if (!rows || rows.length === 0) return false;

  const columns = Object.keys(rows[0]);

  if (
    !columns.includes("institution_name") ||
    !columns.includes("year_int") ||
    !columns.includes("value_numeric")
  ) {
    return false;
  }

  const years = new Set(rows.map((row) => row.year_int).filter(Boolean));
  const institutions = new Set(rows.map((row) => row.institution_name).filter(Boolean));

  return years.size > 1 && institutions.size > 1;
}

function pivotTrendRows(rows, msg) {
  const cleanRows = dedupeRows(rows, [
    "institution_name",
    "year_int",
    "value_numeric",
  ]).filter(
    (row) =>
      row.institution_name &&
      row.year_int !== null &&
      row.year_int !== undefined &&
      row.value_numeric !== null &&
      row.value_numeric !== undefined
  );

  const years = Array.from(new Set(cleanRows.map((row) => row.year_int))).sort(
    (a, b) => Number(a) - Number(b)
  );

  const institutions = Array.from(
    new Set(cleanRows.map((row) => row.institution_name))
  ).sort((a, b) => String(a).localeCompare(String(b)));

  const rowsByInstitution = institutions.map((institution) => {
    const output = {
      institution_name: institution,
    };

    years.forEach((year) => {
      const found = cleanRows.find(
        (row) => row.institution_name === institution && row.year_int === year
      );

      output[String(year)] = found ? found.value_numeric : null;
    });

    return output;
  });

  return {
    years,
    rowsByInstitution,
    metricName: metricLabelFromMessage(msg),
  };
}

function pivotRows(rows, xCol, seriesCol, valueCol) {
  const cleanRows = dedupeRows(rows, [xCol, seriesCol, valueCol]);

  const resultMap = new Map();

  const seriesValues = Array.from(
    new Set(cleanRows.map((row) => row[seriesCol]).filter(Boolean))
  ).slice(0, 15);

  cleanRows.forEach((row) => {
    const x = row[xCol];
    const series = row[seriesCol];

    if (!seriesValues.includes(series)) return;

    if (!resultMap.has(x)) {
      resultMap.set(x, { [xCol]: x });
    }

    resultMap.get(x)[series] = Number(row[valueCol]) || 0;
  });

  const result = Array.from(resultMap.values());

  result.sort((a, b) => {
    const aValue = Number(a[xCol]);
    const bValue = Number(b[xCol]);

    if (!Number.isNaN(aValue) && !Number.isNaN(bValue)) return aValue - bValue;

    return String(a[xCol]).localeCompare(String(b[xCol]));
  });

  return { result, seriesValues };
}

function App() {
  const initialState = useMemo(() => getInitialAppState(), []);

  const [sessions, setSessions] = useState(initialState.initialSessions);
  const [activeSessionId, setActiveSessionId] = useState(
    initialState.initialActiveSessionId
  );

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressSteps, setProgressSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState("");

  const [folderPath, setFolderPath] = useState(
    "E:\\Desktop\\querycraft\\NJ Schools"
  );
  const [summary, setSummary] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");

  const chatEndRef = useRef(null);

  const activeSession = useMemo(() => {
    if (!sessions.length) return null;

    return (
      sessions.find((session) => session.id === activeSessionId) || sessions[0]
    );
  }, [sessions, activeSessionId]);

  useEffect(() => {
    localStorage.setItem("querycraft_sessions", JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem("querycraft_active_session", activeSessionId);
    }
  }, [activeSessionId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [sessions, loading, progressSteps]);

  const updateActiveSessionMessages = (newMessages) => {
    if (!activeSession) return;

    setSessions((prev) =>
      prev.map((session) =>
        session.id === activeSession.id
          ? {
              ...session,
              title:
                session.title === "New chat"
                  ? makeSessionTitle(
                      newMessages.find((m) => m.role === "user")?.content
                    )
                  : session.title,
              messages: newMessages,
            }
          : session
      )
    );
  };

  const startNewChat = () => {
    const session = createNewSession();
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessage("");
    setUploadStatus("");
    setProgressSteps([]);
    setCurrentStep("");
  };

  const deleteSession = (id) => {
    const remaining = sessions.filter((session) => session.id !== id);

    if (remaining.length === 0) {
      const fresh = createNewSession();
      setSessions([fresh]);
      setActiveSessionId(fresh.id);
      return;
    }

    setSessions(remaining);

    if (activeSessionId === id) {
      setActiveSessionId(remaining[0].id);
    }
  };

  const sendMessage = async () => {
    if (!message.trim() || loading || !activeSession) return;

    const userMessage = {
      role: "user",
      content: message.trim(),
    };

    const updatedMessages = [...activeSession.messages, userMessage];

    updateActiveSessionMessages(updatedMessages);
    setMessage("");
    setLoading(true);
    setProgressSteps([]);
    setCurrentStep("Submitting question");

    const localSteps = [];

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ message: userMessage.content }),
      });

      if (!res.body) throw new Error("Streaming response not supported by browser.");

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part
            .split("\n")
            .find((item) => item.startsWith("data: "));

          if (!line) continue;

          const payload = JSON.parse(line.replace("data: ", ""));

          if (payload.type === "step") {
            const stepItem = {
              step: payload.step,
              message: payload.message,
              sql: payload.sql,
            };

            localSteps.push(stepItem);
            setCurrentStep(payload.step);
            setProgressSteps([...localSteps]);
          }

          if (payload.type === "final") {
            const data = payload.data;

            const assistantMessage = {
              role: "assistant",
              question: userMessage.content,
              reply: data.reply || "Done.",
              mode: data.mode,
              sql: data.sql,
              results: data.results,
              evidence: data.evidence,
              error: data.error,
              steps: localSteps,
            };

            updateActiveSessionMessages([...updatedMessages, assistantMessage]);
          }
        }
      }
    } catch (error) {
      updateActiveSessionMessages([
        ...updatedMessages,
        {
          role: "assistant",
          reply: "I could not connect to the backend.",
          error: String(error),
        },
      ]);
    } finally {
      setLoading(false);
      setCurrentStep("");
      setProgressSteps([]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const uploadFile = async (file, endpoint) => {
    if (!file) return;

    setUploadStatus(`Uploading ${file.name}...`);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      setUploadStatus(data.message || "Upload complete.");
      await loadSummary();
    } catch (error) {
      setUploadStatus(`Upload failed: ${String(error)}`);
    }
  };

  const ingestFolder = async () => {
    if (!folderPath.trim()) return;

    setUploadStatus("Ingesting local folder...");

    try {
      const res = await fetch(`${API_BASE}/ingest/folder`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ folder_path: folderPath }),
      });

      const data = await res.json();

      setUploadStatus(data.message || "Folder ingested.");
      await loadSummary();
    } catch (error) {
      setUploadStatus(`Folder ingest failed: ${String(error)}`);
    }
  };

  const loadSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/ingestion/summary`);
      const data = await res.json();
      setSummary(data);
    } catch (error) {
      setUploadStatus(`Could not load summary: ${String(error)}`);
    }
  };

  const clearLocalChats = () => {
    const fresh = createNewSession();

    setSessions([fresh]);
    setActiveSessionId(fresh.id);

    localStorage.removeItem("querycraft_sessions");
    localStorage.removeItem("querycraft_active_session");
  };

  return (
    <div className="qc-app">
      <aside className="qc-sidebar">
        <div className="qc-brand">
          <div className="qc-logo">Q</div>
          <div className="qc-brand-text">
            <h2>QueryCraft</h2>
            <p>Verified Analytics Copilot</p>
          </div>
        </div>

        <button className="qc-new-chat" onClick={startNewChat}>
          + New chat
        </button>

        <div className="qc-upload-panel">
          <h3>Data Upload</h3>

          <label className="qc-upload-btn">
            Upload Excel
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => uploadFile(e.target.files[0], "/upload/excel")}
            />
          </label>

          <label className="qc-upload-btn">
            Upload ZIP
            <input
              type="file"
              accept=".zip"
              onChange={(e) => uploadFile(e.target.files[0], "/upload/zip")}
            />
          </label>

          <div className="qc-folder-box">
            <input
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder="Local folder path"
            />
            <button onClick={ingestFolder}>Ingest Folder</button>
          </div>

          <button className="qc-summary-btn" onClick={loadSummary}>
            Refresh Dataset Summary
          </button>

          {uploadStatus && <p className="qc-status">{uploadStatus}</p>}
        </div>

        {summary && (
          <div className="qc-summary-card">
            <h3>Dataset Summary</h3>

            <div className="qc-summary-grid">
              <div>
                <span>Metric Rows</span>
                <b>{Number(summary.metric_rows || 0).toLocaleString()}</b>
              </div>
              <div>
                <span>Files / Sheets</span>
                <b>{summary.files?.length || 0}</b>
              </div>
            </div>

            <div className="qc-family-list">
              {summary.metric_families?.slice(0, 10).map((family) => (
                <div key={family.metric_family} className="qc-family-item">
                  <span title={friendlyLabel(family.metric_family)}>
                    {friendlyLabel(family.metric_family)}
                  </span>
                  <b>{Number(family.rows).toLocaleString()}</b>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="qc-history">
          <h3>Chat History</h3>

          {sessions.map((session) => (
            <div
              key={session.id}
              className={
                session.id === activeSession?.id
                  ? "qc-history-item active"
                  : "qc-history-item"
              }
            >
              <button
                title={session.title}
                onClick={() => setActiveSessionId(session.id)}
              >
                {session.title}
              </button>

              <span onClick={() => deleteSession(session.id)}>×</span>
            </div>
          ))}
        </div>

        <button className="qc-clear-btn" onClick={clearLocalChats}>
          Clear local chats
        </button>
      </aside>

      <main className="qc-main">
        <header className="qc-header">
          <div>
            <h1>Talk to your data</h1>
            <p>
              Upload Excel or ZIP files, then ask questions across metrics,
              years, institutions, categories, and trends.
            </p>
          </div>

          <div className="qc-pill">Local • Free • SQLite • Ollama</div>
        </header>

        <section className="qc-chat-window">
          {activeSession?.messages.map((msg, index) => (
            <MessageBubble key={index} msg={msg} />
          ))}

          {loading && (
            <div className="qc-message-row assistant">
              <div className="qc-message assistant-msg qc-progress-card">
                <div className="qc-role">QueryCraft</div>

                <div className="qc-current-step">
                  <span className="qc-dot"></span>
                  {currentStep}
                </div>

                <div className="qc-step-list">
                  {progressSteps.map((item, index) => (
                    <div key={`${item.step}-${index}`} className="qc-step-done">
                      <span>✓</span>
                      <div>
                        <b>{item.step}</b>
                        <p>{item.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef}></div>
        </section>

        <footer className="qc-composer">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='Ask: "Show total enrollment for all institutions in 2024"'
          />

          <button onClick={sendMessage} disabled={loading}>
            {loading ? "Working..." : "Send"}
          </button>
        </footer>
      </main>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`qc-message-row ${isUser ? "user" : "assistant"}`}>
      <div className={`qc-message ${isUser ? "user-msg" : "assistant-msg"}`}>
        <div className="qc-role">{isUser ? "You" : "QueryCraft"}</div>

        {isUser && <p>{msg.content}</p>}

        {!isUser && (
          <>
            <p>{msg.reply}</p>

            {msg.mode && (
              <span className="qc-mode">{friendlyLabel(msg.mode)}</span>
            )}

            {msg.sql && (
              <div className="qc-sql-card">
                <div className="qc-card-title">Generated SQL</div>
                <pre>{msg.sql}</pre>
              </div>
            )}

            {msg.results && msg.results.length > 0 && (
              <>
                <ResultsTable rows={msg.results} msg={msg} />
                <SmartChart rows={msg.results} msg={msg} />
              </>
            )}

            {msg.results && msg.results.length === 0 && (
              <div className="qc-empty">No rows returned.</div>
            )}

            {msg.error && <div className="qc-error">Error: {msg.error}</div>}

            {msg.evidence && msg.evidence.length > 0 && (
              <details className="qc-evidence">
                <summary>Evidence / schema used</summary>
                <pre>{msg.evidence[0]}</pre>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ResultsTable({ rows, msg }) {
  if (isMultiYearInstitutionTrend(rows)) {
    return <PivotTrendTable rows={rows} msg={msg} />;
  }

  const cleanRows = dedupeRows(rows, Object.keys(rows[0] || {}));
  const columns = Object.keys(cleanRows[0] || {});

  return (
    <div className="qc-table-wrap">
      <div className="qc-card-title">Results</div>

      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{columnLabel(col, msg)}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {cleanRows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col}>{formatCell(row[col], col, msg)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PivotTrendTable({ rows, msg }) {
  const { years, rowsByInstitution, metricName } = pivotTrendRows(rows, msg);

  return (
    <div className="qc-table-wrap">
      <div className="qc-card-title">Trend Results — {metricName}</div>

      <table>
        <thead>
          <tr>
            <th>Institution Name</th>
            {years.map((year) => (
              <th key={year}>{year}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rowsByInstitution.map((row) => (
            <tr key={row.institution_name}>
              <td>{row.institution_name}</td>
              {years.map((year) => (
                <td key={year}>
                  {row[String(year)] === null || row[String(year)] === undefined
                    ? ""
                    : formatCell(row[String(year)], "value_numeric", msg)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SmartChart({ rows, msg }) {
  if (!rows || rows.length === 0) return null;

  const question = msg.question || "";
  const requestedChart = detectRequestedChart(question);

  const numericCol = getNumericColumn(rows);
  const yearCol = getYearColumn(rows);
  const categoryCol = getCategoryColumn(rows);
  const seriesCol = getSeriesColumn(rows, yearCol, numericCol);

  if (!numericCol) return null;

  const hasYear = Boolean(yearCol);
  const hasCategory = Boolean(categoryCol);
  const hasSeries = Boolean(seriesCol);

  let chartType = requestedChart;

  if (chartType === "auto") {
    if (hasYear && hasSeries) chartType = "line";
    else if (hasYear) chartType = "line";
    else if (hasCategory) chartType = "bar";
    else chartType = "bar";
  }

  if ((chartType === "pie" || chartType === "donut") && hasCategory) {
    return (
      <PieDonutChart
        rows={rows}
        msg={msg}
        categoryCol={categoryCol}
        numericCol={numericCol}
        donut={chartType === "donut"}
      />
    );
  }

  if (chartType === "heatmap" && hasYear && hasCategory) {
    return (
      <HeatmapChart
        rows={rows}
        msg={msg}
        categoryCol={categoryCol}
        yearCol={yearCol}
        numericCol={numericCol}
      />
    );
  }

  if (chartType === "line" && hasYear && hasSeries) {
    return (
      <MultiLineTrendChart
        rows={rows}
        msg={msg}
        yearCol={yearCol}
        seriesCol={seriesCol}
        numericCol={numericCol}
      />
    );
  }

  if (chartType === "grouped" && hasYear && hasSeries) {
    return (
      <GroupedBarChart
        rows={rows}
        yearCol={yearCol}
        seriesCol={seriesCol}
        numericCol={numericCol}
      />
    );
  }

  if (chartType === "line" && hasYear) {
    return (
      <LineTrendChart
        rows={rows}
        msg={msg}
        yearCol={yearCol}
        numericCol={numericCol}
      />
    );
  }

  if (hasCategory) {
    return (
      <BasicBarChart
        rows={rows}
        msg={msg}
        categoryCol={categoryCol}
        numericCol={numericCol}
      />
    );
  }

  return null;
}

function BasicBarChart({ rows, msg, categoryCol, numericCol }) {
  const chartData = dedupeRows(rows, [categoryCol, numericCol])
    .filter((row) => row[categoryCol] && row[numericCol] !== null)
    .slice(0, 20)
    .map((row) => ({
      label: friendlyLabel(stripMetricPrefix(row[categoryCol])),
      value: Number(row[numericCol]) || 0,
    }));

  if (chartData.length === 0) return null;

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">{metricLabelFromMessage(msg)}</div>

      <div className="qc-chart-layout">
        <LeftLegend items={[metricLabelFromMessage(msg)]} />

        <div className="qc-chart-canvas">
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 35 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis
                type="category"
                dataKey="label"
                width={190}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                shared={false}
                cursor={{ fill: "rgba(255, 204, 0, 0.12)" }}
                content={<CustomTooltip msg={msg} />}
              />
              <Bar dataKey="value" name={metricLabelFromMessage(msg)}>
                {chartData.map((_, index) => (
                  <Cell
                    key={index}
                    fill={chartColors[index % chartColors.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function LineTrendChart({ rows, msg, yearCol, numericCol }) {
  const chartData = dedupeRows(rows, [yearCol, numericCol])
    .filter((row) => row[yearCol] !== null && row[numericCol] !== null)
    .map((row) => ({
      year: String(row[yearCol]),
      value: Number(row[numericCol]) || 0,
    }))
    .sort((a, b) => Number(a.year) - Number(b.year));

  if (chartData.length === 0) return null;

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">{metricLabelFromMessage(msg)} Trend</div>

      <div className="qc-chart-layout">
        <LeftLegend items={[metricLabelFromMessage(msg)]} />

        <div className="qc-chart-canvas">
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" />
              <YAxis />
              <Tooltip shared={false} content={<CustomTooltip msg={msg} />} />
              <Line
                type="monotone"
                dataKey="value"
                name={metricLabelFromMessage(msg)}
                stroke="#ffcc00"
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function MultiLineTrendChart({ rows, msg, yearCol, seriesCol, numericCol }) {
  const { result: chartData, seriesValues } = pivotRows(
    rows,
    yearCol,
    seriesCol,
    numericCol
  );

  if (chartData.length === 0 || seriesValues.length === 0) return null;

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">{metricLabelFromMessage(msg)} Trend</div>

      <div className="qc-chart-layout">
        <LeftLegend items={seriesValues} />

        <div className="qc-chart-canvas">
          <ResponsiveContainer width="100%" height={430}>
            <LineChart data={chartData} margin={{ top: 20, right: 35, left: 15, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={yearCol} tickFormatter={(value) => String(value)} />
              <YAxis />
              <Tooltip shared={false} content={<CustomTooltip msg={msg} />} />

              {seriesValues.map((series, index) => (
                <Line
                  key={series}
                  type="monotone"
                  dataKey={series}
                  name={friendlyLabel(stripMetricPrefix(series))}
                  stroke={chartColors[index % chartColors.length]}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  activeDot={{ r: 7 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function GroupedBarChart({ rows, yearCol, seriesCol, numericCol }) {
  const { result: chartData, seriesValues } = pivotRows(
    rows,
    yearCol,
    seriesCol,
    numericCol
  );

  if (chartData.length === 0 || seriesValues.length === 0) return null;

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">Grouped Comparison</div>

      <div className="qc-chart-layout">
        <LeftLegend items={seriesValues} />

        <div className="qc-chart-canvas">
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={yearCol} tickFormatter={(value) => String(value)} />
              <YAxis />
              <Tooltip
                shared={false}
                cursor={{ fill: "rgba(255, 204, 0, 0.12)" }}
                content={<CustomTooltip msg={{}} />}
              />
              {seriesValues.map((series, index) => (
                <Bar
                  key={series}
                  dataKey={series}
                  name={friendlyLabel(stripMetricPrefix(series))}
                  fill={chartColors[index % chartColors.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function PieDonutChart({ rows, msg, categoryCol, numericCol, donut }) {
  const chartData = dedupeRows(rows, [categoryCol, numericCol])
    .filter((row) => row[categoryCol] && row[numericCol] !== null)
    .slice(0, 10)
    .map((row) => ({
      name: friendlyLabel(stripMetricPrefix(row[categoryCol])),
      value: Number(row[numericCol]) || 0,
    }));

  if (chartData.length === 0) return null;

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">
        {donut ? "Donut Chart" : "Pie Chart"} — {metricLabelFromMessage(msg)}
      </div>

      <div className="qc-chart-layout">
        <LeftLegend items={chartData.map((row) => row.name)} />

        <div className="qc-chart-canvas">
          <ResponsiveContainer width="100%" height={360}>
            <PieChart>
              <Tooltip content={<CustomTooltip msg={msg} />} />
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={120}
                innerRadius={donut ? 70 : 0}
                label
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={index}
                    fill={chartColors[index % chartColors.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function HeatmapChart({ rows, msg, categoryCol, yearCol, numericCol }) {
  const cleanRows = dedupeRows(rows, [categoryCol, yearCol, numericCol]).filter(
    (row) => row[categoryCol] && row[yearCol] !== null && row[numericCol] !== null
  );

  if (cleanRows.length === 0) return null;

  const categories = Array.from(
    new Set(cleanRows.map((row) => String(row[categoryCol])))
  ).slice(0, 12);

  const years = Array.from(new Set(cleanRows.map((row) => row[yearCol]))).sort(
    (a, b) => Number(a) - Number(b)
  );

  const values = cleanRows.map((row) => Number(row[numericCol]) || 0);
  const min = Math.min(...values);
  const max = Math.max(...values);

  function getValue(category, year) {
    const found = cleanRows.find(
      (row) => String(row[categoryCol]) === category && row[yearCol] === year
    );

    return found ? Number(found[numericCol]) || 0 : null;
  }

  function intensity(value) {
    if (value === null || max === min) return 0.08;
    return 0.18 + ((value - min) / (max - min)) * 0.82;
  }

  function formatHeatValue(value) {
    if (value === null) return "";

    if (shouldShowAsPercent(msg) && value >= 0 && value <= 1) {
      return `${(value * 100).toFixed(1)}%`;
    }

    return value.toLocaleString();
  }

  return (
    <div className="qc-chart-card">
      <div className="qc-card-title">Heatmap — {metricLabelFromMessage(msg)}</div>

      <div className="qc-heatmap-wrap">
        <div
          className="qc-heatmap-grid"
          style={{
            gridTemplateColumns: `180px repeat(${years.length}, minmax(70px, 1fr))`,
          }}
        >
          <div className="qc-heatmap-header">Category</div>

          {years.map((year) => (
            <div key={year} className="qc-heatmap-header">
              {String(year)}
            </div>
          ))}

          {categories.map((category) => (
            <Fragment key={category}>
              <div className="qc-heatmap-label">
                {friendlyLabel(stripMetricPrefix(category))}
              </div>

              {years.map((year) => {
                const value = getValue(category, year);

                return (
                  <div
                    key={`${category}-${year}`}
                    className="qc-heatmap-cell"
                    style={{
                      background: `rgba(255, 204, 0, ${intensity(value)})`,
                    }}
                    title={`${friendlyLabel(stripMetricPrefix(category))} ${String(
                      year
                    )}: ${formatHeatValue(value) || "No data"}`}
                  >
                    {formatHeatValue(value)}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;