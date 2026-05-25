"""
WMD Plotter — FastAPI Backend

Endpoints:
  GET  /                        → Serve frontend HTML
  GET  /api/chemicals           → Full chemical database JSON
  GET  /api/weather?lat=&lon=   → Current weather + stability class
  POST /api/plume               → Compute plume (GeoJSON + stats)
  GET  /kml/live.kml            → Live KML (uses last computed plume)
  GET  /kml/network.kml         → KML NetworkLink to /kml/live.kml
  GET  /kml/download            → Static KML download (last plume)
"""

import os
import sys
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ── local imports ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from chemicals import CHEMICALS, get_chemical, get_thresholds
from dispersion import compute_all_contours, determine_stability_class
from weather import fetch_weather
from kml_gen import build_combined_kml, build_network_link_kml
from blast import EXPLOSIVES, compute_blast_zones

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="WMD Plotter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ── Shared overlay state (all tools write here; KML endpoints read it) ───────
# Adding a new tool: store its result under a new key and add a folder
# builder to kml_gen._FOLDER_BUILDERS. Nothing else needs to change.
_overlay_state: dict = {
    "plume": {},
    "blast": {},
}


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response models
# ─────────────────────────────────────────────────────────────────────────────

class BlastRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    explosive_id: str = "tnt"
    weight_kg: float = Field(..., gt=0, le=500_000)


class PlumeRequest(BaseModel):
    # Incident location
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

    # Chemical
    chemical_id: str
    use_aegl: bool = True           # True = AEGL, False = ERPG

    # Release parameters
    release_rate_kg_min: float = Field(default=1.0, gt=0, le=10_000)
    release_height_m: float = Field(default=0.0, ge=0, le=500)

    # Weather (if None, fetch from Open-Meteo)
    wind_speed_ms: Optional[float] = Field(default=None, ge=0)
    wind_dir_from_deg: Optional[float] = Field(default=None, ge=0, lt=360)
    stability_class: Optional[str] = Field(default=None, pattern="^[A-Fa-f]$")

    # Override weather fetch
    manual_weather: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(), status_code=200)
    return HTMLResponse(content="<h1>WMD Plotter</h1><p>Frontend not found.</p>")


@app.get("/api/chemicals")
async def list_chemicals():
    """Return full chemical database."""
    return JSONResponse(content={"chemicals": CHEMICALS, "count": len(CHEMICALS)})


