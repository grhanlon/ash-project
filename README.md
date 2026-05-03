# Peer Read-Through

A single-page Streamlit tool for an equity analyst: when a covered company reports earnings, show how each portfolio peer is statistically related to the announcer — without collapsing it into a single score.

The output is a transparent table of GICS overlap, 252-day betas (vs. the announcer and vs. SPX), and how each peer actually moved on the announcer's last 8 earnings reaction days.

## What it answers

> *"My announcer just printed. Which of my peers should I be paying attention to first, and is there any historical evidence they actually move with the announcer?"*

The analyst, not the tool, makes the read-through call. The tool just lays out the evidence.

## What it shows

For an announcing company and a list of portfolio tickers, the table contains one row per peer with:

| Column | Meaning |
|---|---|
| Ticker / Name | Peer identity |
| Sector / Industry / Sub-Industry | Peer's GICS classification |
| Sector Match / Industry Match | True if peer shares GICS level with announcer |
| Beta vs Announcer | OLS slope of peer daily returns on announcer daily returns, last ~252 trading days |
| Beta vs SPX | Same, vs. SPX Index — distinguishes "moves with announcer" from "moves with the market" |
| History Days | Trading days actually used in the beta regression |
| Earnings-Day Mean / Median Return (%) | Peer's return on the announcer's last 8 earnings reaction days |
| Hit Rate | Fraction of past earnings where peer moved in the same direction as announcer |
| Samples | Number of past earnings dates that produced a usable peer return (≤8) |
| Error | Populated only if the peer's data could not be fetched; row falls to the bottom |

The header shows the announcer name, the earnings date used, and the announcer's own event-window return.

## Design choices (what is *not* here)

- **No composite score.** The previous version produced a single 0–100 number. It was thrown away — small samples and high collinearity between sector overlap, beta, and event response made it false precision. Analysts get the inputs and synthesize themselves.
- **No "confidence" or "direction" labels.** Same reason.
- **No persistence, notes, watchlists, multi-user features.** Single user, single process, fresh run on each input change.
- **No fallback data source.** Bloomberg only.
- **No caching.** Streamlit re-runs on each input change; Bloomberg latency is acceptable for ~10 tickers.

## How the numbers are computed

- **Beta** — OLS slope of peer daily returns on reference daily returns over the trailing ~252 trading days. Aligned by intersecting trading dates. Returns `None` if fewer than 60 aligned days, or if reference return variance is zero.
- **Earnings reaction day** — for each historical announcement date `d`, the day in `[d-1, d, d+1]` with the largest `|announcer return|`. Mitigates the BMO/AMC ambiguity (a 7am print's reaction is in `d`'s close-to-close return; a 4:30pm print's reaction is in `d+1`'s). Ties break toward the announcement day itself.
- **Earnings-day stats** — for each announcer reaction day, look up the peer's same-day return. Mean, median, hit rate (same-sign agreement), and sample count are computed only over announcement dates that produced a usable peer return.
- **Per-peer error isolation** — any failure pulling a peer's data becomes an error row at the bottom of the table; the rest of the analysis continues. An announcer-side failure aborts the whole run.

See `docs/plans/2026-05-03-peer-readthrough-design.md` for the design discussion (failure modes considered, alternatives rejected, why no composite score).

## Requirements

- Python 3.11+
- Bloomberg Terminal running locally and logged in
- `xbbg` (Python wrapper around blpapi)

This tool will not run on a machine without a live Bloomberg session.

## Install

```powershell
pip install -r requirements.txt
pip install xbbg
```

`xbbg` is intentionally not in `requirements.txt` — it requires Bloomberg's `blpapi` shared library and is not always installable in CI environments. The codebase imports it lazily so tests run without it.

## Run

```powershell
streamlit run app.py
```

In the sidebar:
- Enter the announcing ticker in Bloomberg form (e.g. `F US`, `MSFT US`, `SPX Index`).
- Leave **Use most recent earnings date** checked, or uncheck and pick a specific date for backtesting.
- Paste your portfolio, one ticker per line.
- Click **Run analysis**.

## Windows VDI (Bloomberg on the same machine)

Use this when analysts have a **Windows virtual desktop** with **Bloomberg Terminal** and **no installs from the public internet** — everything runs **inside the VDI**, not on Vercel.

1. Copy or clone this repo onto the VDI (e.g. `git clone …` or zip from IT).
2. **One-time setup** (needs Python 3.11+ on the image): double-click **`vdi/setup-venv.bat`** *or* run  
   `powershell -ExecutionPolicy Bypass -File vdi\setup-venv.ps1`
3. Install Bloomberg’s Python API per your firm (often **`pip install xbbg`** after Terminal/`blpapi` are on the PATH — confirm with IT).
4. **Each session:** double-click **`vdi/run-streamlit.bat`** *or*  
   `powershell -ExecutionPolicy Bypass -File vdi\run-streamlit.ps1`
5. In the **VDI’s browser**, open **`http://127.0.0.1:8501`** (or the URL Streamlit prints). Stay on localhost — that keeps Bloomberg traffic on the VDI.

`.streamlit/config.toml` binds Streamlit to **127.0.0.1:8501** so the server is not exposed to other machines on the network by default.

