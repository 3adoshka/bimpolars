from __future__ import annotations
import time
from pathlib import Path
import httpx, polars as pl
from bimpolars.frame import BimDataFrame

BSDD_CLASS_ENDPOINT = "https://api.bsdd.buildingsmart.org/api/Classification/v1"

def _query_bsdd_api(uri: str, max_retries: int = 3) -> tuple[bool, str | None]:
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(BSDD_CLASS_ENDPOINT, params={"Uri": uri})
                if r.status_code == 200:
                    data = r.json()
                    return True, str(data.get("name") or data.get("code") or "")
                if r.status_code in (400, 404):
                    return False, None
        except httpx.HTTPError:
            if attempt == max_retries - 1:
                return False, None
            time.sleep(0.4 * (2 ** attempt))
    return False, None

def validate_bsdd_uris(bdf: BimDataFrame, uri_col: str = "bsdd_uri", cache_path: str | Path = ".bsdd_cache.parquet", ttl_hours: float = 168.0, offline: bool = False) -> BimDataFrame:
    if uri_col not in bdf.frame.columns:
        return BimDataFrame(bdf.frame.with_columns(pl.lit(False).alias("bsdd_valid"), pl.lit(None, dtype=pl.String).alias("bsdd_name")), bdf.crs)
    now, max_age = time.time(), ttl_hours * 3600.0
    cp = Path(cache_path)
    cache = pl.read_parquet(cp).filter((pl.lit(now) - pl.col("cached_at")) < max_age) if cp.exists() else pl.DataFrame({"uri": pl.Series([], dtype=pl.String), "valid": pl.Series([], dtype=pl.Boolean), "name": pl.Series([], dtype=pl.String), "cached_at": pl.Series([], dtype=pl.Float64)})
    uris = bdf.frame[uri_col].drop_nulls().cast(pl.String).unique().to_list()
    missing = [u for u in uris if u not in cache["uri"].to_list()]
    if missing and not offline:
        rows = []
        for u in missing:
            ok, name = _query_bsdd_api(u)
            rows.append({"uri": u, "valid": ok, "name": name, "cached_at": now})
        cache = pl.concat([cache, pl.DataFrame(rows, schema=cache.schema)], how="vertical")
        cp.parent.mkdir(parents=True, exist_ok=True)
        cache.write_parquet(cp)
    lookup = cache.select(["uri", "valid", "name"]).rename({"uri": uri_col, "valid": "bsdd_valid", "name": "bsdd_name"})
    joined = bdf.frame.with_columns(pl.col(uri_col).cast(pl.String)).join(lookup, on=uri_col, how="left").with_columns(pl.col("bsdd_valid").fill_null(False))
    return BimDataFrame(joined, bdf.crs)
