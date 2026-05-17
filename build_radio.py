#!/usr/bin/env python3
"""
Free Internet Radio Builder
Fetches stations from the radio-browser.info public API (no key required)
and generates a self-contained HTML player with genre browser and search.

Usage:
  python3 build_radio.py           # generates free_radio.html
  python3 build_radio.py --help
"""

import urllib.request
import urllib.parse
import json
import os
import sys
from datetime import datetime

# radio-browser.info mirror nodes (use any, they are kept in sync)
API_SERVERS = [
    "https://de1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
]

GENRES = [
    "pop", "rock", "jazz", "classical", "blues", "country",
    "hip-hop", "electronic", "ambient", "metal", "folk",
    "reggae", "latin", "soul", "r&b", "indie", "punk",
    "news", "talk", "sports",
]

LIMIT_PER_GENRE = 80   # stations fetched per genre
MIN_BITRATE     = 48   # kbps — skip very low quality streams
OUTPUT_PATH     = "free_radio.html"

def fetch_json(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FreeRadioBuilder/1.0",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ✗ {url}: {e}")
        return None

def pick_server():
    for s in API_SERVERS:
        result = fetch_json(f"{s}/json/stats")
        if result:
            print(f"  Using server: {s}")
            return s
    raise RuntimeError("All radio-browser servers unreachable")

def fetch_genre(server, tag, limit):
    tag_enc = urllib.parse.quote(tag)
    url = (
        f"{server}/json/stations/search"
        f"?tag={tag_enc}"
        f"&limit={limit}"
        f"&order=clickcount"
        f"&reverse=true"
        f"&hidebroken=true"
        f"&is_https=true"
    )
    data = fetch_json(url)
    return data or []

def clean_station(s, genre):
    """Normalize a station dict from the API."""
    return {
        "name":     (s.get("name") or "").strip() or "Unknown",
        "url":      s.get("url_resolved") or s.get("url") or "",
        "favicon":  s.get("favicon") or "",
        "genre":    genre,
        "tags":     s.get("tags") or "",
        "country":  s.get("country") or "",
        "language": s.get("language") or "",
        "bitrate":  int(s.get("bitrate") or 0),
        "codec":    (s.get("codec") or "").upper(),
        "votes":    int(s.get("votes") or 0),
        "uuid":     s.get("stationuuid") or "",
    }

def is_playable(s):
    url = s["url"].lower()
    if not url.startswith("http"):
        return False
    # skip playlists-of-playlists (PLS, XSPF, ASX) — browser Audio can't play them
    if url.endswith(".pls") or url.endswith(".xspf") or url.endswith(".asx"):
        return False
    if s["bitrate"] and s["bitrate"] < MIN_BITRATE:
        return False
    return True

def deduplicate(stations):
    seen_urls  = set()
    seen_names = set()
    out = []
    for s in stations:
        uk = s["url"]
        nk = s["name"].lower()
        if uk in seen_urls or nk in seen_names:
            continue
        seen_urls.add(uk)
        seen_names.add(nk)
        out.append(s)
    return out

def generate_html(stations, output_path):
    data_str  = json.dumps(stations, ensure_ascii=False)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    count     = len(stations)
    genres    = sorted(set(s["genre"] for s in stations))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FREE.RADIO — Internet Radio</title>
<style>
:root {{
  --bg: #080810;
  --panel: #0f0f1a;
  --card: #16162a;
  --border: #252540;
  --accent: #00e5ff;
  --accent2: #a855f7;
  --text: #dde0f5;
  --muted: #555580;
  --green: #00ff88;
  --red: #ff4466;
  --active-bg: rgba(0,229,255,0.08);
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; background: var(--bg); color: var(--text);
  font-family: 'Courier New', 'Lucida Console', monospace; overflow: hidden; }}

#app {{ display: grid; grid-template-rows: 68px 1fr; grid-template-columns: 340px 1fr; height: 100vh; }}

/* ── Topbar ── */
#topbar {{ grid-column: 1/-1;
  background: linear-gradient(90deg,#0a0020 0%,#1a0050 20%,#0d1a60 40%,#003060 60%,#001a40 80%,#0a0020 100%);
  border-bottom: 2px solid transparent;
  border-image: linear-gradient(90deg,var(--accent2),var(--accent),var(--accent2)) 1;
  box-shadow: 0 2px 30px rgba(0,229,255,0.15),inset 0 -1px 0 rgba(168,85,247,0.3);
  display: flex; align-items: center; gap: 14px; padding: 0 20px; }}
