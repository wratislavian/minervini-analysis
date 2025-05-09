#!/usr/bin/env python3
"""Minervini auto‑dashboard → docs/ (GH‑Pages)
Run from repo root via `python src/generate.py` (GitHub Action does exactly that).
"""
from pathlib import Path
from datetime import datetime, timedelta
import glob, os
import pandas as pd
import matplotlib.pyplot as plt

# ── paths ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent     # repo root
DOCS_DIR  = ROOT / "docs"
LINE_IMG  = DOCS_DIR / "chart_counts.png"
DOT_IMG   = DOCS_DIR / "chart_status.png"
HTML_OUT  = DOCS_DIR / "wyniki_minervini.html"
DOCS_DIR.mkdir(exist_ok=True)

# ── load csvs ────────────────────────────────────────────────────────────────
assets: dict[str, pd.DataFrame] = {}
for fp in glob.glob(str(ROOT / "*_data.csv")):
    t   = Path(fp).name.replace("_data.csv", "")
    df  = pd.read_csv(fp, index_col=0, parse_dates=True).sort_index()
    assets[t] = df
if not assets:
    raise SystemExit("No *_data.csv found – abort.")

# ── helpers ──────────────────────────────────────────────────────────────────

def add_minervini(df: pd.DataFrame) -> pd.DataFrame:
    r = df.copy()
    r["SMA50"]  = r["Close"].rolling(50).mean()
    r["SMA150"] = r["Close"].rolling(150).mean()
    r["SMA200"] = r["Close"].rolling(200).mean()
    r["LOW52"]  = r["Close"].rolling(252).min()
    r["HIGH52"] = r["Close"].rolling(252).max()
    c1 = (r.SMA50 > r.SMA150) & (r.SMA50 > r.SMA200)
    c2 = r.SMA150 > r.SMA200
    c3 = (r.Close > r.SMA50) & (r.Close > r.SMA150) & (r.Close > r.SMA200)
    c4 = r.Close > r.LOW52 * 1.3
    c5 = r.Close >= r.HIGH52 * 0.75
    r["SCORE"] = c1.astype(int)+c2.astype(int)+c3.astype(int)+c4.astype(int)+c5.astype(int)
    return r

assets = {t: add_minervini(df) for t, df in assets.items()}

# ── date window ──────────────────────────────────────────────────────────────
latest  = max(df.index.max() for df in assets.values())
window  = pd.date_range(latest - timedelta(days=29), latest, freq="D")
counts  = pd.Series(index=window, dtype=int)
for d in window:
    counts[d] = sum(df.loc[d, "SCORE"]==5 if d in df.index else 0 for df in assets.values())

# ── chart 1: line ────────────────────────────────────────────────────────────
plt.figure(figsize=(10,4))
plt.plot(counts.index, counts, marker="o")
plt.title("Liczba aktywów 5/5 (30 dni)")
plt.xlabel("Data"); plt.ylabel("Ilość"); plt.xticks(rotation=45)
plt.tight_layout(); plt.savefig(LINE_IMG, dpi=110); plt.close()

# ── chart 2: dots ────────────────────────────────────────────────────────────
color_map = {5:"#2ecc71", 4:"#7f8c8d"}  # green/grey, else red
plt.figure(figsize=(6, max(4, len(assets)*0.4)))
for y,(t,df) in enumerate(assets.items()):
    s = int(df.loc[latest,"SCORE"])
    plt.scatter(0, y, s=120, c=color_map.get(s,"#e74c3c"))
plt.yticks(range(len(assets)), assets.keys()); plt.gca().xaxis.set_visible(False)
plt.title(f"Status {latest.date()}")
plt.tight_layout(); plt.savefig(DOT_IMG, dpi=110); plt.close()

# ── html ─────────────────────────────────────────────────────────────────────
HTML_OUT.write_text(f"""<!DOCTYPE html><html lang=pl><meta charset=UTF-8><title>Minervini {latest:%Y-%m-%d}</title>
<style>body{{margin:0;background:#111;color:#ddd;font-family:Arial;text-align:center}}
h1{{margin:1em 0;color:#fff}}img{{max-width:100%;border:1px solid #444;box-shadow:0 0 6px #000;margin:20px 0}}</style>
<h1>Minervini – {latest:%Y-%m-%d}</h1>
<img src='chart_counts.png'><img src='chart_status.png'>
<p style='font-size:.8em'>zielony = 5/5, szary = 4/5, czerwony &lt; 4</p>""")

print("Generated →", HTML_OUT)
