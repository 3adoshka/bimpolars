from __future__ import annotations
from pathlib import Path
import httpx, polars as pl
from bimpolars.frame import BimDataFrame

BSDD_CLASS_ENDPOINT = "https://api.bsdd.buildingsmart.org/api/Class/v1"

def validate_bsdd_uris(bdf: BimDataFrame, uri_col: str = "bsdd_uri", cache_path: str | Path = ".bsdd_cache.parquet") -> BimDataFrame:
    if uri_col not in bdf.frame.columns:
        return BimDataFrame(bdf.frame.with_columns(pl.lit(True).alias("bsdd_pass"), pl.lit(None, dtype=pl.String).alias("bsdd_name")))
    cache_file = Path(cache_path)
    cache: dict[str, str | None] = {}
    if cache_file.exists():
        cdf = pl.read_parquet(cache_file)
        cache = dict(zip(cdf["uri"].to_list(), cdf["name"].to_list()))
    uris = [u for u in bdf.frame[uri_col].drop_nulls().unique().to_list() if u not in cache]
    if uris:
        with httpx.Client(timeout=10.0) as client:
            for u in uris:
                try:
                    r = client.get(BSDD_CLASS_ENDPOINT, params={"Uri": u})
                    cache[u] = r.json().get("name") if r.status_code == 200 else None
                except httpx.HTTPError:
                    cache[u] = None
        pl.DataFrame({"uri": list(cache.keys()), "name": list(cache.values())}).write_parquet(cache_file)
    lookup = pl.DataFrame({"uri": list(cache.keys()), "bsdd_name": list(cache.values())}) if cache else pl.DataFrame(schema={"uri": pl.String, "bsdd_name": pl.String})
    joined = bdf.frame.with_columns(pl.col(uri_col).cast(pl.String)).join(lookup, left_on=uri_col, right_on="uri", how="left").with_columns(
        (pl.col(uri_col).is_null() | pl.col("bsdd_name").is_not_null()).alias("bsdd_pass")
    )
    return BimDataFrame(joined, bdf.crs)