.logo {{ font-size: 26px; font-weight: bold; letter-spacing: 6px; white-space: nowrap;
  background: linear-gradient(90deg,#00e5ff,#a855f7,#00e5ff); background-size: 200% auto;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  animation: shimmer 4s linear infinite;
  filter: drop-shadow(0 0 12px rgba(0,229,255,0.6)); }}
@keyframes shimmer {{ 0%{{background-position:0%}} 100%{{background-position:200%}} }}
.logo em {{ font-style: normal; }}
.pulse {{ width: 9px; height: 9px; border-radius: 50%; background: var(--green);
  box-shadow: 0 0 12px var(--green); animation: blink 2s infinite; flex-shrink: 0; }}
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.2}} }}
.meta {{ font-size: 10px; color: var(--muted); flex: 1; }}
#sig-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }}
#sig-dot.live  {{ background: var(--green); box-shadow: 0 0 10px var(--green); animation: blink 1.5s infinite; }}
#sig-dot.error {{ background: var(--red); }}
#sig-dot.load  {{ background: var(--accent); animation: blink .5s infinite; }}
#sig-label {{ font-size: 10px; color: var(--muted); width: 90px; }}

/* ── Sidebar ── */
#sidebar {{ background: var(--panel); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden; }}
#main {{ display: flex; flex-direction: column; overflow: hidden; background: #000; }}

/* channel search */
#ch-search-wrap {{ padding: 8px 10px; border-bottom: 1px solid var(--border);
  flex-shrink: 0; position: relative; }}
#ch-search-wrap::before {{ content: '⌕'; position: absolute; left: 19px; top: 50%;
  transform: translateY(-50%); color: var(--muted); font-size: 14px; pointer-events: none; }}
#ch-search {{ width: 100%; background: var(--card); border: 1px solid var(--border);
  color: var(--text); padding: 6px 10px 6px 28px; border-radius: 3px;
  font-family: inherit; font-size: 12px; outline: none; transition: border-color .2s; }}
#ch-search:focus {{ border-color: var(--accent); }}
#ch-search::placeholder {{ color: var(--muted); }}

/* genre filter */
#genre-bar {{ display: flex; gap: 4px; padding: 6px 8px; overflow-x: auto;
  border-bottom: 1px solid var(--border); flex-shrink: 0; scrollbar-width: none; }}
#genre-bar::-webkit-scrollbar {{ display: none; }}
.grp {{ background: transparent; border: 1px solid var(--border); color: var(--muted);
  padding: 2px 9px; border-radius: 20px; cursor: pointer; font-size: 10px;
  font-family: inherit; white-space: nowrap; transition: all .15s; text-transform: uppercase; }}
.grp:hover {{ border-color: var(--accent); color: var(--accent); }}
.grp.on {{ background: var(--accent); border-color: var(--accent); color: #000; font-weight: bold; }}

/* station list */
#st-count {{ padding: 5px 12px; font-size: 10px; color: var(--muted);
  border-bottom: 1px solid var(--border); flex-shrink: 0; letter-spacing: .5px; }}
#st-list {{ flex: 1; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }}
#st-list::-webkit-scrollbar {{ width: 4px; }}
#st-list::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
.st {{ display: flex; align-items: center; gap: 11px; padding: 10px 12px;
  cursor: pointer; border-left: 3px solid transparent;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  transition: background .1s, border-left-color .1s; }}
.st:hover {{ background: var(--card); }}
.st.on {{ background: var(--active-bg); border-left-color: var(--accent); }}
.st-logo {{ width: 40px; height: 40px; object-fit: contain; flex-shrink: 0;
  background: rgba(255,255,255,0.04); border-radius: 4px; padding: 3px; }}
.st-ph {{ width: 40px; height: 40px; background: rgba(255,255,255,0.04); border-radius: 4px;
  display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }}
