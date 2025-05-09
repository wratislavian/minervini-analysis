#!/usr/bin/env python3
"""
Regenerates Minervini dashboard and drops it into docs/wyniki_minervini.html
Run daily via GitHub Actions.  Requires yfinance, pandas, matplotlib.
Images saved as PNG and referenced in the html – keeps GH‑Pages light.
"""
import base64
import glob
import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
DOCS_DIR = "docs"  # GH‑Pages points here
LINE_IMG = os.path.join(DOCS_DIR, "chart_counts.png")
DOT_IMG = os.path.join(DOCS_DIR, "chart_status.png")
HTML_OUT = os.path.join(DOCS_DIR, "wyniki_minervini.html")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------
csv_files = glob.glob("*_data.csv")
if not csv_files:
    raise SystemExit("Brak plików *_data.csv – nic do roboty.")

assets: dict[str, pd.DataFrame] = {}
for fp in csv_files:
    t = os.path.basename(fp).replace("_data.csv", "")
    df = (
        pd.read_csv(fp, index_col=0, parse_dates=True)
        .sort_index()
        .dropna(subset=["Close"])
    )
    assets[t] = df

# ---------------------------------------------------------------------------
# UTILS
# ---------------------------------------------------------------------------

def add_minervini(df: pd.DataFrame) -> pd.DataFrame:
    """Return copy with SMA‑s, 52‑week hi/lo and score column."""
    out = df.copy()
    out["SMA50"] = out["Close"].rolling(50).mean()
    out["SMA150"] = out["Close"].rolling(150).mean()
    out["SMA200"] = out["Close"].rolling(200).mean()
    out["LOW52"] = out["Close"].rolling(252).min()
    out["HIGH52"] = out["Close"].rolling(252).max()

    c1 = (out["SMA50"] > out["SMA150"]) & (out["SMA50"] > out["SMA200"])
    c2 = out["SMA150"] > out["SMA200"]
    c3 = (out["Close"] > out["SMA50"]) & (out["Close"] > out["SMA150"]) & (out["Close"] > out["SMA200"])
    c4 = out["Close"] > out["LOW52"] * 1.3
    c5 = out["Close"] >= out["HIGH52"] * 0.75

    out["SCORE"] = c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) + c5.astype(int)
    return out

for t in list(assets):
    assets[t] = add_minervini(assets[t])

# ---------------------------------------------------------------------------
# DATE WINDOW (30 calendar days back from latest common date)
# ---------------------------------------------------------------------------
latest = max(df.index.max() for df in assets.values())
start  = latest - timedelta(days=29)  # inclusive
window = pd.date_range(start, latest, freq="D")

# ---------------------------------------------------------------------------
# SERIES: HOW MANY MEET 5/5 EACH DAY
# ---------------------------------------------------------------------------
count_series = pd.Series(index=window, dtype=int).fillna(0)
for day in window:
    count_series.loc[day] = sum(
        df.loc[day, "SCORE"] == 5 if day in df.index else 0 for df in assets.values()
    )

# ---------------------------------------------------------------------------
# PLOT 1 – LINE CHART
# ---------------------------------------------------------------------------
plt.figure(figsize=(10, 4))
plt.plot(count_series.index, count_series.values, marker="o")
plt.title("Liczba aktywów z wynikiem 5/5 (ostatnie 30 dni)")
plt.xlabel("Data")
plt.ylabel("Ilość")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(LINE_IMG, dpi=110)
plt.close()

# ---------------------------------------------------------------------------
# PLOT 2 – DOT STATUS FOR LATEST DAY
# ---------------------------------------------------------------------------
colors = {5: "#2ecc71", 4: "#7f8c8d"}  # green / grey

tickers = list(assets.keys())
y_pos = range(len(tickers))
plt.figure(figsize=(6, max(4, len(tickers) * 0.4)))
for y, t in zip(y_pos, tickers):
    df = assets[t]
    score = int(df.loc[latest, "SCORE"]) if latest in df.index else -99
    col = colors.get(score, "#e74c3c")  # red default
    plt.scatter(0, y, s=120, c=col)
plt.yticks(y_pos, tickers)
plt.gca().get_xaxis().set_visible(False)
plt.title(f"Status aktywów vs kryteria (stan: {latest.date()})")
plt.tight_layout()
plt.savefig(DOT_IMG, dpi=110)
plt.close()
