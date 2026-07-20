# WMD Plotter — Installation & User Guide

**WHITWERX Model Display (WMD Plotter)** is a browser-based CBRN hazard modeling tool for emergency response planning. It runs a Python backend and serves a single-page web app — no database required.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Deploy to a VPS (5 minutes)](#2-deploy-to-a-vps)
3. [Deploy with Docker](#3-deploy-with-docker)
4. [Access Control (Passphrase Gate)](#4-access-control-passphrase-gate)
5. [Environment Variables (API keys)](#5-environment-variables)
6. [Verify It's Running](#6-verify-its-running)
7. [First-Use Walkthrough](#7-first-use-walkthrough)
8. [TAK / ATAK Integration](#8-tak--atak-integration)
9. [Google Earth Integration](#9-google-earth-integration)
10. [Managing the Service](#10-managing-the-service)
11. [Updating](#11-updating)
12. [Installing on a Phone (PWA)](#12-installing-on-a-phone-pwa)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| VPS OS | Ubuntu 22.04 LTS | Debian 12 also works |
| RAM | 512 MB | 1 GB recommended |
| CPU | 1 vCPU | |
| Disk | 2 GB free | |
| Domain | Optional | Required for HTTPS / PWA install on phone |
| Ports open | 80, 443, 22 | 443 only needed if using HTTPS |

> **No domain?** The app works fine over plain HTTP on an IP address. HTTPS is required only if you want the "Add to Home Screen" PWA feature on mobile.

---

## 2. Deploy to a VPS

SSH into your server as root (or a sudo user), then run:

```bash
# Clone the repository
git clone https://github.com/dwhit6605-bit/WMD-PLOTTER.git /tmp/wmd-install
cd /tmp/wmd-install

# Run the deploy script
# Replace the values below with your own domain and email
sudo bash deploy.sh \
  --domain your.domain.com \
  --email  you@example.com \
  --git-url https://github.com/dwhit6605-bit/WMD-PLOTTER.git
```

**Without a domain (IP-only install):**

```bash
sudo bash deploy.sh \
  --git-url https://github.com/dwhit6605-bit/WMD-PLOTTER.git
```

### What the script does

1. Installs `python3`, `nginx`, `git` via `apt`
2. Creates a dedicated `wmdplotter` system user
3. Clones the repo to `/opt/wmd-plotter`
4. Creates a Python virtualenv and installs dependencies
5. Installs and starts a `systemd` service (`wmd-plotter`)
6. Configures nginx as a reverse proxy
7. If a domain was provided: installs Certbot and provisions a Let's Encrypt HTTPS certificate
8. Configures UFW firewall (allows 22, 80, 443; blocks direct uvicorn port)
9. Installs `sudo wmd-update` command for future updates

The whole process takes **2–5 minutes**.

---

## 3. Deploy with Docker

If you prefer Docker over bare-metal systemd, a `docker-compose.yml` is included.

### Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Any Linux distro, macOS, or Windows (WSL2)

### Quick start

```bash
git clone https://github.com/dwhit6605-bit/WMD-PLOTTER.git
cd WMD-PLOTTER

# Optional: add your FIRMS API key
echo "FIRMS_MAP_KEY=your_key_here" > backend/.env

docker compose up -d
```

Open `http://localhost:8000`.

### Expose on a public port

The default binds to `localhost:8000`. To expose it on all interfaces (e.g., behind your own reverse proxy):

```yaml
# docker-compose.yml — change the ports line:
ports:
  - "0.0.0.0:8000:8000"
```

### Adding HTTPS with Caddy (recommended for Docker)

Create a `Caddyfile` next to docker-compose.yml:

```
your.domain.com {
    reverse_proxy wmd-plotter:8000
    basicauth /* {
        wmd JDJhJDE0JHhY...   # bcrypt hash — generate with: caddy hash-password
    }
}
```

Add Caddy to your `docker-compose.yml`:

```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - wmd-plotter

volumes:
  caddy_data:
  caddy_config:
```

### Updating (Docker)

```bash
git pull
docker compose up -d --build
```

---

## 4. Access Control (Passphrase Gate)

By default the app is open to anyone who can reach the URL. For a shared or internet-facing server, enable HTTP Basic Auth so the app requires a username and passphrase before loading.

### Enable at deploy time (VPS)

```bash
sudo bash deploy.sh \
  --domain your.domain.com \
  --email  you@example.com \
  --git-url https://github.com/dwhit6605-bit/WMD-PLOTTER.git \
  --auth-user wmd \
  --auth-pass YourPassphraseHere
```

### Enable on an existing install (VPS)

```bash
# Install htpasswd utility
sudo apt-get install -y apache2-utils

# Create the password file
sudo htpasswd -bc /etc/nginx/.wmd-htpasswd wmd YourPassphraseHere
sudo chmod 640 /etc/nginx/.wmd-htpasswd
sudo chown root:www-data /etc/nginx/.wmd-htpasswd

# Add these two lines inside the server{} block in nginx config,
# just before the first location{} block:
sudo nano /etc/nginx/sites-available/wmd-plotter
```

Add inside `server { ... }`:
```nginx
auth_basic "WMD Plotter — Authorized Access Only";
auth_basic_user_file /etc/nginx/.wmd-htpasswd;
```

Then reload nginx:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Change the passphrase

```bash
sudo htpasswd /etc/nginx/.wmd-htpasswd wmd
# (prompts for new password)
```

### Disable auth

Remove the two `auth_basic` lines from `/etc/nginx/sites-available/wmd-plotter`, then:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

> **Note:** HTTP Basic Auth sends credentials with every request. Use it over HTTPS only (i.e., with a domain and Let's Encrypt certificate).

---

## 5. Environment Variables

Some features require API keys. These are stored in a `.env` file that is **never committed to git**.

Create the file after deployment:

```bash
sudo nano /opt/wmd-plotter/backend/.env
```

Add the following (replace values with your own keys):

```env
# FIRMS active fire data (NASA EOSDIS)
# Free key — get one at: https://firms.modaps.eosdis.nasa.gov/api/area/
FIRMS_MAP_KEY=your_firms_key_here

# Public URL of this server — required for TAK data package push.
# ATAK devices download the KMZ from this URL when you push a data package.
# Must be reachable by field devices (use your domain, not localhost).
WMD_PUBLIC_URL=https://wmd.whitwerx.net
```

Save the file (`Ctrl+O`, `Enter`, `Ctrl+X`), then restart the service:

```bash
sudo systemctl restart wmd-plotter
```

> **Note:** The app runs without any `.env` file — only the FIRMS live fire feed requires a key. All hazard models, weather, ERG, and TAK export work without any API key.

### Getting a free FIRMS key

1. Go to [firms.modaps.eosdis.nasa.gov/api/area](https://firms.modaps.eosdis.nasa.gov/api/area/)
2. Click **"Get MAP_KEY"**
3. Register with your email — the key arrives instantly
4. Paste it into `/opt/wmd-plotter/backend/.env` as shown above

---

## 6. Verify It's Running

```bash
# Check service status
sudo systemctl status wmd-plotter

# Check the API is responding
curl http://localhost:8000/api/health

# View live logs
sudo journalctl -u wmd-plotter -f
```

Expected health response:
```json
{"status":"ok"}
```

Model results are per-user, so an unauthenticated health check reports liveness
only. Called with a valid session cookie it also returns that user's overlays:

```json
{"status":"ok","active_overlays":{"plume":false,"blast":false,...}}
```

Open a browser and go to your domain (or `http://<server-ip>`). You should see the WMD Plotter map.

---

## 7. First-Use Walkthrough

### Step 1 — Place your incident

Click anywhere on the map, or type an address into the **Search** box at the top of the left panel.

- The map will place a red incident marker
- Weather data is automatically pulled for that location
- Wind speed, direction, and Pasquill stability class are shown in the **Weather** section

You can also enter coordinates directly in the **Lat / Lon** fields.

### Step 2 — Pick your hazard models

Click the **+ Add Overlay** section to see available models:

| Model | Use case |
|---|---|
| **Chemical Plume** | TIC/TIM/CWA Gaussian dispersion (chlorine, ammonia, nerve agents, etc.) |
| **Blast Zones** | Explosive overpressure damage radii (IED, VBIED, munitions) |
| **BLEVE / Fireball** | Pressurized fuel tank thermal hazard zones |
| **Dense Gas** | Heavy gas cloud (propane, chlorine spill) footprint |
| **ERG 2024** | UN hazmat isolation and PAD zones (any UN number) |
| **Radiation (RDD)** | Dirty bomb / radiological dispersal contours |
| **Fire / Smoke** | Buoyant smoke plume from structure/wildland fire |
| **Population Impact** | Census-based exposure estimate in the hazard zone |
| **Infrastructure** | Critical facilities (hospitals, schools, utilities) within the affected area |

Toggle as many as needed — overlays stack on the map.

### Step 3 — Configure and run the model

Each model has its own panel with parameter inputs. Fill in the relevant fields and click the **Run** button. Typical parameters:

- **Chemical plume** — chemical agent, release rate (kg/s), release height
- **Blast** — explosive type, net explosive weight (kg)
- **ERG** — UN number, spill size (small / large)
- **Radiation** — isotope, activity (Ci or TBq)

Results appear as colored zones on the map with a legend.

### Step 4 — Export

Use the **Export** section in the left panel:

| Export | Use |
|---|---|
| **KML Download** | Open in Google Earth or any GIS |
| **Network Link KML** | Live-updating link for Google Earth |
| **TAK Data Package (.zip)** | Import directly into ATAK, WinTAK, or iTAK |
| **CoT XML** | Cursor-on-Target for FreeTAK Server / WinTAK broadcast |
| **Copy Share Link** | URL that restores the full scenario in any browser |

---

## 8. TAK / ATAK Integration

### Import a Data Package into ATAK

1. In WMD Plotter, run your model(s) and click **TAK Data Package (.zip)**
2. The file downloads to your device or computer
3. In ATAK on your phone/tablet: **Menu → Manage Files → Local → Import**
4. Select the `.zip` file — hazard zones appear as colored polygons on the map

### WinTAK

1. Download the `.zip` to your computer
2. WinTAK: **File → Import → Mission Package** → select the zip

### FreeTAK Server (CoT broadcast)

1. Run your model in WMD Plotter
2. Click **CoT XML** to download
3. Use `nc` or your FTS import tool to push to the multicast address:
   ```bash
   cat wmd_cot.xml | nc -u 239.2.3.1 6969
   ```

---

## 9. Google Earth Integration

### One-time Network Link setup (live-updating)

1. In WMD Plotter, run a model
2. Click **Network Link KML** in the Export section
3. Open the downloaded `.kml` file in Google Earth Desktop
4. The link will refresh every 30 seconds — re-run any model and the zones update automatically

### Static snapshot

Click **KML Download** for a one-time export. Open with Google Earth, ArcGIS, QGIS, or any KML-compatible viewer.

---

## 10. Managing the Service

```bash
# Status
sudo systemctl status wmd-plotter

# Start / Stop / Restart
sudo systemctl start  wmd-plotter
sudo systemctl stop   wmd-plotter
sudo systemctl restart wmd-plotter

# Live logs (Ctrl+C to exit)
sudo journalctl -u wmd-plotter -f

# Last 100 lines of logs
sudo journalctl -u wmd-plotter -n 100

# Interactive API docs (useful for testing)
# Open in browser: http://your-domain/docs
```

---

## 11. Updating

Pull the latest code and restart in one command:

```bash
sudo wmd-update
```

This pulls from GitHub, upgrades any new Python dependencies, and restarts the service. Downtime is typically under 5 seconds.

---

## 12. Installing on a Phone (PWA)

WMD Plotter is a **Progressive Web App** — it can be installed on Android or iOS and works like a native app with an offline shell.

**Requires HTTPS** (i.e., you must have set up a domain with `--domain` during deployment).

### Android (Chrome)

1. Open `https://your.domain.com` in Chrome
2. A banner appears in the WMD Plotter sidebar: **"Add to Home Screen"**
3. Tap it and follow the prompt
4. The app installs to your home screen and launches in standalone mode

### iOS (Safari)

1. Open `https://your.domain.com` in Safari
2. The sidebar shows: *Tap Share ⎋ at the bottom of Safari, then tap "Add to Home Screen"*
3. Follow the Safari share sheet prompt

Once installed, the app shell loads instantly even with no signal. Model runs still require an internet connection to reach the backend.

---

## 13. Troubleshooting

### App doesn't load / blank page

```bash
sudo systemctl status wmd-plotter
sudo journalctl -u wmd-plotter -n 50
```

Common causes:
- Port 8000 not available — check with `sudo ss -tlnp | grep 8000`
- Python dependency missing — re-run `sudo wmd-update`

### "502 Bad Gateway" from nginx

The backend isn't running. Check:
```bash
sudo systemctl restart wmd-plotter
sudo systemctl status wmd-plotter
```

### Weather not loading

The app uses the free NWS API (`api.weather.gov`) — US locations only. For non-US locations, enter wind speed and direction manually in the Weather section.

### FIRMS fire data not showing

Check your API key in `/opt/wmd-plotter/backend/.env`, then restart the service. Confirm the key works:
```bash
source /opt/wmd-plotter/backend/.env
curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/${FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/world/1"
```

### ATAK won't import the data package

- Make sure you're importing the `.zip` file (not the `.kml`)
- In ATAK: **Menu → Settings → Display → KML** — ensure KML import is enabled
- Confirm the app URL is reachable from the ATAK device (same network or VPN)

### HTTPS certificate not renewing

Certbot installs an automatic renewal timer. Check it:
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

### Reset to a clean state

If overlay state gets stuck (e.g. stale exports after a server restart mid-session), hard-reload the browser tab (`Ctrl+Shift+R` / `Cmd+Shift+R`) and re-run your model.

---

## Quick Reference

| Task | Command |
|---|---|
| Check status | `sudo systemctl status wmd-plotter` |
| View logs | `sudo journalctl -u wmd-plotter -f` |
| Restart service | `sudo systemctl restart wmd-plotter` |
| Update to latest | `sudo wmd-update` |
| Edit API keys | `sudo nano /opt/wmd-plotter/backend/.env` |
| API docs | `https://your.domain/docs` |
| Health check | `curl http://localhost:8000/api/health` |

---

*WMD Plotter is maintained by WHITWERX. For issues or contributions, open a GitHub issue.*
