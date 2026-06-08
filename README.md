# WMD Plotter — WHITWERX Model Display

**Browser-based CBRN hazard modeling for emergency response planning.**

Run chemical plume, blast, radiation, BLEVE, dense gas, fire/smoke, and ERG 2024 models directly in your browser. Export to ATAK, Google Earth, or share a scenario URL with a single click. Deploys to any Ubuntu VPS in under 5 minutes.

![Version](https://img.shields.io/badge/version-2.3.0-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Hazard Models

| Model | Description |
|---|---|
| ☣ **Chemical Plume** | Gaussian dispersion for TICs, TIMs, and CWAs — IDLH, AEGL-1/2/3 contours |
| 💥 **Blast Zones** | Explosive overpressure damage radii from IEDs, VBIEDs, and munitions |
| 🔥 **BLEVE / Fireball** | Thermal hazard zones for pressurized fuel tank failures |
| 🌫 **Dense Gas** | Heavy gas cloud footprint (chlorine, propane, LNG) |
| 🧪 **ERG 2024** | UN hazmat isolation and protective action distances — any UN number |
| ☢ **Radiation (RDD)** | Radiological dispersal device contours with dose rate zones |
| 🔥 **Fire / Smoke** | Buoyant smoke plume with PM2.5 and CO hazard zones |
| ☠ **Probit / Casualty** | Dose-response lethality and injury estimates |
| 👥 **Population Impact** | Census-based exposure count within the hazard footprint |
| 🏗 **Infrastructure** | Critical facilities (hospitals, schools, utilities) in the affected area |
| 📡 **Live Data Feeds** | NASA FIRMS active fire, NIFC perimeters, NWS forecast |
| 🏠 **Shelter / Evac** | Protective action guidance — shelter-in-place vs. evacuation |
| 📅 **Incident Timeline** | CBRN scenario log and replay |

Multiple models run simultaneously and stack on the same map.

---

## Export & Integration

- **TAK Data Package** — `.zip` for direct import into ATAK, WinTAK, and iTAK
- **CoT XML** — Cursor-on-Target for FreeTAK Server or UDP broadcast to `239.2.3.1:6969`
- **KML Download** — static snapshot for Google Earth, ArcGIS, or QGIS
- **Network Link KML** — live-updating feed; Google Earth polls for new results automatically
- **Share URL** — encode the full scenario (location, model, parameters) into a URL anyone can open

---

## Deploy in 5 Minutes

Requires Ubuntu 22.04 VPS. Run as root:

```bash
git clone https://github.com/dwhit6605-bit/WMD-PLOTTER.git /tmp/wmd-install
cd /tmp/wmd-install

sudo bash deploy.sh \
  --domain your.domain.com \
  --email  you@example.com \
  --git-url https://github.com/dwhit6605-bit/WMD-PLOTTER.git
```

The script handles everything: Python virtualenv, systemd service, nginx reverse proxy, UFW firewall, and Let's Encrypt HTTPS.

**No domain?** Drop the `--domain` and `--email` flags to deploy over HTTP on a plain IP.

**Update later:**
```bash
sudo wmd-update
```

See [INSTALL.md](INSTALL.md) for the complete deployment guide, environment variable setup, ATAK integration steps, and troubleshooting.

---

## Run Locally

```bash
git clone https://github.com/dwhit6605-bit/WMD-PLOTTER.git
cd WMD-PLOTTER

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd backend
python main.py
```

Open `http://localhost:8000` in your browser.

---

## Optional: FIRMS Live Fire Data

Active fire feeds require a free NASA API key.

1. Get a key at [firms.modaps.eosdis.nasa.gov/api/area](https://firms.modaps.eosdis.nasa.gov/api/area/)
2. Create `backend/.env`:
   ```
   FIRMS_MAP_KEY=your_key_here
   ```

All hazard models, weather, ERG, and TAK export work without a key.

---

## Install as a Mobile App (PWA)

WMD Plotter is a Progressive Web App. On HTTPS deployments:

- **Android** — Chrome shows an "Add to Home Screen" prompt inside the app sidebar
- **iOS** — Safari: Share ⎋ → "Add to Home Screen"

The app shell and assets are cached for offline use. Model runs still require connectivity to reach the backend.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.10+, FastAPI, uvicorn |
| Modeling | Pure Python — no external solvers required |
| Frontend | Vanilla JS, Leaflet.js, Leaflet-Geoman |
| Reverse proxy | nginx |
| Process manager | systemd |
| HTTPS | Let's Encrypt / Certbot |
| TAK export | Mission Package v2 (KML + manifest ZIP) |

No database. No Docker required. Minimal dependencies.

---

## API

The backend exposes a self-documenting REST API. Once running, visit `/docs` for the interactive Swagger UI.

Key endpoints:

```
POST /api/plume          Chemical plume dispersion
POST /api/blast          Blast zone calculation
POST /api/radiation      Radiation dispersal
POST /api/bleve          BLEVE / fireball zones
POST /api/erg            ERG 2024 isolation zones
POST /api/dense-gas      Dense gas cloud
POST /api/fire-smoke     Fire / smoke plume
GET  /kml/live.kml       Live KML of all active overlays
GET  /kml/network.kml    Google Earth NetworkLink
GET  /export/tak-dp      TAK Data Package (.zip)
GET  /api/cot            Cursor-on-Target XML
GET  /api/health         Service health + overlay state
```

---

## Project Structure

```
WMD-PLOTTER/
├── backend/
│   ├── main.py          API server and route definitions
│   ├── dispersion.py    Gaussian plume model
│   ├── blast.py         Hopkinson-Cranz scaling
│   ├── radiation.py     RDD dose contours
│   ├── bleve.py         BLEVE / fireball thermal model
│   ├── erg.py           ERG 2024 database and zone calculator
│   ├── dense_gas.py     Heavy gas dispersion
│   ├── fire_smoke.py    Buoyant plume model
│   ├── kml_gen.py       KML builder (ATAK-compatible)
│   ├── tak_dp.py        TAK Mission Package and CoT generator
│   ├── chemicals.py     TIC / CWA database
│   ├── aegl_db.py       AEGL tier thresholds
│   └── .env             API keys — NOT committed to git
├── frontend/
│   ├── index.html       Single-page app (HTML + CSS + JS)
│   ├── sw.js            Service worker (PWA offline shell)
│   ├── manifest.json    Web app manifest
│   └── icons/           PWA icons (192px, 512px, apple-touch)
├── deploy.sh            One-command VPS deployment
├── update.sh            Pull and restart
├── requirements.txt     Python dependencies
└── INSTALL.md           Full deployment and user guide
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

*Built and maintained by WHITWERX.*