.st-info {{ flex: 1; min-width: 0; }}
.st-name {{ font-size: 13px; font-weight: 500; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; color: var(--text); line-height: 1.3; }}
.st.on .st-name {{ color: var(--accent); }}
.st-sub {{ font-size: 10px; color: var(--muted); margin-top: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.st-badge {{ font-size: 9px; padding: 1px 5px; border-radius: 2px;
  background: rgba(168,85,247,0.15); color: var(--accent2);
  border: 1px solid rgba(168,85,247,0.3); flex-shrink: 0; }}
.st-empty {{ padding: 40px 20px; text-align: center; color: var(--muted);
  font-size: 12px; line-height: 1.8; }}

/* ── Player panel ── */
#main {{ position: relative; }}
#player-area {{ flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 20px;
  background: radial-gradient(ellipse at center, #0d0d20 0%, #000 100%);
  position: relative; overflow: hidden; }}

/* animated background rings */
#player-area::before {{
  content: ''; position: absolute;
  width: 500px; height: 500px; border-radius: 50%;
  border: 1px solid rgba(0,229,255,0.05);
  animation: ring-pulse 4s ease-in-out infinite;
}}
#player-area::after {{
  content: ''; position: absolute;
  width: 340px; height: 340px; border-radius: 50%;
  border: 1px solid rgba(168,85,247,0.08);
  animation: ring-pulse 4s ease-in-out infinite .8s;
}}
@keyframes ring-pulse {{
  0%,100% {{ transform: scale(1); opacity: .4; }}
  50% {{ transform: scale(1.08); opacity: 1; }}
}}

#album-art {{ width: 120px; height: 120px; border-radius: 8px;
  background: var(--card); object-fit: contain; padding: 8px;
  box-shadow: 0 0 40px rgba(0,229,255,0.1);
  border: 1px solid var(--border); position: relative; z-index: 1; }}
#album-art.spinning {{ animation: spin 8s linear infinite; border-radius: 50%;
  box-shadow: 0 0 40px rgba(168,85,247,0.3); }}
@keyframes spin {{ from{{transform:rotate(0deg)}} to{{transform:rotate(360deg)}} }}
#album-ph {{ width: 120px; height: 120px; border-radius: 50%;
  background: var(--card); display: flex; align-items: center; justify-content: center;
  font-size: 48px; border: 1px solid var(--border);
  box-shadow: 0 0 40px rgba(0,229,255,0.1); position: relative; z-index: 1; }}
#album-ph.spinning {{ animation: spin 8s linear infinite;
  box-shadow: 0 0 40px rgba(168,85,247,0.3); border-color: rgba(168,85,247,0.4); }}

#station-name {{ font-size: 20px; font-weight: bold; color: var(--accent);
  letter-spacing: 2px; text-align: center; max-width: 400px;
  text-shadow: 0 0 20px rgba(0,229,255,0.4); position: relative; z-index: 1; }}
#station-meta {{ font-size: 11px; color: var(--muted); text-align: center;
  position: relative; z-index: 1; }}

/* audio visualizer bars */
#viz {{ display: flex; gap: 3px; align-items: flex-end; height: 32px;
  position: relative; z-index: 1; }}
.vbar {{ width: 4px; background: linear-gradient(to top, var(--accent2), var(--accent));
  border-radius: 2px; opacity: 0; transition: height .1s; }}
.vbar.active {{ animation: vbar-bounce var(--d, .6s) ease-in-out infinite alternate; opacity: 1; }}
@keyframes vbar-bounce {{ from{{height:3px}} to{{height:var(--h,20px)}} }}

audio {{ display: none; }}

#idle-msg {{ font-size: 13px; color: var(--muted); text-align: center;
  line-height: 1.8; position: relative; z-index: 1; }}
#idle-hint {{ font-size: 10px; color: var(--border); position: relative; z-index: 1; }}
#prog {{ position: absolute; bottom: 0; left: 0; height: 2px;
  background: linear-gradient(90deg,var(--accent2),var(--accent));
  width: 0; transition: width .4s; }}

/* controls */
#controls {{ display: flex; gap: 12px; align-items: center; position: relative; z-index: 1; }}
.ctrl-btn {{ background: transparent; border: 1px solid var(--border); color: var(--muted);
  width: 36px; height: 36px; border-radius: 50%; cursor: pointer; font-size: 14px;
  font-family: inherit; transition: all .15s; display: flex; align-items: center; justify-content: center; }}
