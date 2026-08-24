from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

HUMAN_FILES = ("A1.csv", "A2.csv", "A3.csv")
DIMS = ("dominant_actor", "tone", "framing", "balance", "political_lean")
DIM_LABELS = {
    "dominant_actor": "Dominantni akter",
    "tone": "Ton",
    "framing": "Uokviravanje",
    "balance": "Balansiranost",
    "political_lean": "Politička usmjerenost",
}
TONE_ORDER = (-2, -1, 0, 1, 2)
BALANCE_ORDER = (0, 1, 2)
LEAN_CATS = (
    "neutralno",
    "nejasno",
    "pro_vlast",
    "pro_opozicija",
    "pro_bosnjacka_opcija",
    "pro_srpska_opcija",
    "pro_hrvatska_opcija",
    "pro_gradjanska_opcija",
)
FRAME_CATS = (
    "konflikt",
    "odgovornost",
    "ekonomski",
    "moralni",
    "proceduralni",
    "nacionalni",
    "neutralni",
)

def strip_diacritics(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )

def norm_actor(value) -> str:
    value = "" if pd.isna(value) else str(value)
    value = strip_diacritics(value.lower().strip())
    value = value.replace("&", ",").replace(";", ",").replace("/", ",")
    tokens = []
    for token in value.split(","):
        token = re.sub(r"\s+", " ", token).strip(" .-_")
        if token:
            tokens.append(token)
    return ",".join(sorted(tokens))

def norm_frame(value) -> str:
    value = "" if pd.isna(value) else str(value).strip().lower()
    return {"neutralan": "neutralni", "neutralno": "neutralni"}.get(value, value)

def norm_lean(value) -> str:
    value = "" if pd.isna(value) else str(value).strip().lower()
    return {"neutralan": "neutralno", "neutralni": "neutralno"}.get(value, value)

def norm_numeric(value, field: str) -> int:
    if pd.isna(value):
        raise ValueError(f"Missing value in {field}")
    return int(float(str(value).strip().replace(",", ".")))

def norm_val(value, dim: str):
    if dim == "dominant_actor":
        return norm_actor(value)
    if dim == "framing":
        return norm_frame(value)
    if dim == "political_lean":
        return norm_lean(value)
    if dim in ("tone", "balance"):
        return norm_numeric(value, dim)
    return value

def load_csv(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path, encoding="utf-8-sig")
    required = {"article_id", *DIMS}
    missing = required - set(table.columns)
    if missing:
        raise RuntimeError(f"{path.name}: missing columns {sorted(missing)}")
    if table["article_id"].duplicated().any():
        raise RuntimeError(f"{path.name}: duplicate article_id")
    table["article_id"] = table["article_id"].astype(str)
    return table.set_index("article_id", drop=False)

def load_humans(directory: Path):
    humans = [load_csv(directory / name) for name in HUMAN_FILES]
    sets = [set(table.index) for table in humans]
    if not (sets[0] == sets[1] == sets[2]):
        raise RuntimeError("Human annotation files do not contain the same article_id set")
    return humans, sorted(sets[0])

def load_model_manifest(path: Path):
    table = pd.read_csv(path)
    required = {"model", "filename"}
    missing = required - set(table.columns)
    if missing:
        raise RuntimeError(f"Model manifest missing columns {sorted(missing)}")
    if table["model"].duplicated().any() or table["filename"].duplicated().any():
        raise RuntimeError("Model manifest contains duplicates")
    return list(table[["model", "filename"]].itertuples(index=False, name=None))

def load_models(directory: Path, manifest_path: Path):
    manifest = load_model_manifest(manifest_path)
    models = [(name, load_csv(directory / filename)) for name, filename in manifest]
    return manifest, models

def build_human_reference(humans, article_ids):
    refs = {dim: {} for dim in DIMS}
    consensus = {dim: {} for dim in DIMS}
    ratings = {dim: {} for dim in DIMS}
    for article_id in article_ids:
        for dim in DIMS:
            vals = [norm_val(table.loc[article_id, dim], dim) for table in humans]
            ratings[dim][article_id] = vals
            counts = Counter(vals)
            max_count = max(counts.values())
            consensus[dim][article_id] = 3 if max_count == 3 else 2 if max_count == 2 else 1
            if dim in ("tone", "balance"):
                refs[dim][article_id] = int(np.median(vals))
            else:
                refs[dim][article_id] = counts.most_common(1)[0][0] if max_count >= 2 else None
    return refs, consensus, ratings

def safe_kappa(y, p, weighted=False):
    if len(y) < 2:
        return float("nan")
    try:
        return float(cohen_kappa_score(y, p, weights="quadratic" if weighted else None))
    except Exception:
        return float("nan")

def krippendorff_alpha_nominal(items):
    counts = Counter(v for row in items for v in row if v is not None)
    n = sum(counts.values())
    if n < 2:
        return float("nan")
    observed = 0.0
    for row in items:
        row = [x for x in row if x is not None]
        m = len(row)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i != j and row[i] != row[j]:
                    observed += 1.0 / (m - 1)
    do = observed / n
    de = sum(c * (n - c) for c in counts.values()) / (n * (n - 1))
    return 1.0 - do / de if de > 0 else float("nan")

def krippendorff_alpha_ordinal(items, order):
    counts = Counter(v for row in items for v in row if v is not None)
    n = sum(counts.values())
    index = {c: i for i, c in enumerate(order)}
    if n < 2:
        return float("nan")

    def delta(a, b):
        ia, ib = index[a], index[b]
        if ia == ib:
            return 0.0
        lo, hi = sorted((ia, ib))
        value = 0.5 * counts[order[lo]] + 0.5 * counts[order[hi]]
        for k in range(lo + 1, hi):
            value += counts[order[k]]
        return value * value

    observed = 0.0
    for row in items:
        row = [x for x in row if x is not None]
        m = len(row)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i != j:
                    observed += delta(row[i], row[j]) / (m - 1)
    do = observed / n
    expected = 0.0
    for a, na in counts.items():
        for b, nb in counts.items():
            expected += na * nb * delta(a, b)
    de = expected / (n * (n - 1))
    return 1.0 - do / de if de > 0 else float("nan")

def percentile_ci(values):
    values = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))

def holm_adjust(values):
    p = np.asarray(values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    sorted_p = p[order]
    adjusted_sorted = np.empty(m, dtype=float)
    running = 0.0
    for i, value in enumerate(sorted_p):
        candidate = (m - i) * value
        running = max(running, candidate)
        adjusted_sorted[i] = min(1.0, running)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted

def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(path, index=False)
        return
    rows = list(rows)
    pd.DataFrame(rows).to_csv(path, index=False)

def q(value, digits=4):
    if value is None:
        return ""
    try:
        if math.isnan(float(value)):
            return ""
    except Exception:
        pass
    return round(float(value), digits)

def model_common_ids(human_ids, models):
    common = set(human_ids)
    for _, table in models:
        common &= set(table.index)
    return sorted(common)

def portal_aliases(values):
    unique = sorted({str(v) for v in values})
    if len(unique) > 26:
        raise RuntimeError("Too many portal values")
    return {value: f"Portal {chr(65 + i)}" for i, value in enumerate(unique)}

def mode_value(values):
    values = [v for v in values if v is not None and not pd.isna(v)]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]
