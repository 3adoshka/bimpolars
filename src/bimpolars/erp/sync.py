from __future__ import annotations
import json, os, time
from pathlib import Path
import httpx, polars as pl
from bimpolars.frame import BimDataFrame

def push_boq(boq_df: pl.DataFrame, out_path: str | Path, webhook_url: str | None = None, max_retries: int = 3) -> Path:
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if dest.suffix.lower() == ".json":
        tmp.write_text(json.dumps(boq_df.to_dicts(), indent=2))
    else:
        boq_df.write_parquet(tmp)
    tmp.replace(dest)
    url = webhook_url or os.getenv("ERP_WEBHOOK_URL")
    if url:
        payload = {"schema_version": "1.0", "row_count": len(boq_df), "items": boq_df.to_dicts()}
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.5 * (2 ** attempt))
    return dest

def pull_4d5d_status(bdf: BimDataFrame, status_source: str | Path | pl.DataFrame, id_col: str = "id") -> BimDataFrame:
    if isinstance(status_source, pl.DataFrame):
        sdf = status_source
    else:
        src = Path(status_source)
        ext = src.suffix.lower()
        if ext == ".parquet":
            sdf = pl.read_parquet(src)
        elif ext == ".csv":
            sdf = pl.read_csv(src)
        else:
            sdf = pl.DataFrame(json.loads(src.read_text()))
    if id_col not in sdf.columns:
        raise ValueError(f"4D/5D status source missing required join key: {id_col!r}")
    sdf_dedup = sdf.unique(subset=[id_col], keep="last")
    overlap = [c for c in sdf_dedup.columns if c != id_col and c in bdf.frame.columns]
    base = bdf.frame.drop(overlap) if overlap else bdf.frame
    joined = base.join(sdf_dedup, on=id_col, how="left")
    return BimDataFrame(joined, bdf.crs)
