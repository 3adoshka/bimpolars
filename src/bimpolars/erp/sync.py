from __future__ import annotations
import json
from pathlib import Path
import httpx, polars as pl
from bimpolars.frame import BimDataFrame

def push_boq(boq_df: pl.DataFrame, out_path: str | Path, webhook_url: str | None = None) -> Path:
    dest = Path(out_path)
    if dest.suffix.lower() == ".json":
        dest.write_text(json.dumps(boq_df.to_dicts(), indent=2))
    else:
        boq_df.write_parquet(dest)
    if webhook_url:
        with httpx.Client(timeout=15.0) as client:
            client.post(webhook_url, json={"items": boq_df.to_dicts()})
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
    joined = bdf.frame.join(sdf, on=id_col, how="left")
    return BimDataFrame(joined, bdf.crs)
