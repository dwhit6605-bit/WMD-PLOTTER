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
import secrets
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Load .env from backend directory (FIRMS_MAP_KEY, etc.) — never committed to git
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException, Request, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── local imports ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from chemicals import CHEMICALS, get_chemical, get_thresholds
from dispersion import compute_all_contours, determine_stability_class
from weather import fetch_weather, fetch_asos_weather
from kml_gen import build_combined_kml, build_network_link_kml
from blast import EXPLOSIVES, compute_blast_zones
from radiation import RADIONUCLIDES, get_radionuclide, compute_radiation_contours
from bleve import FUELS, compute_bleve_zones
from population import estimate_population_impact
from tak_dp import build_tak_data_package, build_cot_xml
from erg import search_erg, get_erg_entry, compute_erg_zones
from dense_gas import compute_dense_gas_zones, list_dense_gases, get_dense_gas
from probit import compute_probit_zones
from fire_smoke import compute_fire_smoke_zones, list_fire_types
from firms import fetch_firms_hotspots
from nws_forecast import fetch_nws_forecast
from hifld import fetch_hifld_infra
from nifc import fetch_nifc_perimeters
from aegl_db import get_aegl
from db   import init_db, count_users, create_user, get_user_by_username, \
                 get_user_by_id, update_last_login, list_users, delete_user, update_password, \
                 get_setting, set_setting, \
                 list_tak_profiles, get_tak_profile, get_active_tak_profile, \
                 upsert_tak_profile, set_tak_profile_cert, set_tak_profile_admin_cert, set_active_tak_profile, delete_tak_profile
from tak_push import push_cot, push_test_point
from tak_marti import push_via_marti, push_cot_http
from auth import (
    hash_password, verify_password, create_token, decode_token,
    auth_middleware, current_user, require_admin,
    COOKIE_NAME, JWT_EXPIRE_DAYS, ALLOW_REGISTRATION, REGISTRATION_CODE,
)

APP_VERSION = "2.3.0"
BUILD_DATE  = "2026-05-27"   # v2.3.0: AEGL table, plume animation, print report, multi-incident

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="WMD Plotter API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth_middleware)


@app.on_event("startup")
async def startup():
    init_db()
    if count_users() == 0:
        admin_pass = secrets.token_urlsafe(12)
        create_user("admin", hash_password(admin_pass), role="admin")
        print("\n" + "=" * 60)
        print("  INITIAL ADMIN ACCOUNT CREATED")
        print(f"  Username : admin")
        print(f"  Password : {admin_pass}")
        print("  Change this password after first login!")
        print("=" * 60 + "\n")

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
    "radiation": {},
    "bleve": {},
    "erg": {},
    "dense_gas": {},
    "fire_smoke": {},
    "population": {},
    "infra": {},
}


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response models
# ─────────────────────────────────────────────────────────────────────────────

class BleveRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    fuel_id: str = "propane"
    mass_kg: float = Field(..., gt=0, le=500_000)


class PopulationRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    zones: list[dict]   # [{"level": str, "label": str, "color": str, "latlon": [[lat,lon],...]}]


class RadiationRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radionuclide_id: str
    release_rate_ci_min: float = Field(..., gt=0, le=1_000_000)
    release_height_m: float = Field(default=0.0, ge=0, le=500)
    wind_speed_ms: Optional[float] = Field(default=None, ge=0)
    wind_dir_from_deg: Optional[float] = Field(default=None, ge=0, lt=360)
    stability_class: Optional[str] = Field(default=None, pattern="^[A-Fa-f]$")
    manual_weather: bool = False


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


@app.get("/sw.js")
async def service_worker():
    """Service worker must be served from root scope, not /static/."""
    sw_path = FRONTEND_DIR / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="sw.js not found")
    return Response(
        content=sw_path.read_text(),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )


@app.get("/manifest.json")
async def web_manifest():
    """PWA web app manifest."""
    manifest_path = FRONTEND_DIR / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    return Response(
        content=manifest_path.read_text(),
        media_type="application/manifest+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ── Auth pages ────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Already logged in? Redirect to app
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            decode_token(token)
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/", status_code=302)
        except Exception:
            pass
    return HTMLResponse((FRONTEND_DIR / "login.html").read_text())


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    return HTMLResponse((FRONTEND_DIR / "register.html").read_text())


# ── Auth API ──────────────────────────────────────────────────────────────────

@app.post("/auth/login")
async def auth_login(request: Request):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    update_last_login(user["id"])
    token = create_token(user["id"], user["username"], user["role"])

    is_https = request.url.scheme == "https"
    resp = JSONResponse({"username": user["username"], "role": user["role"]})
    resp.set_cookie(
        COOKIE_NAME, token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=JWT_EXPIRE_DAYS * 24 * 3600,
    )
    return resp


@app.post("/auth/logout")
async def auth_logout():
    resp = JSONResponse({"status": "logged out"})
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.post("/auth/register")
async def auth_register(request: Request):
    body = await request.json()
    username  = (body.get("username") or "").strip()
    password  = body.get("password") or ""
    reg_code  = (body.get("registration_code") or "").strip()

    # Determine if the requester is an admin (already logged in)
    requester = getattr(request.state, "user", None)
    is_admin  = requester and requester.get("role") == "admin"

    if not is_admin:
        if not ALLOW_REGISTRATION:
            raise HTTPException(status_code=403, detail="Registration is disabled. Contact your administrator.")
        if REGISTRATION_CODE and reg_code != REGISTRATION_CODE:
            raise HTTPException(status_code=403, detail="Invalid registration code.")

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(username) > 32:
        raise HTTPException(status_code=400, detail="Username must be 32 characters or less.")
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="That username is already taken.")

    role = "user"
    user = create_user(username, hash_password(password), role)
    return JSONResponse({"username": user["username"], "role": user["role"]}, status_code=201)


