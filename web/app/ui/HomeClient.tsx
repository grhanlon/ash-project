"use client";

import { useCallback, useState } from "react";
import { DRIVER_KEYS, DRIVER_LABELS } from "@/lib/drivers";
import type { AnalyzeResponse } from "@/lib/types";

const DEFAULT_PORTFOLIO = "LEA US\nAPTV US\nBWA US\nAN US";

export default function HomeClient() {
  const [ticker, setTicker] = useState("F US");
  const [useLatest, setUseLatest] = useState(true);
  const [earningsDate, setEarningsDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [portfolio, setPortfolio] = useState(DEFAULT_PORTFOLIO);
  const [drivers, setDrivers] = useState<string[]>(["production_volume"]);
  const [commentary, setCommentary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const toggleDriver = (key: string) => {
    setDrivers((prev) =>
      prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key],
    );
  };

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          announcingTicker: ticker,
          portfolioText: portfolio,
          drivers: drivers.length ? drivers : ["production_volume"],
          useLatest,
          earningsDate,
        }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const data = (await res.json()) as AnalyzeResponse;
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [ticker, portfolio, drivers, useLatest, earningsDate]);

  const metaLine =
    result != null
      ? `${result.meta.announcerTicker} · ${result.meta.earningsDate}`
      : "— · —";

  return (
    <div className="shell">
      <aside className="rail">
        <div>
          <p className="brandTitle">CONTAGION</p>
          <p className="brandSub">Read-through console</p>
        </div>

        <p className="railLabel" style={{ marginTop: 0 }}>
          Case
        </p>
        <div className="caseCard">
          <label className="sr" htmlFor="ticker">
            Announcing ticker
          </label>
          <input
            id="ticker"
            className="input"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            autoCapitalize="characters"
            placeholder="F US"
          />
          <label className="checkRow">
            <input
              type="checkbox"
              checked={useLatest}
              onChange={(e) => setUseLatest(e.target.checked)}
            />
            Use most recent earnings
          </label>
          {!useLatest ? (
            <input
              type="date"
              className="input"
              value={earningsDate}
              onChange={(e) => setEarningsDate(e.target.value)}
            />
          ) : (
            <p className="hint">Date override inactive</p>
          )}
        </div>

        <p className="railLabel">Portfolio</p>
        <div className="caseCard portfolioBox">
          <textarea
            className="input textarea mono"
            value={portfolio}
            onChange={(e) => setPortfolio(e.target.value)}
            aria-label="Portfolio tickers"
          />
        </div>

        <p className="railLabel">Driver filters</p>
        <div className="caseCard" style={{ gap: 8 }}>
          {DRIVER_KEYS.map((k) => (
            <label key={k} className="checkRow">
              <input
                type="checkbox"
                checked={drivers.includes(k)}
                onChange={() => toggleDriver(k)}
              />
              {DRIVER_LABELS[k]}
            </label>
          ))}
        </div>

        <p className="railLabel">Transcript buffer</p>
        <textarea
          className="input textarea"
          style={{ minHeight: 120 }}
          value={commentary}
          onChange={(e) => setCommentary(e.target.value)}
          aria-label="Transcript or commentary excerpt"
        />

        <button type="button" className="btnRun" disabled={loading} onClick={() => void run()}>
          {loading ? "Running…" : "Run Analysis"}
        </button>
      </aside>

      <main className="main">
        <header className="workbenchHeader">
          <div>
            <h1 className="workbenchTitle">Contagion Read-Through</h1>
            <p className="workbenchSub">
              Case-file view: ranked impact, evidence trail, and peer tape in one pass.
            </p>
          </div>
          <div className="meta">
            <div className="meta1">{metaLine}</div>
            <div className="meta2">Output labels: direction · magnitude · confidence</div>
          </div>
        </header>

        <div className="content">
          {error ? (
            <div className="infoBanner errorBanner">Error: {error}</div>
          ) : null}

          {!result && !loading && !error ? (
            <div className="infoBanner">
              Configure the case in the command rail and click <strong>Run Analysis</strong>. Theme
              tokens load from <span className="mono">design/done.pen</span> at build/runtime (server reads the Pencil{" "}
              <span className="mono">variables</span> block).
            </div>
          ) : null}

          {result ? (
            <>
              <p style={{ color: "var(--pen-text-secondary)", fontSize: 13, margin: 0 }}>
                <strong style={{ color: "var(--pen-text-primary)" }}>Expected Read-Through</strong>{" "}
                — announcer miss driver → downstream company → direction · magnitude · confidence.
              </p>

              <div className="grid2">
                <div className="panel">
                  <div className="panelHead">
                    <h2 className="panelTitle">Impact Ladder</h2>
                    <p className="panelKicker">Severity 1–3, categorical</p>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontFamily: "IBM Plex Mono, monospace", fontSize: 13 }}>
                    {result.impactLadder.map((row) => (
                      <li key={row.rank} style={{ marginBottom: 8 }}>
                        <span
                          style={{
                            color:
                              row.direction === "negative"
                                ? "var(--pen-danger)"
                                : row.direction === "positive"
                                  ? "var(--pen-success)"
                                  : "var(--pen-warning)",
                          }}
                        >
                          {row.label}
                        </span>
                        <span style={{ color: "var(--pen-text-secondary)", marginLeft: 8 }}>
                          (severity {row.severity})
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="panel">
                  <div className="panelHead">
                    <h2 className="panelTitle">Evidence Rail</h2>
                    <p className="panelKicker">Trace snippets used to weight confidence.</p>
                  </div>
                  {result.evidence.map((ev) => {
                    const tier =
                      ev.emphasis === "danger"
                        ? "evidenceDanger"
                        : ev.emphasis === "success"
                          ? "evidenceSuccess"
                          : ev.emphasis === "warn"
                            ? "evidenceWarn"
                            : "evidenceAccent";
                    return (
                      <div key={ev.key} className={`evidenceCard ${tier}`}>
                        <h4>{ev.label}</h4>
                        <p>{ev.body}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="panel">
                <div className="panelHead">
                  <h2 className="panelTitle">Exposure Matrix</h2>
                  <p className="panelKicker">Cells encode direction · magnitude · confidence</p>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="table">
                    <thead>
                      <tr>
                        {result.exposureMatrix.headers.map((h) => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.exposureMatrix.rows.map((r) => (
                        <tr key={r[0]}>
                          {r.map((c, i) => (
                            <td key={`${r[0]}-${i}`}>{c}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="caveat">
                <strong>Expected read-through</strong> — model output, not observed market reaction.{" "}
                {commentary ? `Transcript buffer: ${commentary.slice(0, 200)}${commentary.length > 200 ? "…" : ""}` : null}
              </div>

              <div className="panel">
                <div className="panelHead">
                  <h2 className="panelTitle">Peer Statistics</h2>
                  <p className="panelKicker mono">
                    {result.meta.announcerName} · {result.meta.announcerTicker}
                  </p>
                </div>
                <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
                  <div className="caseCard" style={{ minWidth: 140 }}>
                    <div className="railLabel" style={{ marginTop: 0 }}>
                      Earnings date
                    </div>
                    <div className="mono">{result.meta.earningsDate}</div>
                  </div>
                  <div className="caseCard" style={{ minWidth: 140 }}>
                    <div className="railLabel" style={{ marginTop: 0 }}>
                      Event-window return
                    </div>
                    <div className="mono">{result.meta.eventWindowReturnPct.toFixed(2)}%</div>
                  </div>
                </div>
                <table className="table">
                  <thead>
                    <tr>
                      {result.peerTable.headers.map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.peerTable.rows.map((row, i) => (
                      <tr key={i}>
                        {result.peerTable.headers.map((h) => (
                          <td key={h}>{String(row[h] ?? "—")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="hint" style={{ margin: 0 }}>
                {result.bloombergNote}
              </p>
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}
