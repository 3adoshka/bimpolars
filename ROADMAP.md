# Project Blueprint: `bimpolars` Enterprise openBIM & ERP Engine

**Repository:** `3adoshka/bimpolars` (Forked from `bedrock-engineer/bimpolars`, Apache-2.0)  
**Target Architecture:** Zero-license, columnar BIM-to-GIS & BIM-to-ERP data engineering engine compliant with buildingSMART and ISO standards.

---

## 1. Executive Objective

Extend `bimpolars`' high-speed Polars/Arrow `BimDataFrame` and ISO 19111 georeferencing core with a modular **openBIM & ISO Governance Layer (`standards/`)** and an **OpenConstructionERP Bridge (`erp/`)**. 

Instead of maintaining slow object-graph parsers or proprietary middleware, this fork wraps battle-tested `ifcopenshell` and `ifctester` primitives in vectorized Polars expressions—enabling deterministic model auditing, automated BCF issue round-tripping, bSDD semantic validation, and traceable Bill of Quantities (BOQ) generation.

---

## 2. Standards Compliance Matrix

| Standard | Scope | Engine / Implementation | Status |
| :--- | :--- | :--- | :--- |
| **IFC (ISO 16739)** | Geometry, `Psets`/`Qto`, `PredefinedType`, `IfcExtrudedAreaSolid` | `bimpolars.read_ifc` (`ifcopenshell`) | **Native (Pass)** |
| **ISO 19111 / GeoParquet** | `DerivedProjectedCRS`, `IfcMapConversion`, WKB footprints | `bimpolars.geobim` (`pyproj`, `shapely`) | **Native (Pass)** |
| **IDS (ISO 7817-1)** | XML Information Delivery Specification facet validation | `standards/ids.py` (`ifctester` $\rightarrow$ Polars) | **New Module** |
| **BCF (ISO 21597)** | `.bcfzip` issue serialization + `bbox` camera viewpoints | `standards/bcf.py` (`ifcopenshell.bcf`) | **New Module** |
| **bSDD (ISO 12006-3 / 23386)** | Classification URI & property domain verification | `standards/bsdd.py` (`httpx` + Parquet cache) | **New Module** |
| **ISO 19650-1 / -2** | CDE suitability states (`S0`–`S7`), naming & LOD gates | `standards/iso19650.py` (YAML BEP rules) | **New Module** |

---

## 3. Target Repository Structure

Isolate all internal extensions inside dedicated subpackages to preserve clean upstream syncs with `bedrock-engineer/bimpolars:main`:

```text
src/bimpolars/
├── ... (upstream core: read_ifc, geobim, lightbim, gltf, speckle)
├── standards/                  # openBIM & ISO Governance Layer
│   ├── __init__.py
│   ├── iso19650.py             # YAML BEP rule compiler (naming, Psets, geometry bounds)
│   ├── ids.py                  # ifctester -> BimDataFrame join adapter
│   ├── bcf.py                  # Failing rows + bbox centroids -> .bcfzip exporter
│   └── bsdd.py                 # buildingSMART Data Dictionary API + local cache
└── erp/                        # OpenConstructionERP Integration Layer
    ├── __init__.py
    ├── boq.py                  # Cost-code mapping & net quantity rollups
    └── sync.py                 # Push BOQ to ERP / pull 4D-5D status for 3D viewer
