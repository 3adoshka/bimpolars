from __future__ import annotations
import time, zipfile
from pathlib import Path
import polars as pl, pytest
from bimpolars.cli import main as cli_main
from bimpolars.erp import build_boq, pull_4d5d_status, push_boq
from bimpolars.frame import BimDataFrame
from bimpolars.standards import audit_iso19650, export_bcf, validate_bsdd_uris

def test_boq_qto_and_fallback() -> None:
    df = pl.DataFrame({
        "id": ["w1", "b1"],
        "class": ["IfcWall", "IfcBeam"],
        "properties": [{"Qto_WallBaseQuantities": {"NetVolume": 10.0, "NetArea": 25.0}}, {"Qto_WallBaseQuantities": {"NetVolume": None, "NetArea": None}}],
        "bbox": [{"xmin": 0.0, "ymin": 0.0, "zmin": 0.0, "xmax": 1.0, "ymax": 1.0, "zmax": 1.0}, {"xmin": 0.0, "ymin": 0.0, "zmin": 0.0, "xmax": 2.0, "ymax": 0.5, "zmax": 0.5}],
    })
    boq = build_boq(BimDataFrame(df, "EPSG:4326"))
    assert boq.filter(pl.col("class") == "IfcWall")["quantity_source"].to_list() == ["Qto"]
    assert boq.filter(pl.col("class") == "IfcBeam")["quantity_source"].to_list() == ["bbox_fallback"]

def test_sync_and_4d5d_dedup(tmp_path: Path) -> None:
    bdf = BimDataFrame(pl.DataFrame({"id": ["g1", "g2"], "class": ["IfcWall", "IfcSlab"]}), "EPSG:4326")
    out = push_boq(bdf.frame, tmp_path / "boq.json")
    assert out.exists()
    merged = pull_4d5d_status(bdf, pl.DataFrame({"id": ["g1", "g1"], "pct_complete": [25, 90]}))
    assert merged.frame["pct_complete"].to_list() == [90, None]
    with pytest.raises(ValueError):
        pull_4d5d_status(bdf, pl.DataFrame({"wrong_key": ["g1"]}))

def test_iso19650_bcf_and_bsdd(tmp_path: Path) -> None:
    df = pl.DataFrame({
        "id": ["2O2Fr$t4X7Zf8NOew3FLOH", "3O2Fr$t4X7Zf8NOew3FLOH"],
        "name": ["PRJ-ARC-W01", "BAD"],
        "class": ["IfcWall", "IfcWall"],
        "cde_status": ["S3", "S0"],
        "bsdd_uri": ["https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3/class/IfcWall", None],
        "properties": [{"Pset_WallCommon": {"FireRating": "REI120"}}, {"Pset_WallCommon": {"FireRating": None}}],
        "bbox": [{"xmin": 0.0, "ymin": 0.0, "zmin": 0.0, "xmax": 3.0, "ymax": 0.3, "zmax": 3.0}, {"xmin": 0.0, "ymin": 0.0, "zmin": 0.0, "xmax": 3.0, "ymax": 0.3, "zmax": 3.0}],
    })
    audited = audit_iso19650(BimDataFrame(df, "EPSG:4326"), {"name_regex": "^PRJ-", "allowed_cde_codes": ["S3"], "required_properties": {"IfcWall": {"Pset_WallCommon.FireRating": {"regex": "^REI"}}}})
    assert audited.frame["iso19650_pass"].to_list() == [True, False]
    bcf_file = export_bcf(audited, tmp_path / "issues.bcfzip")
    assert any(n.endswith(".bcfv") for n in zipfile.ZipFile(bcf_file).namelist())
    cp = tmp_path / "bsdd.parquet"
    pl.DataFrame({"uri": ["https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3/class/IfcWall"], "valid": [True], "name": ["Wall"], "cached_at": [time.time()]}).write_parquet(cp)
    bsdd_out = validate_bsdd_uris(audited, cache_path=cp, offline=True)
    assert bsdd_out.frame["bsdd_valid"].to_list() == [True, False]