@app.get("/api/weather")
async def get_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Fetch current weather + stability class for a location."""
    try:
        wx = await fetch_weather(lat, lon)
        return JSONResponse(content=wx)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")


@app.post("/api/plume")
async def compute_plume(req: PlumeRequest, request: Request):
    """
    Compute Gaussian plume contours.
    Returns GeoJSON FeatureCollection + stats for each threshold level.
    Caches result for /kml/live.kml.
    """
    chem = get_chemical(req.chemical_id)
    if not chem:
        raise HTTPException(status_code=404, detail=f"Chemical '{req.chemical_id}' not found.")

    # ── Weather ──────────────────────────────────────────────────────────────
    if req.manual_weather and req.wind_speed_ms is not None and req.wind_dir_from_deg is not None:
        wind_ms     = req.wind_speed_ms
        wind_from   = req.wind_dir_from_deg
        stability   = (req.stability_class or "D").upper()
        wx_data     = {
            "wind_speed_ms": wind_ms,
            "wind_speed_mph": round(wind_ms * 2.237, 1),
            "wind_dir_from_deg": wind_from,
            "wind_dir_label": "Manual",
            "stability_class": stability,
            "stability_desc": f"{stability} — Manual override",
            "source": "Manual",
        }
    else:
        try:
            wx_data = await fetch_weather(req.lat, req.lon)
        except Exception as e:
            # Fallback to neutral conditions
            wx_data = {
                "wind_speed_ms": 3.0,
                "wind_speed_mph": 6.7,
                "wind_dir_from_deg": 270.0,
                "wind_dir_label": "W",
                "stability_class": "D",
                "stability_desc": "D — Neutral (fallback)",
                "source": "Fallback",
                "error": str(e),
            }
        wind_ms   = wx_data["wind_speed_ms"]
        wind_from = wx_data["wind_dir_from_deg"]
        stability = wx_data["stability_class"]

        # Override wind/stability if user provided them
        if req.wind_speed_ms is not None:
            wind_ms = req.wind_speed_ms
        if req.wind_dir_from_deg is not None:
            wind_from = req.wind_dir_from_deg
        if req.stability_class:
            stability = req.stability_class.upper()

    # ── Thresholds & dispersion ───────────────────────────────────────────────
    thresholds = get_thresholds(chem, use_aegl=req.use_aegl)
    if not thresholds:
        raise HTTPException(status_code=422, detail="No hazard thresholds available for this chemical.")

    Q_gs = req.release_rate_kg_min * 1000 / 60.0   # kg/min → g/s

    contours = compute_all_contours(
        Q_gs=Q_gs,
        u_ms=wind_ms,
        stability=stability,
        mw=chem["mw"],
        thresholds=thresholds,
        source_lat=req.lat,
        source_lon=req.lon,
        wind_from_deg=wind_from,
        H_m=req.release_height_m,
    )

    # ── Build GeoJSON response ────────────────────────────────────────────────
    features = []

    # Source point
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [req.lon, req.lat]},
        "properties": {
            "type": "source",
            "chemical": chem["name"],
            "formula": chem["formula"],
            "release_rate_gs": Q_gs,
            "release_height_m": req.release_height_m,
        },
    })

    stats = {}
    for level, info in contours.items():
        latlon = info.get("latlon", [])
        if latlon:
            coords = [[lon, lat] for lat, lon in latlon]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type": "plume_contour",
                    "level": level,
                    "label": info["label"],
                    "color": info["color"],
                    "threshold_ppm": info["threshold_ppm"],
                    "max_downwind_m": round(info["max_downwind_m"], 1),
                    "max_downwind_km": round(info["max_downwind_m"] / 1000, 3),
                    "max_width_m": round(info["max_width_m"], 1),
                    "max_width_km": round(info["max_width_m"] / 1000, 3),
                },
            })
        stats[level] = {
            "label": info["label"],
            "threshold_ppm": info["threshold_ppm"],
            "max_downwind_km": round(info.get("max_downwind_m", 0) / 1000, 3),
            "max_width_km": round(info.get("max_width_m", 0) / 1000, 3),
            "has_contour": bool(latlon),
        }

    geojson = {"type": "FeatureCollection", "features": features}

    # ── Cache for KML endpoint ────────────────────────────────────────────────
    base_url = str(request.base_url).rstrip("/")
    global _overlay_state
    _overlay_state["plume"] = {
        "source_lat": req.lat,
        "source_lon": req.lon,
        "chemical_name": chem["name"],
        "contours": contours,
        "wind_speed_ms": wind_ms,
        "wind_dir_from_deg": wind_from,
        "stability_class": stability,
        "release_rate_gs": Q_gs,
        "release_height_m": req.release_height_m,
        "weather_desc": wx_data.get("weather_desc", ""),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content={
        "geojson": geojson,
        "stats": stats,
        "weather": wx_data,
        "model": {
            "type": "Gaussian (Pasquill-Gifford)",
            "stability_class": stability,
            "wind_speed_ms": wind_ms,
            "wind_dir_from_deg": wind_from,
            "Q_gs": Q_gs,
            "H_m": req.release_height_m,
        },
        "kml_links": {
            "network_link": f"{base_url}/kml/network.kml",
            "live_kml": f"{base_url}/kml/live.kml",
            "download": f"{base_url}/kml/download",
        },
    })


@app.get("/kml/live.kml")
async def live_kml():
    """Combined live KML of all active overlays. Polled by Google Earth NetworkLink."""
    if not any(_overlay_state.values()):
        raise HTTPException(status_code=404, detail="No overlays computed yet. Run a scenario first.")
    return Response(
        content=build_combined_kml(_overlay_state),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/kml/network.kml")
async def network_link_kml(request: Request, interval: int = Query(default=30, ge=5, le=300)):
    """
    Serve a KML NetworkLink document.
    Open in Google Earth — it will auto-refresh every `interval` seconds.
    """
    base_url = str(request.base_url).rstrip("/")
    live_url = f"{base_url}/kml/live.kml"
    kml_content = build_network_link_kml(live_url, refresh_interval_seconds=interval)
    return Response(
        content=kml_content,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": 'attachment; filename="wmd_plotter_network.kml"'},
    )


@app.get("/kml/download")
async def download_kml():
    """Download a static KML snapshot of all active overlays."""
    if not any(_overlay_state.values()):
        raise HTTPException(status_code=404, detail="No overlays computed yet.")
    active = [k for k, v in _overlay_state.items() if v]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"wmd_{'_'.join(active)}_{ts}.kml"
    return Response(
        content=build_combined_kml(_overlay_state),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/explosives")
async def list_explosives():
    """Return explosive types with TNT equivalency factors."""
    return JSONResponse(content={"explosives": EXPLOSIVES})


@app.post("/api/blast")
async def compute_blast(req: BlastRequest):
    """Compute blast overpressure damage zones (Brode/Hopkinson-Cranz model)."""
    from blast import EXPLOSIVES as _EXPLOSIVES
    result = compute_blast_zones(
        lat=req.lat,
        lon=req.lon,
        weight_kg=req.weight_kg,
        explosive_id=req.explosive_id,
    )

    # Cache for unified KML export
    exp = next((e for e in _EXPLOSIVES if e["id"] == req.explosive_id), {})
    global _overlay_state
    _overlay_state["blast"] = {
        "source_lat":    req.lat,
        "source_lon":    req.lon,
        "explosive_id":  req.explosive_id,
        "explosive_name": exp.get("name", req.explosive_id),
        "weight_kg":     req.weight_kg,
        "W_tnt_kg":      result["W_tnt_kg"],
        "zones": [
            {
                **feat["properties"],
                # KML builder needs [lon, lat] ring stored as "lonlat"
                "lonlat": feat["geometry"]["coordinates"][0],
            }
            for feat in result["geojson"]["features"]
            if feat["properties"]["type"] == "blast_zone"
        ],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=result)


@app.get("/api/health")
async def health():
    return {"status": "ok", "active_overlays": {k: bool(v) for k, v in _overlay_state.items()}}


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