@app.get("/auth/me")
async def auth_me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse(user)


@app.get("/auth/registration-status")
async def registration_status(request: Request):
    """Tells the frontend whether the register page should show the form."""
    requester = getattr(request.state, "user", None)
    is_admin  = requester and requester.get("role") == "admin"
    return JSONResponse({
        "open":          ALLOW_REGISTRATION or bool(is_admin),
        "code_required": bool(REGISTRATION_CODE) and not is_admin,
        "admin_session": bool(is_admin),
    })


# ── Admin: user management ────────────────────────────────────────────────────

@app.get("/admin/users")
async def admin_users_page(user: dict = Depends(require_admin)):
    return HTMLResponse((FRONTEND_DIR / "admin_users.html").read_text())


@app.get("/api/admin/users")
async def api_list_users(user: dict = Depends(require_admin)):
    return JSONResponse({"users": list_users()})


@app.post("/api/admin/users")
async def api_create_user(request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role     = body.get("role", "user")

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'.")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already taken.")

    user = create_user(username, hash_password(password), role)
    return JSONResponse({"username": user["username"], "role": user["role"]}, status_code=201)


@app.delete("/api/admin/users/{user_id}")
async def api_delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if str(user_id) == str(admin.get("sub")):
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    return JSONResponse({"status": "deleted"})


@app.post("/api/admin/users/{user_id}/password")
async def api_reset_password(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    password = body.get("password") or ""
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    update_password(user_id, hash_password(password))
    return JSONResponse({"status": "updated"})


@app.get("/api/version")
async def get_version():
    return JSONResponse(content={
        "version": APP_VERSION,
        "build_date": BUILD_DATE,
        "name": "WHITWERX Model Display (WMD)",
    })


@app.get("/api/chemicals")
async def list_chemicals():
    """Return full chemical database."""
    return JSONResponse(content={"chemicals": CHEMICALS, "count": len(CHEMICALS)})


@app.get("/api/weather")
async def get_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Fetch current weather + stability class for a location.
    Tries Open-Meteo first; falls back to NWS hourly forecast if Open-Meteo fails.
    """
    # Primary: Open-Meteo (global, no key needed)
    try:
        wx = await fetch_weather(lat, lon)
        return JSONResponse(content=wx)
    except Exception:
        pass

    # Fallback: NWS hourly forecast (US only) — return the current hour
    try:
        periods = await fetch_nws_forecast(lat, lon)
        if not periods:
            raise ValueError("NWS returned no periods")
        p = periods[0]
        from dispersion import determine_stability_class
        import math
        from weather import _estimate_solar_elevation
        solar_el = _estimate_solar_elevation(lat, lon)
        wx_nws = {
            "wind_speed_ms":    p["wind_speed_ms"],
            "wind_speed_mph":   p["wind_speed_mph"],
            "wind_dir_from_deg": p["wind_dir_from_deg"],
            "wind_dir_label":   p["wind_dir_label"],
            "wind_gusts_ms":    p["wind_speed_ms"],
            "wind_gusts_mph":   p["wind_speed_mph"],
            "cloud_cover_pct":  p.get("cloud_cover_pct", 50),
            "temp_f":           p.get("temp_f", 70),
            "temp_c":           round((p.get("temp_f", 70) - 32) * 5 / 9, 1),
            "humidity_pct":     50,
            "is_day":           p.get("is_daytime", True),
            "weather_code":     0,
            "weather_desc":     p.get("short_forecast", ""),
            "solar_elevation_deg": round(solar_el, 1),
            "stability_class":  p["stability_class"],
            "stability_desc":   p["stability_desc"],
            "source":           "NWS Forecast (Open-Meteo unavailable)",
            "fetched_at_utc":   p["startTime"],
        }
        return JSONResponse(content=wx_nws)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed (both Open-Meteo and NWS): {e}")


@app.get("/api/weather/asos")
async def get_asos_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """
    Fetch the latest ASOS/AWOS surface observation from the nearest NWS
    observation station (US only — uses api.weather.gov, no key required).
    Returns wind speed/direction, temperature, cloud cover, stability class,
    station ID/name/distance, observation age, and raw METAR string.
    """
    try:
        data = await fetch_asos_weather(lat, lon)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ASOS fetch failed: {e}")


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


@app.get("/api/aegl/{chem_id}")
async def get_aegl_data(chem_id: str):
    """Return multi-time-point AEGL values (10min, 60min, 8hr) for a chemical."""
    data = get_aegl(chem_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No AEGL data for '{chem_id}'")
    return JSONResponse(content={"chem_id": chem_id, "aegl": data})


@app.post("/api/plume/animate")
async def animate_plume(req: PlumeRequest):
    """
    Compute plume animation frames at t=0,5,10,15,20,30,45,60,90,120 minutes.
    Each frame clips the steady-state plume to the distance travelled by the
    plume front at that elapsed time (wind_speed × t).
    Returns an array of GeoJSON FeatureCollections, one per time step.
    """
    chem = get_chemical(req.chemical_id)
    if not chem:
        raise HTTPException(status_code=404, detail=f"Chemical '{req.chemical_id}' not found.")

    if req.manual_weather and req.wind_speed_ms is not None and req.wind_dir_from_deg is not None:
        wind_ms   = req.wind_speed_ms
        wind_from = req.wind_dir_from_deg
        stability = (req.stability_class or "D").upper()
    else:
        try:
            wx = await fetch_weather(req.lat, req.lon)
        except Exception:
            wx = {"wind_speed_ms": 3.0, "wind_dir_from_deg": 270.0, "stability_class": "D"}
        wind_ms   = req.wind_speed_ms   or wx["wind_speed_ms"]
        wind_from = req.wind_dir_from_deg or wx["wind_dir_from_deg"]
        stability = (req.stability_class or wx["stability_class"]).upper()

    thresholds = get_thresholds(chem, use_aegl=req.use_aegl)
    if not thresholds:
        raise HTTPException(status_code=422, detail="No hazard thresholds for this chemical.")

    Q_gs = req.release_rate_kg_min * 1000 / 60.0

    time_steps = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120]
    frames = []

    for t_min in time_steps:
        x_front = max(wind_ms * t_min * 60, 50.0)   # metres; min 50m so source area shown
        contours = compute_all_contours(
            Q_gs=Q_gs, u_ms=wind_ms, stability=stability, mw=chem["mw"],
            thresholds=thresholds, source_lat=req.lat, source_lon=req.lon,
            wind_from_deg=wind_from, H_m=req.release_height_m,
            x_max_clip=x_front,
        )
        features = []
        for level, info in contours.items():
            latlon = info.get("latlon", [])
            if latlon:
                coords = [[ln, lt] for lt, ln in latlon]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "level": level, "label": info["label"],
                        "color": info["color"],
                        "threshold_ppm": info["threshold_ppm"],
                        "max_downwind_km": round(info["max_downwind_m"] / 1000, 3),
                    },
                })
        frames.append({
            "time_min": t_min,
            "x_front_m": round(x_front, 0),
            "features": features,
        })

    return JSONResponse(content={
        "frames": frames,
        "wind_speed_ms": wind_ms,
        "wind_from_deg": wind_from,
        "stability": stability,
        "chemical": chem["name"],
        "total_time_steps": len(time_steps),
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


@app.delete("/api/overlay/{tool_id}")
async def clear_overlay(tool_id: str):
    """Clear a single tool's overlay from server state (called when the user closes a tool panel)."""
    if tool_id not in _overlay_state:
        raise HTTPException(status_code=404, detail=f"Unknown overlay: {tool_id}")
    _overlay_state[tool_id] = {}
    return {"status": "cleared", "tool": tool_id}


@app.delete("/api/overlay")
async def clear_all_overlays():
    """Clear all overlays (called on full scenario reset)."""
    for key in _overlay_state:
        _overlay_state[key] = {}
    return {"status": "cleared"}


@app.get("/export/tak-dp")
async def export_tak_data_package(tools: Optional[str] = Query(default=None)):
    """Download a TAK Data Package (.zip) for import into ATAK/WinTAK/iTAK.

    Optional ?tools=plume,blast query param restricts which overlays are included.
    If omitted, all non-empty overlays are included (legacy behaviour).
    """
    # Determine which overlays to export
    if tools:
        requested = [t.strip() for t in tools.split(",") if t.strip()]
        export_state = {k: v for k, v in _overlay_state.items() if k in requested and v}
    else:
        export_state = {k: v for k, v in _overlay_state.items() if v}

    if not export_state:
        raise HTTPException(status_code=404, detail="No overlays computed yet.")

    active = list(export_state.keys())
    kml_bytes = build_combined_kml(export_state).encode("utf-8")
    zip_bytes, filename = build_tak_data_package(kml_bytes, active)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
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


@app.get("/api/fuels")
async def list_fuels():
    """Return BLEVE fuel database."""
    return JSONResponse(content={"fuels": FUELS})


@app.post("/api/bleve")
async def compute_bleve(req: BleveRequest):
    """Compute BLEVE fireball thermal damage zones (Roberts 1982 model)."""
    result = compute_bleve_zones(
        lat=req.lat, lon=req.lon, mass_kg=req.mass_kg, fuel_id=req.fuel_id
    )

    fuel = next((f for f in FUELS if f["id"] == req.fuel_id), {})
    global _overlay_state
    _overlay_state["bleve"] = {
        "source_lat":  req.lat,
        "source_lon":  req.lon,
        "fuel_id":     req.fuel_id,
        "fuel_name":   fuel.get("name", req.fuel_id),
        "mass_kg":     req.mass_kg,
        "fireball":    result["fireball"],
        "zones": [
            {
                **feat["properties"],
                "lonlat": feat["geometry"]["coordinates"][0],
            }
            for feat in result["geojson"]["features"]
            if feat["properties"]["type"] == "bleve_zone"
        ],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(content=result)


@app.post("/api/population")
async def compute_population(req: PopulationRequest):
    """
    Estimate population exposure within each hazard zone.
    Uses US Census ACS 5-year county density (uniform distribution assumption).
    Caches result (with zone geometries) for KML export.
    """
    try:
        result = await estimate_population_impact(req.lat, req.lon, req.zones)

        # Merge latlon from request zones back into results for KML export
        zones_with_geo = [
            {**res_z, "latlon": req_z.get("latlon", [])}
            for req_z, res_z in zip(req.zones, result["zones"])
        ]
        global _overlay_state
        _overlay_state["population"] = {
            "source_lat":          req.lat,
            "source_lon":          req.lon,
            "county_name":         result["county_name"],
            "pop_density_per_km2": result["pop_density_per_km2"],
            "data_source":         result["data_source"],
            "zones":               zones_with_geo,
            "computed_at":         datetime.now(timezone.utc).isoformat(),
        }

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Population estimate failed: {e}")


@app.get("/api/radionuclides")
async def list_radionuclides():
    """Return radionuclide database with cloudshine DCF values."""
    return JSONResponse(content={"radionuclides": RADIONUCLIDES})


@app.post("/api/radiation")
async def compute_radiation(req: RadiationRequest, request: Request):
    """
    Compute radiological dose rate contours (Gaussian plume, cloudshine pathway).
    Returns GeoJSON FeatureCollection + stats for each dose zone.
    """
    nuclide = get_radionuclide(req.radionuclide_id)
    if not nuclide:
        raise HTTPException(status_code=404, detail=f"Radionuclide '{req.radionuclide_id}' not found.")

    # ── Weather ──────────────────────────────────────────────────────────────
    if req.manual_weather and req.wind_speed_ms is not None and req.wind_dir_from_deg is not None:
        wind_ms   = req.wind_speed_ms
        wind_from = req.wind_dir_from_deg
        stability = (req.stability_class or "D").upper()
        wx_data   = {
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

        if req.wind_speed_ms is not None:
            wind_ms = req.wind_speed_ms
        if req.wind_dir_from_deg is not None:
            wind_from = req.wind_dir_from_deg
        if req.stability_class:
            stability = req.stability_class.upper()

    # ── Compute ───────────────────────────────────────────────────────────────
    Q_ci_s = req.release_rate_ci_min / 60.0   # Ci/min → Ci/s

    contours = compute_radiation_contours(
        Q_ci_s=Q_ci_s,
        u_ms=wind_ms,
        stability=stability,
        dcf_cloud=nuclide["dcf_cloud"],
        source_lat=req.lat,
        source_lon=req.lon,
        wind_from_deg=wind_from,
        H_m=req.release_height_m,
    )

    # ── GeoJSON response ──────────────────────────────────────────────────────
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [req.lon, req.lat]},
        "properties": {
            "type": "rad_source",
            "radionuclide": nuclide["name"],
            "symbol": nuclide["symbol"],
            "release_rate_ci_s": Q_ci_s,
            "release_height_m": req.release_height_m,
        },
    }]

    stats = {}
    for level, info in contours.items():
        latlon = info.get("latlon", [])
        if latlon:
            coords = [[lon, lat] for lat, lon in latlon]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "type": "rad_contour",
                    "level": level,
                    "label": info["label"],
                    "color": info["color"],
                    "dose_msvhr": info["dose_msvhr"],
                    "desc": info["desc"],
                    "max_downwind_m": round(info["max_downwind_m"], 1),
                    "max_downwind_km": round(info["max_downwind_m"] / 1000, 3),
                    "max_width_m": round(info["max_width_m"], 1),
                    "max_width_km": round(info["max_width_m"] / 1000, 3),
                },
            })
        stats[level] = {
            "label": info["label"],
            "dose_msvhr": info["dose_msvhr"],
            "color": info["color"],
            "desc": info["desc"],
            "max_downwind_km": round(info.get("max_downwind_m", 0) / 1000, 3),
            "max_width_km": round(info.get("max_width_m", 0) / 1000, 3),
            "has_contour": bool(latlon),
        }

    geojson = {"type": "FeatureCollection", "features": features}

    # ── Cache for KML ─────────────────────────────────────────────────────────
    global _overlay_state
    _overlay_state["radiation"] = {
        "source_lat": req.lat,
        "source_lon": req.lon,
        "radionuclide_name": nuclide["name"],
        "radionuclide_symbol": nuclide["symbol"],
        "dcf_cloud": nuclide["dcf_cloud"],
        "release_rate_ci_s": Q_ci_s,
        "release_height_m": req.release_height_m,
        "wind_speed_ms": wind_ms,
        "wind_dir_from_deg": wind_from,
        "stability_class": stability,
        "contours": contours,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(content={
        "geojson": geojson,
        "stats": stats,
        "weather": wx_data,
        "model": {
            "type": "Gaussian (Pasquill-Gifford) — Cloudshine",
            "stability_class": stability,
            "wind_speed_ms": wind_ms,
            "wind_dir_from_deg": wind_from,
            "Q_ci_s": Q_ci_s,
            "H_m": req.release_height_m,
            "dcf_cloud": nuclide["dcf_cloud"],
        },
        "kml_links": {
            "network_link": f"{base_url}/kml/network.kml",
            "live_kml": f"{base_url}/kml/live.kml",
            "download": f"{base_url}/kml/download",
        },
    })


@app.get("/api/health")
async def health():
    return {"status": "ok", "active_overlays": {k: bool(v) for k, v in _overlay_state.items()}}


# ── ERG 2024 ──────────────────────────────────────────────────────────────────

class ERGZonesRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    un_number: str
    spill_size: str = "small"           # "small" | "large"
    wind_dir_from_deg: Optional[float] = None


class DenseGasRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    gas_id: str
    release_rate_kg_min: float = Field(..., gt=0, le=10_000)
    release_height_m: float = Field(default=0.0, ge=0, le=500)
    wind_speed_ms: float = Field(..., ge=0)
    wind_dir_from_deg: float = Field(..., ge=0, lt=360)
    stability_class: str = Field(..., pattern="^[A-Fa-f]$")


class FireSmokeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    fire_type_id: str
    wind_speed_ms: float = Field(..., ge=0)
    wind_dir_from_deg: float = Field(..., ge=0, lt=360)
    stability_class: str = Field(..., pattern="^[A-Fa-f]$")
    h_stack: float = Field(default=0.0, ge=0, le=500)


class ProbitRequest(BaseModel):
    zones: list[dict]
    exposure_min: float = Field(..., gt=0, le=480)
    gas_id: Optional[str] = None


class InfraCacheRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius: int = Field(..., gt=0, le=50_000)
    items: list[dict]  # [{type, name, lat, lon, distKm}, ...]


@app.post("/api/infra/cache")
async def cache_infra(req: InfraCacheRequest):
    """Cache infrastructure search results (from frontend Overpass query) for KML export."""
    global _overlay_state
    _overlay_state["infra"] = {
        "source_lat": req.lat,
        "source_lon": req.lon,
        "radius":     req.radius,
        "items":      req.items,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(content={"cached": len(req.items)})


@app.get("/api/erg/search")
async def erg_search(q: str = Query(..., min_length=1)):
    """Search ERG 2024 Table 1 by UN number or chemical name."""
    results = search_erg(q)
    return JSONResponse(content={"results": results, "count": len(results)})


@app.get("/api/erg/{un_number}")
async def erg_entry(un_number: str):
    """Return full ERG entry (both spill sizes) for a UN number."""
    entry = get_erg_entry(un_number)
    if not entry:
        raise HTTPException(status_code=404, detail=f"UN{un_number} not found in ERG 2024 Table 1.")
    return JSONResponse(content=entry)


@app.post("/api/erg/zones")
async def erg_zones(req: ERGZonesRequest):
    """Compute ERG isolation and PAD zones as GeoJSON."""
    if req.spill_size not in ("small", "large"):
        raise HTTPException(status_code=422, detail="spill_size must be 'small' or 'large'.")
    result = compute_erg_zones(
        lat=req.lat, lon=req.lon, un_number=req.un_number,
        spill_size=req.spill_size, wind_dir_from_deg=req.wind_dir_from_deg,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"UN{req.un_number} not in ERG 2024 Table 1.")

    global _overlay_state
    _overlay_state["erg"] = {
        **result,
        "source_lat": req.lat,
        "source_lon": req.lon,
        "zones": [
            {**f["properties"], "lonlat": f["geometry"]["coordinates"][0]}
            for f in result["geojson"]["features"]
            if f["properties"]["type"] == "erg_zone"
        ],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(content=result)


# ── Dense Gas Dispersion ─────────────────────────────────────────────────────

@app.get("/api/dense_gas/chemicals")
async def list_dense_gas_chemicals():
    """Return dense-gas chemical database (all gases with thresholds)."""
    return JSONResponse(content={"chemicals": list_dense_gases()})


@app.post("/api/dense_gas/zones")
async def compute_dense_gas(req: DenseGasRequest):
    """
    Compute modified-PG dense-gas dispersion zones (GeoJSON + stats).
    Weather parameters must be supplied by the caller (pre-fetched).
    """
    gas = get_dense_gas(req.gas_id)
    if not gas:
        raise HTTPException(status_code=404, detail=f"Gas '{req.gas_id}' not found.")

    stability = req.stability_class.upper()
    result = compute_dense_gas_zones(
        lat=req.lat,
        lon=req.lon,
        gas_id=req.gas_id,
        release_rate_kg_min=req.release_rate_kg_min,
        release_height_m=req.release_height_m,
        wind_speed_ms=req.wind_speed_ms,
        wind_dir_from_deg=req.wind_dir_from_deg,
        stability_class=stability,
    )

    global _overlay_state
    _overlay_state["dense_gas"] = {
        "source_lat":          req.lat,
        "source_lon":          req.lon,
        "gas_id":              req.gas_id,
        "gas_name":            gas["name"],
        "gas_formula":         gas.get("formula", ""),
        "release_rate_kg_min": req.release_rate_kg_min,
        "release_height_m":    req.release_height_m,
        "wind_speed_ms":       req.wind_speed_ms,
        "wind_dir_from_deg":   req.wind_dir_from_deg,
        "stability_class":     stability,
        "zones": [
            {
                **feat["properties"],
                "lonlat": feat["geometry"]["coordinates"][0],
            }
            for feat in result["geojson"]["features"]
            if feat["geometry"]["coordinates"]
        ],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=result)


# ── Fire / Smoke Plume ────────────────────────────────────────────────────────

@app.get("/api/fire_smoke/types")
async def list_fire_smoke_types():
    """Return fire-type database."""
    return JSONResponse(content={"fire_types": list_fire_types()})


@app.post("/api/fire_smoke/zones")
async def compute_fire_smoke(req: FireSmokeRequest):
    """
    Compute Briggs (1975) buoyant plume smoke zones (PM2.5 and CO).
    Weather parameters must be supplied by the caller (pre-fetched).
    """
    stability = req.stability_class.upper()
    result = compute_fire_smoke_zones(
        lat=req.lat,
        lon=req.lon,
        fire_type_id=req.fire_type_id,
        wind_speed_ms=req.wind_speed_ms,
        wind_dir_from_deg=req.wind_dir_from_deg,
        stability_class=stability,
        h_stack=req.h_stack,
    )

    global _overlay_state
    _overlay_state["fire_smoke"] = {
        "source_lat":        req.lat,
        "source_lon":        req.lon,
        "fire_type_id":      req.fire_type_id,
        "fire_name":         result["fire"]["name"],
        "hrr_mw":            result["fire"]["hrr_mw"],
        "wind_speed_ms":     req.wind_speed_ms,
        "wind_dir_from_deg": req.wind_dir_from_deg,
        "stability_class":   stability,
        "h_stack_m":         req.h_stack,
        "zones": [
            {
                **feat["properties"],
                "lonlat": feat["geometry"]["coordinates"][0],
            }
            for feat in result["geojson"]["features"]
            if feat["geometry"]["coordinates"]
        ],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=result)


# ── Probit Casualty Estimator ─────────────────────────────────────────────────

@app.post("/api/probit")
async def run_probit(req: ProbitRequest):
    """
    Estimate casualties in each hazard zone using probit analysis.
    Zones must include 'pop_estimate' field (from /api/population).
    """
    result = compute_probit_zones(
        zones=req.zones,
        exposure_min=req.exposure_min,
        gas_id=req.gas_id,
    )
    return JSONResponse(content=result)


# ── CoT XML (ATAK streaming) ──────────────────────────────────────────────────

@app.get("/api/cot")
async def get_cot_xml():
    """
    Return Cursor-on-Target (CoT) XML for all active overlays.
    Feed into WinTAK / iTAK / FreeTAKServer or stream over UDP 239.2.3.1:6969.
    """
    if not any(_overlay_state.values()):
        raise HTTPException(status_code=404, detail="No overlays computed yet.")
    xml = build_cot_xml(_overlay_state)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": 'attachment; filename="wmd_cot.xml"'})


# ── TAK Server profiles (admin) ───────────────────────────────────────────────

def _profile_to_config(p: dict) -> dict:
    return {
        "host":            p.get("host") or "",
        "port":            str(p.get("port") or 8089),
        "marti_port":      str(p.get("marti_port") or 8443),
        "ssl":             bool(p.get("ssl")),
        "cert_p12":        p.get("cert_p12"),
        "cert_pass":       p.get("cert_pass") or "",
        "admin_cert_p12":  p.get("admin_cert_p12"),
        "admin_cert_pass": p.get("admin_cert_pass") or "",
    }


@app.get("/api/admin/tak-profiles")
async def api_list_tak_profiles(user: dict = Depends(require_admin)):
    return {"profiles": list_tak_profiles()}


@app.post("/api/admin/tak-profiles")
async def api_create_tak_profile(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    pid = upsert_tak_profile(
        name       = (body.get("name") or "Unnamed").strip(),
        host       = (body.get("host") or "").strip(),
        port       = int(body.get("port") or 8089),
        marti_port = int(body.get("marti_port") or 8443),
        ssl        = bool(body.get("ssl", True)),
        callsign   = (body.get("callsign") or "WMD PLOTTER").strip(),
    )
    if body.get("cert_p12_b64"):
        set_tak_profile_cert(pid, body["cert_p12_b64"], body.get("cert_pass") or "")
    if body.get("admin_cert_p12_b64"):
        set_tak_profile_admin_cert(pid, body["admin_cert_p12_b64"], body.get("admin_cert_pass") or "")
    # Auto-activate if it's the first profile
    profiles = list_tak_profiles()
    if len(profiles) == 1:
        set_active_tak_profile(pid)
    return {"id": pid, "status": "created"}


@app.put("/api/admin/tak-profiles/{profile_id}")
async def api_update_tak_profile(profile_id: int, request: Request, user: dict = Depends(require_admin)):
    if not get_tak_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    body = await request.json()
    upsert_tak_profile(
        name       = (body.get("name") or "Unnamed").strip(),
        host       = (body.get("host") or "").strip(),
        port       = int(body.get("port") or 8089),
        marti_port = int(body.get("marti_port") or 8443),
        ssl        = bool(body.get("ssl", True)),
        callsign   = (body.get("callsign") or "WMD PLOTTER").strip(),
        profile_id = profile_id,
    )
    if body.get("clear_cert"):
        set_tak_profile_cert(profile_id, None, None)
    elif body.get("cert_p12_b64"):
        set_tak_profile_cert(profile_id, body["cert_p12_b64"], body.get("cert_pass") or "")
    if body.get("clear_admin_cert"):
        set_tak_profile_admin_cert(profile_id, None, None)
    elif body.get("admin_cert_p12_b64"):
        set_tak_profile_admin_cert(profile_id, body["admin_cert_p12_b64"], body.get("admin_cert_pass") or "")
    return {"status": "updated"}


@app.delete("/api/admin/tak-profiles/{profile_id}")
async def api_delete_tak_profile(profile_id: int, user: dict = Depends(require_admin)):
    if not delete_tak_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    # If we deleted the active profile, activate the first remaining one
    remaining = list_tak_profiles()
    if remaining and not any(p["is_active"] for p in remaining):
        set_active_tak_profile(remaining[0]["id"])
    return {"status": "deleted"}


@app.post("/api/admin/tak-profiles/{profile_id}/activate")
async def api_activate_tak_profile(profile_id: int, user: dict = Depends(require_admin)):
    if not get_tak_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    set_active_tak_profile(profile_id)
    return {"status": "activated"}


@app.get("/api/tak-status")
async def tak_status(user: dict = Depends(current_user)):
    p = get_active_tak_profile()
    if not p:
        return {"configured": False, "host": "", "port": "8089"}
    return {"configured": bool(p.get("host")), "host": p.get("host") or "", "port": str(p.get("port") or 8089),
            "profile_name": p.get("name") or ""}


@app.post("/api/tak-push")
async def tak_push(request: Request, user: dict = Depends(current_user)):
    """Stream all active overlays to the active TAK server profile as CoT events."""
    if not any(_overlay_state.values()):
        return JSONResponse(
            {"success": False, "sent": 0,
             "error": "No model data — run a model first, then push."},
            status_code=400,
        )
    p = get_active_tak_profile()
    if not p or not p.get("host"):
        return JSONResponse({"success": False, "sent": 0, "error": "No TAK server profile configured"}, status_code=400)
    result = push_cot(_profile_to_config(p), _overlay_state)
    result["server_tools"] = {k: len(v.get("zones", [])) for k, v in _overlay_state.items() if v}
    return JSONResponse(result, status_code=200 if result["success"] else 502)


@app.get("/api/tak-preview")
async def tak_preview(user: dict = Depends(current_user)):
    """Return the raw CoT XML that would be sent on the next push — for debugging."""
    from tak_push import _build_events
    events = _build_events(_overlay_state)
    if not events:
        return JSONResponse({"events": [], "count": 0, "error": "No active overlays — run a model first"})
    return JSONResponse({
        "count": len(events),
        "events": events,
        "tools": [k for k, v in _overlay_state.items() if v],
    })


@app.post("/api/tak-push-marti")
async def tak_push_marti(request: Request, user: dict = Depends(current_user)):
    """
    Push overlay CoT events to TAK server via Marti HTTPS.
    Primary: POST each CoT to /Marti/api/cot (confirmed working with device cert).
    Fallback: KMZ upload + b-f-t-r notification (requires upload permissions).
    """
    if not any(_overlay_state.values()):
        return JSONResponse(
            {"success": False, "error": "No model data — run a model first."},
            status_code=400,
        )
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    profile_id = body.get("profile_id")
    p = get_tak_profile(int(profile_id)) if profile_id else get_active_tak_profile()
    if not p or not p.get("host"):
        return JSONResponse({"success": False, "error": "No TAK server profile configured"}, status_code=400)
    config = _profile_to_config(p)

    # Primary: HTTP CoT injection (same endpoint as working test marker)
    result = await push_cot_http(config, _overlay_state)
    if result["success"]:
        return JSONResponse(result)

    # Fallback: KMZ upload + b-f-t-r (requires Marti upload permissions)
    result2 = await push_via_marti(config, _overlay_state)
    if result2.get("success"):
        return JSONResponse(result2)

    # Return HTTP CoT error (more actionable)
    return JSONResponse(result, status_code=502)


@app.post("/api/tak-test-point")
async def tak_test_point(request: Request, user: dict = Depends(require_admin)):
    """
    Send an SA point marker to a TAK profile to verify end-to-end routing.
    Tries HTTP CoT injection (/Marti/api/cot) first — more reliable than raw TCP
    because the HTTPS response confirms the server processed the event.
    Falls back to TCP CoT if HTTP fails.
    """
    body = await request.json()
    lat  = float(body.get("lat", 0.0))
    lon  = float(body.get("lon", 0.0))
    profile_id = body.get("profile_id")
    p = get_tak_profile(int(profile_id)) if profile_id else get_active_tak_profile()
    if not p or not p.get("host"):
        return JSONResponse({"success": False, "error": "No TAK server profile configured"}, status_code=400)

    config   = _profile_to_config(p)
    callsign = p.get("callsign") or "WMD PLOTTER"
    host     = config["host"]
    marti_port = int(config.get("marti_port") or 8443)

    from tak_dp import point_cot_event
    from tak_marti import _make_ssl_ctx
    cot_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{point_cot_event(lat, lon, callsign)}'

    # Attempt 1: HTTP CoT injection via Marti API (same cert, same port as data package push)
    if config.get("cert_p12"):
        try:
            ctx, temps = _make_ssl_ctx(config["cert_p12"], config.get("cert_pass") or "")
            try:
                async with httpx.AsyncClient(verify=ctx, timeout=10.0) as client:
                    r = await client.post(
                        f"https://{host}:{marti_port}/Marti/api/cot",
                        content=cot_xml.encode("utf-8"),
                        headers={
                            "Content-Type": "application/octet-stream",
                            "X-Content-Type": "application/xml",
                        },
                    )
                if r.status_code in (200, 201, 204):
                    return JSONResponse({"success": True, "method": "http", "error": None})
            finally:
                import os as _os
                for t in temps:
                    try: _os.unlink(t)
                    except OSError: pass
        except Exception:
            pass

    # Attempt 2: TCP CoT (with 2-second linger before close)
    result = push_test_point(config, lat, lon, callsign)
    result["method"] = "tcp"
    return JSONResponse(result, status_code=200 if result["success"] else 502)


# ── NASA FIRMS hotspots ───────────────────────────────────────────────────────

@app.get("/api/firms/hotspots")
async def firms_hotspots(
    lat:       float = Query(..., ge=-90,  le=90),
    lon:       float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=200, ge=10, le=1000),
    days:      int   = Query(default=1,   ge=1,  le=7),
):
    """VIIRS S-NPP NRT fire hotspots within radius_km for the past `days` days."""
    try:
        result = await fetch_firms_hotspots(lat, lon, radius_km, days)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"FIRMS fetch failed: {e}")


# ── NOAA NWS hourly forecast ──────────────────────────────────────────────────

@app.get("/api/weather/forecast")
async def nws_forecast(
    lat: float = Query(..., ge=-90,  le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """NOAA NWS 24-hour hourly wind/stability forecast (US locations only)."""
    try:
        periods = await fetch_nws_forecast(lat, lon)
        return JSONResponse(content={"periods": periods, "count": len(periods)})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NWS forecast failed: {e}")


# ── HIFLD critical infrastructure ────────────────────────────────────────────

@app.get("/api/hifld/infra")
async def hifld_infra(
    lat:       float = Query(..., ge=-90,  le=90),
    lon:       float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=5, ge=0.5, le=50),
):
    """HIFLD DHS critical infrastructure within radius_km (US only)."""
    try:
        items = await fetch_hifld_infra(lat, lon, radius_km)
        return JSONResponse(content={"items": items, "count": len(items), "source": "HIFLD"})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HIFLD fetch failed: {e}")


# ── NIFC active fire perimeters ───────────────────────────────────────────────

@app.get("/api/nifc/perimeters")
async def nifc_perimeters(
    lat:       Optional[float] = Query(default=None, ge=-90,  le=90),
    lon:       Optional[float] = Query(default=None, ge=-180, le=180),
    radius_km: float           = Query(default=500,  ge=10,   le=3000),
):
    """NIFC/WFIGS active wildfire perimeters (optionally filtered by bbox)."""
    try:
        result = await fetch_nifc_perimeters(lat, lon, radius_km)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NIFC fetch failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
