#!/usr/bin/env python3
"""Minervini auto‑dashboard → docs/ (GitHub Pages)
-------------------------------------------------
• Szuka plików *_data.csv.
• Jeśli brak – próbuje uruchomić `1download.py`.
• Gdy nadal brak danych – tworzy stronę‑placeholder i kończy funkcję, **bez** `sys.exit`,
  żeby workflow w piaskownicy nie rzucał `SystemExit`.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
import glob
import os
import subprocess
import sys

import pandas as pd
import matplotlib.pyplot as plt

# ────────────────────────── helpers ─────────────────────────────────────────

def ensure_csv_files(root: Path) -> list[str]:
    """Return list of *_data.csv; try running 1download.py when empty."""
    csvs = glob.glob(str(root / "*_data.csv"))
    if csvs:
        return csvs

    dl = root / "1download.py"
    if dl.exists():
        print("[info] brak CSV → odpalam 1download.py", file=sys.stderr)
        subprocess.run([sys.executable, str(dl)], check=True)
        return glob.glob(str(root / "*_data.csv"))
    return []


def add_minervini(df: pd.DataFrame) -> pd.DataFrame:
    r = df.copy()
    r["SMA50"]  = r.Close.rolling(50).mean()
    r["SMA150"] = r.Close.rolling(150).mean()
    r["SMA200"] = r.Close.rolling(200).mean()
    r["LOW52"]  = r.Close.rolling(252).min()
    r["HIGH52"] = r.Close.rolling(252).max()
    c1 = (r.SMA50 > r.SMA150) & (r.SMA50 > r.SMA200)
    c2 = r.SMA150 > r.SMA200
    c3 = (r.Close > r.SMA50) & (r.Close > r.SMA150) & (r.Close > r.SMA200)
    c4 = r.Close > r.LOW52 * 1.3
    c5 = r.Close >= r.HIGH52 * 0.75
    r["SCORE"] = c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) + c5.astype(int)
    return r


# ───────────────────────────── main ────────────────────────────────────────

def main() -> None:
    # ścieżki
    try:
        root = Path(__file__).resolve().parent.parent  # normal run
    except NameError:
        root = Path.cwd()                              # notebook / gha sandbox

    docs      = root / "docs"
    line_img  = docs / "chart_counts.png"
    dot_img   = docs / "chart_status.png"
    html_out  = docs / "wyniki_minervini.html"
    docs.mkdir(exist_ok=True)

    # dane
    csv_files = ensure_csv_files(root)

    if not csv_files:
        # placeholder
        html_out.write_text("""<!DOCTYPE html><meta charset=utf-8><title>Minervini – brak danych</title>
<style>body{background:#111;color:#ccc;font-family:Arial;text-align:center;padding-top:10%}</style>
<h1>Nie znaleziono plików *_data.csv</h1>
<p>Dashboard pojawi się automatycznie po dodaniu danych lub gdy <code>1download.py</code> je pobierze.</p>""")
        print("[warn] brak CSV – wygenerowano stronę‑placeholder.")
        return  # ← zamiast sys.exit()

    # wczytaj
    assets: dict[str, pd.DataFrame] = {}
    for fp in csv_files:
        tic = Path(fp).stem.replace("_data", "")
        df  = pd.read_csv(fp, index_col=0, parse_dates=True).sort_index()
        assets[tic] = add_minervini(df)

    # 30‑dniowe okno
    latest = max(df.index.max() for df in assets.values())
    window = pd.date_range(latest - timedelta(days=29), latest, freq="D")
    counts = pd.Series(index=window, dtype=int).fillna(0)
    for d in window:
        counts[d] = sum(df.loc[d, "SCORE"] == 5 if d in df.index else 0 for df in assets.values())

    # wykres 1
    plt.figure(figsize=(10, 4))
    plt.plot(counts.index, counts, marker="o")
    plt.title("Liczba aktywów 5/5 (30 dni)")
    plt.xlabel("Data"); plt.ylabel("Ilość"); plt.xticks(rotation=45)
    plt.tight_layout(); plt.savefig(line_img, dpi=110); plt.close()

    # wykres 2
    color_map = {5: "#2ecc71", 4: "#7f8c8d"}
    plt.figure(figsize=(6, max(4, len(assets) * 0.4)))
    for y, (t, df) in enumerate(assets.items()):
        score = int(df.loc[latest, "SCORE"])
        plt.scatter(0, y, s=120, c=color_map.get(score, "#e74c3c"))
    plt.yticks(range(len(assets)), assets.keys()); plt.gca().xaxis.set_visible(False)
    plt.title(f"Status {latest.date()}")
    plt.tight_layout(); plt.savefig(dot_img, dpi=110); plt.close()

    # html
    html_out.write_text(f"""<!DOCTYPE html><html lang=pl><meta charset=UTF-8>
<title>Minervini {latest:%Y-%m-%d}</title>
<style>body{{margin:0;background:#111;color:#ddd;font-family:Arial;text-align:center}}
 h1{{margin:1em 0;color:#fff}}
 img{{max-width:100%;border:1px solid #444;box-shadow:0 0 6px #000;margin:20px 0}}
</style>
<h1>Minervini – {latest:%Y-%m-%d}</h1>
<img src='chart_counts.png'>
<img src='chart_status.png'>
<p style='font-size:.8em'>zielony = 5/5, szary = 4/5, czerwony &lt; 4</p>""")

    print("[ok] dashboard wygenerowany → docs/")


if __name__ == "__main__":
    main()
