export type AnalyzeResponse = {
  meta: {
    announcerTicker: string;
    announcerName: string;
    earningsDate: string;
    eventWindowReturnPct: number;
  };
  impactLadder: { rank: number; label: string; severity: number; direction: string }[];
  exposureMatrix: { headers: string[]; rows: string[][] };
  evidence: { key: string; label: string; body: string; emphasis: "accent" | "danger" | "success" | "warn" }[];
  peerTable: { headers: string[]; rows: Record<string, string | number | null>[] };
  source: "mock";
  bloombergNote: string;
};