.ctrl-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
#vol-wrap {{ display: flex; align-items: center; gap: 8px; }}
#vol-icon {{ font-size: 12px; color: var(--muted); }}
#vol {{ -webkit-appearance: none; width: 90px; height: 3px;
  background: var(--border); border-radius: 2px; outline: none; cursor: pointer; }}
#vol::-webkit-slider-thumb {{ -webkit-appearance: none; width: 12px; height: 12px;
  border-radius: 50%; background: var(--accent); cursor: pointer; }}

/* now bar */
#now-bar {{ background: var(--panel); border-top: 1px solid var(--border);
  padding: 5px 16px; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }}
#np-name {{ font-size: 12px; color: var(--accent); flex: 2; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }}
#np-genre {{ font-size: 10px; color: var(--muted); flex: 1; white-space: nowrap; }}
#np-meta {{ font-size: 9px; color: var(--border); flex: 2; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }}

/* toast */
#toast {{ position: fixed; bottom: 52px; right: 16px; background: #1a0a10;
  border: 1px solid var(--red); color: var(--red); padding: 7px 14px; border-radius: 3px;
  font-size: 11px; opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 999; max-width: 300px; }}
#toast.on {{ opacity: 1; }}
</style>
</head>
<body>
<div id="app">

  <!-- Topbar -->
  <div id="topbar">
    <div class="logo">FREE<em>.</em>RADIO</div>
    <div class="pulse"></div>
    <div class="meta" id="top-meta">{count} stations · built {timestamp}</div>
    <div id="sig-dot"></div>
    <div id="sig-label">idle</div>
  </div>

  <!-- Sidebar -->
  <div id="sidebar">
    <div id="ch-search-wrap">
      <input id="ch-search" type="search" placeholder="Search stations…" autocomplete="off">
    </div>
    <div id="genre-bar">
      <button class="grp on" data-g="ALL">ALL</button>
      {''.join(f'<button class="grp" data-g="{g}">{g}</button>' for g in genres)}
    </div>
    <div id="st-count"></div>
    <div id="st-list"><div class="st-empty">Loading stations…</div></div>
  </div>

  <!-- Main player -->
  <div id="main">
    <div id="player-area">
      <div id="album-ph">📻</div>
      <img id="album-art" style="display:none" alt="">
      <div id="station-name" style="display:none"></div>
      <div id="station-meta" style="display:none"></div>
      <div id="viz">
        {''.join(f'<div class="vbar" style="--d:{0.4+i*0.07:.2f}s;--h:{10+((i*7)%22)}px"></div>' for i in range(16))}
      </div>
      <div id="controls" style="display:none">
        <button class="ctrl-btn" id="btn-prev" title="Previous">◀</button>
        <button class="ctrl-btn" id="btn-stop" title="Stop">■</button>
        <button class="ctrl-btn" id="btn-next" title="Next">▶</button>
        <div id="vol-wrap">
          <span id="vol-icon">🔊</span>
          <input id="vol" type="range" min="0" max="1" step="0.02" value="0.8">
        </div>
      </div>
      <div id="idle-msg">Select a station from the list to start streaming.<br>
        Radio Browser: {count} free stations across {len(genres)} genres.</div>
      <div id="idle-hint">↑↓ keyboard · / search · click to tune</div>
      <audio id="aud" preload="none"></audio>
      <div id="prog"></div>
    </div>
    <div id="now-bar">
      <div id="np-name">No station selected</div>
      <div id="np-genre"></div>
      <div id="np-meta"></div>
    </div>
  </div>

</div>
<div id="toast"></div>

<script>
const STATIONS = {data_str};

let filtered = [...STATIONS], currentSt = null, activeGenre = "ALL";