**IT checklist (short):** Python 3.11+ · permission to create `.venv` · Bloomberg Terminal + API · outbound pip or internal package mirror · allow **local** HTTP to 127.0.0.1 in the VDI browser.

## Project layout

```
app.py                          Streamlit entry point — main() only, no module-level Streamlit calls
contagion/
  __init__.py                   Public exports: AnalysisRequest, AnalysisResult, PeerStat
  models.py                     Frozen dataclasses + ticker normalization + invariants
  data.py                       BloombergAdapter, BloombergClient Protocol, live_bloomberg_client()
  analysis.py                   compute_beta, pick_earnings_reaction_day, compute_peer_stats
  report.py                     REPORT_COLUMNS, peer_stats_to_dataframe
tests/
  test_models.py                Dataclass validation
  test_data.py                  BloombergAdapter against an injected FakeClient
  test_analysis.py              Beta, reaction-day, full aggregator with synthetic Bloomberg data
  test_report.py                Column layout, error-row rendering
  test_app_smoke.py             app.py imports cleanly and exposes main()
  conftest.py                   (intentionally minimal — fakes live next to their tests)
design/
  done.pen                      Pencil document; `variables` drive Streamlit + Next.js themes
web/                            Next.js app for Vercel (`npm run dev` in `web/`)
desktop/
  launcher.py                   Starts Streamlit (used by PyInstaller / optional dev)
  contagion.spec                PyInstaller build recipe → `dist/ContagionReadThrough.app`
  requirements-build.txt        pyinstaller only (build machine)
.streamlit/
  config.toml                   Streamlit server/browser defaults (incl. VDI bind 127.0.0.1:8501)
vdi/
  run-streamlit.bat             Windows: start Streamlit from repo root (uses .venv if present)
  setup-venv.bat                Windows: create .venv and pip install requirements.txt
  run-streamlit.ps1             PowerShell alternative if .bat is blocked
  setup-venv.ps1                PowerShell one-time venv setup
docs/plans/
  2026-05-03-peer-readthrough-design.md         Approved design doc
  2026-05-03-peer-readthrough-implementation.md Task-by-task plan
```

## Testing

```powershell
pytest -q
```

All tests run offline against an injected `FakeClient` — no Bloomberg required. The `live_bloomberg_client()` factory imports `xbbg` lazily, so the module is importable on a Bloomberg-free machine; only calling the factory triggers the import.

## Architecture notes

- **`BloombergAdapter` takes a `BloombergClient` Protocol in its constructor.** Tests inject a `FakeClient`; production injects `live_bloomberg_client()`. The adapter never touches `xbbg` directly.
- **`xbbg` 1.0.0 returns Narwhals-wrapped Arrow DataFrames in long format** (`[ticker, field, value]` for `bdp`, `[ticker, date, field, value]` for `bdh`). The `_XbbgClient` inside `live_bloomberg_client()` converts to pandas and pivots to the wide structures the adapter expects.
- **Past earnings dates** are sourced via `bdh('ANNOUNCEMENT_DT', ...)` over a 3-year window. Bloomberg returns quarterly historical announcement dates as YYYYMMDD integers.
- **All analysis is pure.** `analysis.py` takes an `AnalysisRequest` and any object satisfying the adapter interface, and returns an `AnalysisResult`. No I/O, no Streamlit, no globals.
- **`PeerStat` enforces an invariant**: when `error` is non-None, every numeric field is `None`. Validated in `__post_init__`.

## Web UI (Next.js on Vercel)

The `web/` directory is a **Next.js** app meant for **Vercel**. On the server it reads `design/done.pen` and maps the Pencil **`variables`** object into CSS custom properties (`--pen-accent`, etc.). That is the supported way to “use” the `.pen` file on the web today: as **structured design tokens**, not as a live Pencil canvas (there is no first-party browser renderer for the full `.pen` scene graph).

- **Local:** `cd web && npm install && npm run dev`
- **Deploy:** In Vercel, set the project **Root Directory** to `web`. The repository is cloned in full, so `../design/done.pen` resolves during the build.
- **Data:** `POST /api/analyze` returns **mock** JSON only. Real Bloomberg-backed peer stats still require the Python/Streamlit path (or a separate private backend with Terminal/`xbbg`).

## Desktop app (PyInstaller, double-click for analysts)

Build a **macOS `.app`** on your machine; hand analysts the zip — they open it like any app (no terminal).

**You build once** (from `ash-project`, Python 3.11+ recommended, ideally the same env where Bloomberg + `xbbg` already work if you want those bundled):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r desktop/requirements-build.txt
# Optional: pip install xbbg   # if Terminal / blpapi are set up on the build machine
pyinstaller desktop/contagion.spec
```

**Artifact:** `dist/ContagionReadThrough.app`. First launch on a Mac may need **Right-click → Open** (unsigned).

**What it is:** the same **`streamlit run app.py`** UI, started by `desktop/launcher.py`. Bloomberg Terminal must still be logged in on that Mac for live data.

**Windows:** run the same `pyinstaller desktop/contagion.spec` on Windows to get `dist/ContagionReadThrough/ContagionReadThrough.exe` (no `.app` bundle).
