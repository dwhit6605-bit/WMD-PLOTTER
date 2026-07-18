# WMD PLOTTER — Android shell

A [Capacitor](https://capacitorjs.com/) wrapper that ships the existing web app as
an installable Android application, plus native GPS for incident-location autofill.

## Toolchain

This machine needs three things pointed at explicitly, because the defaults are all wrong:

| Need | Why the default fails | Use |
|---|---|---|
| Node ≥ 22 | `node` is symlinked to `node@20`; the Capacitor 8 CLI hard-fails below 22 | `export PATH="/opt/homebrew/Cellar/node/26.4.0/bin:$PATH"` |
| JDK 17+ | system `java` is 1.8, which cannot run the Android Gradle Plugin | `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"` (JDK 21) |
| Android SDK | `ANDROID_HOME` is unset | `export ANDROID_HOME="$HOME/Library/Android/sdk"` |

Both Node versions are installed via Homebrew and `node` is deliberately linked to
`node@20` — presumably something else needs it — so put Node 26 on `PATH` per-command
rather than running `brew link --overwrite node`.

Config is `capacitor.config.json`, not `.ts`, on purpose: the Capacitor 8 CLI parses
`.ts` configs through a TypeScript 5 API (`ts.ModuleKind`) that TypeScript 7 removed,
so a `.ts` config dies with `Cannot read properties of undefined (reading 'CommonJS')`.
JSON sidesteps the CLI bug and drops the TypeScript dependency entirely.

## Build

```bash
export PATH="/opt/homebrew/Cellar/node/26.4.0/bin:$PATH"
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export ANDROID_HOME="$HOME/Library/Android/sdk"

cd mobile
npx cap sync android              # after changing config or plugins
cd android && ./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
```

Open in Android Studio with `npx cap open android`.

## Architecture: the shell loads the live site

`capacitor.config.json` sets `server.url = https://wmd.whitwerx.net`, so the WebView
loads the deployed site instead of bundling `frontend/` into the APK.

This is what makes the auth work unchanged. The WebView's origin *is*
`wmd.whitwerx.net`, so the existing httpOnly JWT cookie is first-party and
credentialed fetches behave exactly as in a desktop browser. Bundling the assets
instead would make every `/api` call cross-origin from `https://localhost`, which
forces CORS *and* `SameSite=None` cookies — which Android's WebView treats as
third-party and may block outright. That path means rewriting auth to bearer tokens
in secure storage. Not worth it.

Consequence worth knowing: **a web deploy updates the app instantly, with no Play
release.** Only native-shell changes (plugins, permissions, icons, `capacitor.config.json`)
need a new APK. The tradeoff is that the app requires connectivity — there is no
offline mode. If field teams need airgap operation, that is the Chaquopy path
(bundle a Python runtime and run the models on-device), which is a much larger job.

## Play Store constraints

The app is distributed on the public Play Store, and subscriptions are sold on the
web via Stripe. Two rules follow from that, and **both are load-bearing**:

1. **No purchase flow in the app.** Selling a digital subscription inside a
   Play-distributed app requires Google Play Billing (15% of the first $1M/yr, 30%
   above). The app therefore sells nothing — users subscribe at `wmd.whitwerx.net`
   in a browser and the app is purely a sign-in client for an account they already
   pay for. This is the standard enterprise-SaaS pattern (Slack, Salesforce, Notion).

2. **No link to the purchase page from inside the app.** Google's anti-steering rule
   historically banned linking out to external payment; that rule was being unwound
   through the *Epic v. Google* injunction, and the current state is worth verifying
   before relying on it. The conservative build — an inactive-subscription screen
   that is **plain text**, with no tappable link to Stripe — is safe under either
   regime. Keep it that way unless someone confirms the current policy.

**Store listing:** do not lead with "WMD." Play review is partly automated, and an app
titled "WMD Plotter" describing plume and blast modeling invites a rejection you would
then have to appeal. Use the real expansion — *WHITWERX Model Display* — and position
it as HazMat/CBRN modeling for fire and emergency services. `appName` in
`capacitor.config.json` is already set this way.

**Minimum functionality:** Play's spam policy targets apps that are only a WebView of a
website. Native GPS autofill is the substantive native capability that distinguishes
this from a bookmark. Do not remove it. Be aware this is still the weakest part of the
Play case — a WebView plus GPS is not a lot of native surface, and a reviewer could
reasonably push back. If it gets rejected on minimum-functionality grounds, the next
native capabilities worth adding are offline scenario caching and share-sheet export
of KMZ/PDF products.

## Geolocation: no plugin needed

`frontend/index.html` already calls `navigator.geolocation` in `useMyLocation()`, and
**that works unmodified inside the Capacitor WebView**. Two things in Capacitor's own
source make it work, both verified by reading it rather than assuming:

- `Bridge.java:585` calls `settings.setGeolocationEnabled(true)` unconditionally.
- `BridgeWebChromeClient.onGeolocationPermissionsShowPrompt` requests the
  `ACCESS_COARSE_LOCATION` / `ACCESS_FINE_LOCATION` runtime permission and then grants
  the WebView, so the user sees a normal native Android permission dialog.

The only thing that was missing was the manifest declarations, which are now in
`android/app/src/main/AndroidManifest.xml`. `@capacitor/geolocation` was therefore
removed — it would have been an unused native dependency, and using it would have meant
a Capacitor-specific JS path that breaks the app in a plain desktop browser. One code
path, works everywhere.

## Detecting the app: User-Agent, not `window.Capacitor`

`android.appendUserAgent` appends `WMDPlotterAndroid` to the WebView User-Agent, and
that is the supported way to tell app traffic from browser traffic.

Do **not** use `window.Capacitor` for this. With `server.url` set, the bridge is
injected by `WebViewLocalServer.handleProxyRequest`, which only intercepts HTML `GET`s
and calls `conn.getInputStream()` — that throws on any 4xx, and the catch falls back to
letting the WebView load the URL directly *without injecting the bridge*. So on an
auth-error page `window.Capacitor` is silently undefined. The User-Agent is set on
`WebSettings` and survives that fallback, every fetch, and every navigation.

It is also visible **server-side**, which is what the billing gate needs: the backend
can decline to render the payment link for app traffic, rather than shipping the link
and trusting client JS to hide it.
