import { NextResponse } from "next/server";
import type { AnalyzeResponse } from "@/lib/types";
import { DRIVER_LABELS } from "@/lib/drivers";

export const runtime = "nodejs";

type Body = {
  announcingTicker?: string;
  portfolioText?: string;
  drivers?: string[];
  useLatest?: boolean;
  earningsDate?: string;
};

export async function POST(req: Request) {
  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const ticker = (body.announcingTicker ?? "F US").trim().toUpperCase();
  const drivers = (body.drivers?.length ? body.drivers : ["production_volume"]).map((d) =>
    d.trim(),
  );

  const announcerName =
    ticker.startsWith("F ") || ticker === "F US" ? "Ford Motor Company" : `Company (${ticker})`;

  const earningsDate = body.useLatest === false && body.earningsDate
    ? body.earningsDate
    : new Date().toISOString().slice(0, 10);

  const evidence = drivers.map((k) => {
    const label = DRIVER_LABELS[k] ?? k;
    const emphasis =
      k === "production_volume" ? ("danger" as const) : k.includes("credit") ? ("warn" as const) : ("accent" as const);
    return {
      key: k,
      label: label.toUpperCase(),
      body: `${label} selected for downstream mapping. Supply-chain seed links are MVP-only on the web build.`,
      emphasis,
    };
  });

  const impactLadder = [
    { rank: 1, label: `${ticker}  ·  ${DRIVER_LABELS[drivers[0]] ?? drivers[0]}  ·  negative  ·  high`, severity: 3, direction: "negative" },
    { rank: 2, label: "Peer B  ·  guide-down  ·  mixed  ·  med", severity: 2, direction: "mixed" },
    { rank: 3, label: "Peer C  ·  demand  ·  positive  ·  low", severity: 1, direction: "positive" },
  ];

  const driverCols = drivers.map((d) => DRIVER_LABELS[d] ?? d);
  const exposureMatrix = {
    headers: ["Peer", ...driverCols],
    rows: [
      ["LEA US", ...driverCols.map((_, i) => (i === 0 ? "NEG · 3 · HIGH" : "NEU · 1 · LOW"))],
      ["APTV US", ...driverCols.map(() => "NEU · 1 · LOW")],
    ],
  };

  const peerTable = {
    headers: [
      "Ticker",
      "Beta vs Announcer",
      "Beta vs SPX",
      "Hit Rate",
    ],
    rows: [
      { Ticker: "LEA US", "Beta vs Announcer": "1.12", "Beta vs SPX": "0.98", "Hit Rate": "0.62" },
      { Ticker: "APTV US", "Beta vs Announcer": "0.88", "Beta vs SPX": "1.05", "Hit Rate": "0.50" },
    ],
  };

  const payload: AnalyzeResponse = {
    meta: {
      announcerTicker: ticker,
      announcerName,
      earningsDate,
      eventWindowReturnPct: -2.35,
    },
    impactLadder,
    exposureMatrix,
    evidence,
    peerTable,
    source: "mock",
    bloombergNote:
      "Vercel runs mock data only. Live betas and GICS require the Python Streamlit app with Bloomberg Terminal + xbbg, or a dedicated desktop/VPN backend.",
  };

  return NextResponse.json(payload);
}