const aud      = document.getElementById("aud");
const stList   = document.getElementById("st-list");
const stCount  = document.getElementById("st-count");
const chSearch = document.getElementById("ch-search");
const genreBar = document.getElementById("genre-bar");
const sigDot   = document.getElementById("sig-dot");
const sigLabel = document.getElementById("sig-label");
const topMeta  = document.getElementById("top-meta");
const npName   = document.getElementById("np-name");
const npGenre  = document.getElementById("np-genre");
const npMeta   = document.getElementById("np-meta");
const prog     = document.getElementById("prog");
const toast    = document.getElementById("toast");
const albumPh  = document.getElementById("album-ph");
const albumArt = document.getElementById("album-art");
const stName   = document.getElementById("station-name");
const stMeta   = document.getElementById("station-meta");
const controls = document.getElementById("controls");
const idleMsg  = document.getElementById("idle-msg");
const idleHint = document.getElementById("idle-hint");
const vbars    = [...document.querySelectorAll(".vbar")];
const vol      = document.getElementById("vol");

// genre filter
genreBar.addEventListener("click", e => {{
  const b = e.target.closest(".grp");
  if (!b) return;
  document.querySelectorAll(".grp").forEach(x => x.classList.remove("on"));
  b.classList.add("on");
  activeGenre = b.dataset.g;
  applyFilters();
}});

chSearch.addEventListener("input", applyFilters);

function applyFilters() {{
  const q = chSearch.value.toLowerCase().trim();
  filtered = STATIONS.filter(s =>
    (activeGenre === "ALL" || s.genre === activeGenre) &&
    (!q || s.name.toLowerCase().includes(q) ||
           s.tags.toLowerCase().includes(q) ||
           s.country.toLowerCase().includes(q))
  );
  renderList();
}}

function renderList() {{
  stCount.textContent = filtered.length + " station" + (filtered.length !== 1 ? "s" : "");
  if (!filtered.length) {{
    stList.innerHTML = `<div class="st-empty">No stations match.</div>`;
    return;
  }}
  const frag = document.createDocumentFragment();
  filtered.forEach(st => {{
    const d = document.createElement("div");
    d.className = "st" + (st === currentSt ? " on" : "");
    const codec = st.codec ? `<span class="st-badge">${{esc(st.codec)}}</span>` : "";
    const sub   = [st.country, st.bitrate ? st.bitrate + "k" : "", st.language]
                    .filter(Boolean).join(" · ");
    d.innerHTML =
      (st.favicon
        ? `<img class="st-logo" src="${{esc(st.favicon)}}" alt="" loading="lazy" onerror="this.outerHTML='<div class=st-ph>📻</div>'">`
        : `<div class="st-ph">📻</div>`) +
      `<div class="st-info">
        <div class="st-name">${{esc(st.name)}}</div>
        <div class="st-sub">${{esc(sub)}}</div>
      </div>${{codec}}`;
    d.addEventListener("click", () => tune(st, d));
    frag.appendChild(d);
  }});
  stList.innerHTML = "";
  stList.appendChild(frag);
}}

function esc(s) {{
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

function tune(st, el) {{
  currentSt = st;
  document.querySelectorAll(".st").forEach(x => x.classList.remove("on"));
  if (el) el.classList.add("on");

  // player UI
  idleMsg.style.display  = "none";
  idleHint.style.display = "none";
  controls.style.display = "flex";
  stName.style.display   = "block";
  stMeta.style.display   = "block";
  stName.textContent = st.name;
  stMeta.textContent = [st.genre.toUpperCase(), st.country, st.bitrate ? st.bitrate + " kbps" : "", st.codec]
    .filter(Boolean).join("  ·  ");

  // logo
  if (st.favicon) {{
    albumPh.style.display  = "none";
    albumArt.style.display = "block";
    albumArt.src = st.favicon;
    albumArt.onerror = () => {{ albumArt.style.display="none"; albumPh.style.display="flex"; startSpin(albumPh); }};
    startSpin(albumArt);
  }} else {{
    albumArt.style.display = "none";
    albumPh.style.display  = "flex";
    startSpin(albumPh);
  }}

  npName.textContent  = st.name;
  npGenre.textContent = st.genre;
  npMeta.textContent  = st.url;
  setSig("load", "connecting…");
  prog.style.width = "20%";
  stopViz();

  aud.pause();
  aud.src = st.url;
  aud.volume = parseFloat(vol.value);
  aud.load();
  aud.play().catch(() => {{}});
}}

function startSpin(el) {{
  albumPh.classList.remove("spinning");
  albumArt.classList.remove("spinning");
  el.classList.add("spinning");
}}
function stopSpin() {{
  albumPh.classList.remove("spinning");
  albumArt.classList.remove("spinning");
}}

// visualizer
let vizInterval;
function startViz() {{
  stopViz();
  vbars.forEach(b => b.classList.add("active"));
  vizInterval = setInterval(() => {{
    vbars.forEach(b => {{
      const h = 3 + Math.random() * 26;
      b.style.setProperty("--h", h + "px");
    }});
  }}, 120);
}}
function stopViz() {{
  clearInterval(vizInterval);
  vbars.forEach(b => {{ b.classList.remove("active"); b.style.height = "3px"; }});
}}

aud.onplaying = () => {{
  setSig("live", "▶ ON AIR");
  prog.style.width = "100%";
  setTimeout(() => {{ prog.style.width = "0"; }}, 700);
  startViz();
}};
aud.onwaiting = () => {{ setSig("load", "buffering…"); stopViz(); }};
aud.onerror   = () => {{ setSig("error", "error"); stopViz(); stopSpin(); showToast("Stream error — try another station."); }};
aud.onstalled = () => {{ setSig("load", "stalled…"); }};

// volume
vol.addEventListener("input", () => {{ aud.volume = parseFloat(vol.value); }});

// prev/next
document.getElementById("btn-prev").addEventListener("click", () => navigate(-1));
document.getElementById("btn-next").addEventListener("click", () => navigate(1));
document.getElementById("btn-stop").addEventListener("click", () => {{
  aud.pause(); aud.src = ""; setSig("", "stopped"); stopViz(); stopSpin();
}});

function navigate(dir) {{
  if (!filtered.length) return;
  const idx = filtered.indexOf(currentSt);
  let ni = (idx + dir + filtered.length) % filtered.length;
  const items = [...stList.querySelectorAll(".st")];
  tune(filtered[ni], items[ni]);
  if (items[ni]) items[ni].scrollIntoView({{ block: "nearest" }});
}}

function setSig(state, label) {{
  sigDot.className = "";
  if (state === "live")  sigDot.classList.add("live");
  if (state === "error") sigDot.classList.add("error");
  if (state === "load")  sigDot.classList.add("load");
  sigLabel.textContent = label;
}}

function showToast(msg) {{
  toast.textContent = msg;
  toast.classList.add("on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("on"), 5000);
}}

// keyboard
document.addEventListener("keydown", e => {{
  if (e.target === chSearch) return;
  if (e.key === "/") {{ e.preventDefault(); chSearch.focus(); return; }}
  if (e.key === "ArrowUp" || e.key === "ArrowDown") {{
    e.preventDefault();
    navigate(e.key === "ArrowDown" ? 1 : -1);
  }}
}});

// init
applyFilters();
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path

def main():
    print("=" * 50)
    print("  FREE.RADIO Builder")
    print("  Source: radio-browser.info (no API key)")
    print("=" * 50)

    print("\n[1] Finding best API server…")
    try:
        server = pick_server()
    except RuntimeError as e:
        print(f"\nError: {e}")
        sys.exit(1)

    print(f"\n[2] Fetching top stations per genre (limit={LIMIT_PER_GENRE})…")
    raw = []
    for genre in GENRES:
        print(f"  {genre}…", end=" ", flush=True)
        items = fetch_genre(server, genre, LIMIT_PER_GENRE)
        cleaned = [clean_station(s, genre) for s in items]
        raw.extend(cleaned)
        print(f"{len(cleaned)} stations")

    print(f"\n[3] Filtering & deduplicating…")
    playable = [s for s in raw if is_playable(s)]
    print(f"  Playable: {len(playable)} / {len(raw)}")
    unique = deduplicate(playable)
    print(f"  Unique:   {len(unique)}")
    unique.sort(key=lambda s: (s["genre"], -s["votes"], s["name"].lower()))

    print(f"\n[4] Generating HTML player…")
    out = generate_html(unique, OUTPUT_PATH)
    print(f"\n✓ Done → {out}")
    print(f"  {len(unique)} stations embedded across {len(GENRES)} genres.")
    print(f"\n  Open {OUTPUT_PATH} in your browser to listen.")

if __name__ == "__main__":
    main()
