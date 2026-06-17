import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import xml.etree.ElementTree as ET
import zipfile
import os
import math
from datetime import datetime

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rail Weather Monitor",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Thai:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans Thai', sans-serif;
}

.stApp {
    background: #0a0e1a;
    color: #e0e8ff;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0d1220;
    border-right: 1px solid #1e2d4a;
}
section[data-testid="stSidebar"] * {
    color: #b0c4de !important;
}

/* Title */
.rail-header {
    background: linear-gradient(135deg, #0d1f3c 0%, #162040 50%, #0d2a1a 100%);
    border: 1px solid #1e3a5f;
    border-left: 4px solid #00d4ff;
    border-radius: 4px;
    padding: 20px 28px;
    margin-bottom: 24px;
}
.rail-header h1 {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.6rem;
    font-weight: 600;
    color: #00d4ff;
    margin: 0 0 4px 0;
    letter-spacing: 0.05em;
}
.rail-header p {
    color: #7a9ec0;
    font-size: 0.85rem;
    margin: 0;
    font-family: 'IBM Plex Mono', monospace;
}

/* Metric cards */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin: 16px 0;
}
.metric-card {
    background: #0d1a2e;
    border: 1px solid #1e3a5f;
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}
.metric-card .label {
    font-size: 0.72rem;
    color: #5a7a9a;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}
.metric-card .value {
    font-size: 1.6rem;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
}
.metric-card .unit {
    font-size: 0.75rem;
    color: #5a7a9a;
    margin-top: 2px;
}

/* Alert cards */
.alert-critical { background:#1a0810; border:1px solid #ff3366; border-left:4px solid #ff3366; border-radius:6px; padding:14px 18px; margin:8px 0; }
.alert-warning  { background:#1a1208; border:1px solid #ffaa00; border-left:4px solid #ffaa00; border-radius:6px; padding:14px 18px; margin:8px 0; }
.alert-normal   { background:#081a10; border:1px solid #00cc66; border-left:4px solid #00cc66; border-radius:6px; padding:14px 18px; margin:8px 0; }

.alert-critical .al-title { color:#ff3366; font-weight:700; font-size:0.9rem; }
.alert-warning  .al-title { color:#ffaa00; font-weight:700; font-size:0.9rem; }
.alert-normal   .al-title { color:#00cc66; font-weight:700; font-size:0.9rem; }
.al-body { color:#b0c4de; font-size:0.82rem; margin-top:4px; }

/* Section label */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #00d4ff;
    border-bottom: 1px solid #1e3a5f;
    padding-bottom: 6px;
    margin: 20px 0 14px 0;
}

/* Segment table */
.seg-row { display:flex; align-items:center; padding:10px 14px; border-bottom:1px solid #111d2e; gap:12px; }
.seg-row:hover { background:#0d1a2e; }
.seg-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.seg-name { flex:1; font-size:0.82rem; color:#c0d4f0; }
.seg-rain { font-family:'IBM Plex Mono',monospace; font-size:0.8rem; width:70px; text-align:right; }
.seg-badge { font-size:0.68rem; padding:2px 7px; border-radius:10px; font-family:'IBM Plex Mono',monospace; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Constants ─────────────────────────────────────────────────────────────────
OWM_BASE = "https://api.openweathermap.org/data/2.5"
TMD_BASE = "https://data.tmd.go.th/api/v1"

RAIN_CRITICAL = 35   # mm/hr → danger
RAIN_WARNING  = 10
RAIN_WATCH    = 2

# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_kmz_centroids(kmz_path: str):
    """Extract one representative centroid per polygon from KMZ."""
    centroids = []
    with zipfile.ZipFile(kmz_path) as z:
        kml_name = [n for n in z.namelist() if n.endswith('.kml')][0]
        kml_bytes = z.read(kml_name)
    root = ET.fromstring(kml_bytes)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    for poly in root.findall('.//kml:Polygon', ns):
        coords_el = poly.find('.//kml:coordinates', ns)
        if coords_el is None:
            continue
        pts = []
        for tok in coords_el.text.strip().split():
            parts = tok.split(',')
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            centroids.append({'lon': round(cx, 4), 'lat': round(cy, 4)})
    return centroids


def fetch_owm_weather(lat, lon, api_key):
    """Fetch current weather from OpenWeatherMap."""
    url = f"{OWM_BASE}/weather"
    params = {'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric', 'lang': 'th'}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        d = r.json()
        rain = d.get('rain', {}).get('1h', 0) or 0
        return {
            'temp':        d['main']['temp'],
            'humidity':    d['main']['humidity'],
            'wind_speed':  d['wind']['speed'],
            'description': d['weather'][0]['description'],
            'rain_1h':     rain,
            'icon':        d['weather'][0]['icon'],
            'city':        d.get('name', ''),
        }
    except Exception as e:
        return None


def fetch_owm_forecast(lat, lon, api_key):
    """Fetch 3-day forecast for max rain."""
    url = f"{OWM_BASE}/forecast"
    params = {'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric', 'cnt': 24}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        d = r.json()
        max_rain = 0
        for item in d.get('list', []):
            rain = item.get('rain', {}).get('3h', 0) or 0
            max_rain = max(max_rain, rain / 3)
        return max_rain
    except Exception:
        return 0


def rain_level(mm_hr):
    if mm_hr >= RAIN_CRITICAL: return 'critical', '#ff3366'
    if mm_hr >= RAIN_WARNING:  return 'warning',  '#ffaa00'
    if mm_hr >= RAIN_WATCH:    return 'watch',    '#ffdd55'
    return 'normal', '#00cc66'


def get_marker_color(level):
    return {'critical': 'red', 'warning': 'orange', 'watch': 'beige', 'normal': 'green'}.get(level, 'blue')


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def region_name(lat, lon):
    """Rough Thai region from coordinates."""
    if lat > 16.0:   return "ภาคเหนือ"
    if lat > 13.5:   return "ภาคกลาง-เหนือ"
    if lat > 12.0:   return "ภาคกลาง"
    if lat > 10.0:   return "ภาคตะวันออก/ตะวันตก"
    return "ภาคใต้"


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ การตั้งค่า")
    api_source = st.radio("แหล่งข้อมูลอากาศ", ["OpenWeatherMap", "TMD (กรมอุตุฯ)"], index=0)

    if api_source == "OpenWeatherMap":
        owm_key = st.text_input("OWM API Key", type="password",
                                value=st.secrets.get("OWM_TOKEN", ""),
                                placeholder="ใส่ API Key ของ OpenWeatherMap")
        tmd_key = ""
    else:
        tmd_key = st.text_input("TMD API Token", type="password",
                                value=st.secrets.get("TMD_TOKEN", ""),
                                placeholder="ใส่ JWT Token ของกรมอุตุฯ")
        owm_key = ""

    st.markdown("---")
    st.markdown("**ตัวกรองพื้นที่**")
    show_critical = st.checkbox("🔴 วิกฤต (≥35 mm/hr)", value=True)
    show_warning  = st.checkbox("🟡 เฝ้าระวัง (≥10 mm/hr)", value=True)
    show_watch    = st.checkbox("🟡 ต้องติดตาม (≥2 mm/hr)", value=True)
    show_normal   = st.checkbox("🟢 ปกติ", value=True)
    st.markdown("---")

    max_points = st.slider("จำนวนจุดตรวจวัด", 5, 37, 20,
                           help="ลดจำนวนเพื่อเพิ่มความเร็วในการดึงข้อมูล")
    refresh = st.button("🔄 รีเฟรชข้อมูล", use_container_width=True)
    st.markdown(f"<div style='font-size:0.72rem;color:#3a5a7a;margin-top:8px'>อัพเดตล่าสุด: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rail-header">
  <h1>🚆 RAIL WEATHER MONITOR</h1>
  <p>ระบบแจ้งเตือนสภาพอากาศและปริมาณน้ำฝนตามแนวเส้นทางรถไฟไทย · Right of Way Weather Alert</p>
</div>
""", unsafe_allow_html=True)

# ─── Load KMZ ──────────────────────────────────────────────────────────────────
KMZ_PATH = "/mnt/user-data/uploads/rail_network.kmz"

@st.cache_data
def get_centroids(path):
    return load_kmz_centroids(path)

centroids = get_centroids(KMZ_PATH)
centroids = centroids[:max_points]

# ─── Fetch weather ─────────────────────────────────────────────────────────────
if 'weather_data' not in st.session_state or refresh:
    st.session_state.weather_data = []

need_key = (api_source == "OpenWeatherMap" and owm_key) or (api_source == "TMD (กรมอุตุฯ)" and tmd_key)

results = []
if need_key and (not st.session_state.weather_data or refresh):
    prog = st.progress(0, text="กำลังดึงข้อมูลสภาพอากาศ...")
    for i, c in enumerate(centroids):
        w = fetch_owm_weather(c['lat'], c['lon'], owm_key) if api_source == "OpenWeatherMap" else None
        if w:
            level, color = rain_level(w['rain_1h'])
            results.append({**c, **w, 'level': level, 'color': color,
                            'region': region_name(c['lat'], c['lon']), 'idx': i})
        prog.progress((i+1)/len(centroids), text=f"กำลังดึงข้อมูล... ({i+1}/{len(centroids)})")
    prog.empty()
    st.session_state.weather_data = results
elif st.session_state.weather_data:
    results = st.session_state.weather_data

# ─── Demo mode fallback ────────────────────────────────────────────────────────
if not results and not need_key:
    import random
    random.seed(42)
    demo_rains = [0, 0, 1.2, 0.5, 0, 15.3, 0, 42.0, 0, 3.1, 0.2, 0, 8.7, 0, 55.0,
                  0, 0, 2.3, 0, 0.8, 0, 0, 12.4, 0, 0, 1.5, 0, 0, 0, 22.1, 0, 0, 4.5, 0, 0, 0, 0]
    for i, c in enumerate(centroids):
        rain = demo_rains[i] if i < len(demo_rains) else 0
        level, color = rain_level(rain)
        results.append({
            **c, 'level': level, 'color': color,
            'rain_1h': rain, 'temp': 28+random.uniform(-3,3),
            'humidity': 70+random.randint(-10,20),
            'wind_speed': random.uniform(1,8),
            'description': 'ฝนตกหนัก' if rain > 10 else ('มีฝนเล็กน้อย' if rain > 0 else 'ท้องฟ้าแจ่มใส'),
            'region': region_name(c['lat'], c['lon']), 'idx': i, 'city': ''
        })
    st.session_state.weather_data = results

if not results:
    st.info("💡 ใส่ API Key ของ OpenWeatherMap ในแถบด้านซ้าย หรือทดสอบด้วยโหมด Demo (ปิด API Key ไว้)")
    st.stop()

# ─── Filter ────────────────────────────────────────────────────────────────────
visible_levels = []
if show_critical: visible_levels.append('critical')
if show_warning:  visible_levels.append('warning')
if show_watch:    visible_levels.append('watch')
if show_normal:   visible_levels.append('normal')
filtered = [r for r in results if r['level'] in visible_levels]

# ─── Summary metrics ───────────────────────────────────────────────────────────
n_crit = sum(1 for r in results if r['level'] == 'critical')
n_warn = sum(1 for r in results if r['level'] == 'warning')
n_watch = sum(1 for r in results if r['level'] == 'watch')
max_rain = max((r['rain_1h'] for r in results), default=0)
avg_temp = sum(r['temp'] for r in results) / len(results) if results else 0
avg_hum  = sum(r['humidity'] for r in results) / len(results) if results else 0

def val_color(v, thresholds, colors):
    for t, c in zip(thresholds, colors):
        if v >= t: return c
    return colors[-1]

crit_c  = '#ff3366' if n_crit > 0 else '#00cc66'
warn_c  = '#ffaa00' if n_warn > 0 else '#00cc66'
watch_c = '#ffdd55' if n_watch > 0 else '#00cc66'
rain_c  = val_color(max_rain, [RAIN_CRITICAL, RAIN_WARNING, RAIN_WATCH], ['#ff3366','#ffaa00','#ffdd55'])

st.markdown(f"""
<div class="metric-grid">
  <div class="metric-card">
    <div class="label">จุดวิกฤต</div>
    <div class="value" style="color:{crit_c}">{n_crit}</div>
    <div class="unit">≥ 35 mm/hr</div>
  </div>
  <div class="metric-card">
    <div class="label">เฝ้าระวัง</div>
    <div class="value" style="color:{warn_c}">{n_warn}</div>
    <div class="unit">≥ 10 mm/hr</div>
  </div>
  <div class="metric-card">
    <div class="label">ต้องติดตาม</div>
    <div class="value" style="color:{watch_c}">{n_watch}</div>
    <div class="unit">≥ 2 mm/hr</div>
  </div>
  <div class="metric-card">
    <div class="label">ฝนสูงสุด</div>
    <div class="value" style="color:{rain_c}">{max_rain:.1f}</div>
    <div class="unit">mm/hr</div>
  </div>
  <div class="metric-card">
    <div class="label">อุณหภูมิเฉลี่ย</div>
    <div class="value" style="color:#00aaff">{avg_temp:.1f}°</div>
    <div class="unit">เซลเซียส</div>
  </div>
  <div class="metric-card">
    <div class="label">ความชื้นเฉลี่ย</div>
    <div class="value" style="color:#7799ff">{avg_hum:.0f}%</div>
    <div class="unit">สัมพัทธ์</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Alert summary ─────────────────────────────────────────────────────────────
if n_crit > 0:
    crit_pts = [r for r in results if r['level'] == 'critical']
    locs = ', '.join(f"({r['lat']:.2f}°N, {r['lon']:.2f}°E) {r['rain_1h']:.1f} mm/hr" for r in crit_pts[:3])
    st.markdown(f"""
    <div class="alert-critical">
      <div class="al-title">🔴 แจ้งเตือนระดับวิกฤต — {n_crit} จุด</div>
      <div class="al-body">ปริมาณน้ำฝนเกินขีดวิกฤต 35 mm/hr: {locs}{'...' if len(crit_pts)>3 else ''}</div>
      <div class="al-body" style="margin-top:4px;color:#ff6688">⚠️ แนะนำให้ชะลอหรือหยุดการเดินรถในพื้นที่ดังกล่าว</div>
    </div>""", unsafe_allow_html=True)

if n_warn > 0:
    warn_pts = [r for r in results if r['level'] == 'warning']
    locs = ', '.join(f"({r['lat']:.2f}°N, {r['lon']:.2f}°E)" for r in warn_pts[:4])
    st.markdown(f"""
    <div class="alert-warning">
      <div class="al-title">🟡 เฝ้าระวัง — {n_warn} จุด</div>
      <div class="al-body">ปริมาณน้ำฝน 10-35 mm/hr: {locs}{'...' if len(warn_pts)>4 else ''}</div>
      <div class="al-body" style="margin-top:4px">⚠️ ให้พนักงานขับรถลดความเร็วและระมัดระวัง</div>
    </div>""", unsafe_allow_html=True)

if n_crit == 0 and n_warn == 0:
    st.markdown("""
    <div class="alert-normal">
      <div class="al-title">✅ สถานการณ์ปกติ</div>
      <div class="al-body">ไม่พบจุดที่มีปริมาณน้ำฝนเกินขีดเฝ้าระวัง — เส้นทางรถไฟทุกสาย ปลอดภัย</div>
    </div>""", unsafe_allow_html=True)

# ─── Map + Table columns ────────────────────────────────────────────────────────
col_map, col_table = st.columns([3, 2])

with col_map:
    st.markdown('<div class="section-label">แผนที่เส้นทางรถไฟ</div>', unsafe_allow_html=True)

    center_lat = sum(r['lat'] for r in filtered) / len(filtered) if filtered else 13.5
    center_lon = sum(r['lon'] for r in filtered) / len(filtered) if filtered else 101.0
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='CartoDB dark_matter',
    )

    # Draw KMZ polygon outlines lightly
    try:
        with zipfile.ZipFile(KMZ_PATH) as z:
            kml_bytes = z.read('doc.kml')
        root_kml = ET.fromstring(kml_bytes)
        ns_k = {'kml': 'http://www.opengis.net/kml/2.2'}
        for poly in root_kml.findall('.//kml:Polygon', ns_k)[:20]:
            cel = poly.find('.//kml:coordinates', ns_k)
            if cel is not None:
                coords = []
                for tok in cel.text.strip().split():
                    parts = tok.split(',')
                    if len(parts) >= 2:
                        try: coords.append([float(parts[1]), float(parts[0])])
                        except: pass
                if len(coords) > 3:
                    folium.PolyLine(coords, color='#00d4ff', weight=1.5, opacity=0.25).add_to(m)
    except Exception:
        pass

    # Markers
    for r in filtered:
        level = r['level']
        mc = {'critical':'#ff3366','warning':'#ffaa00','watch':'#ffdd55','normal':'#00cc66'}.get(level,'#aaaaaa')
        popup_html = f"""
        <div style="font-family:monospace;font-size:12px;background:#0d1220;color:#c0d8f0;padding:10px;border-radius:6px;min-width:200px">
          <b style="color:{mc}">{level.upper()} — {r['region']}</b><br>
          🌧 ฝน: <b style="color:{mc}">{r['rain_1h']:.1f} mm/hr</b><br>
          🌡 อุณหภูมิ: {r['temp']:.1f} °C<br>
          💧 ความชื้น: {r['humidity']}%<br>
          💨 ลม: {r['wind_speed']:.1f} m/s<br>
          📍 {r['lat']:.4f}°N, {r['lon']:.4f}°E
        </div>"""

        radius = 10 if level == 'critical' else (8 if level == 'warning' else 6)
        folium.CircleMarker(
            location=[r['lat'], r['lon']],
            radius=radius,
            color=mc, fill=True, fill_color=mc, fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{r['region']} — {r['rain_1h']:.1f} mm/hr"
        ).add_to(m)

    st_folium(m, width=None, height=480, returned_objects=[])

with col_table:
    st.markdown('<div class="section-label">รายการจุดตรวจวัด</div>', unsafe_allow_html=True)

    # Sort: critical first
    sort_order = {'critical':0,'warning':1,'watch':2,'normal':3}
    sorted_r = sorted(filtered, key=lambda x: (sort_order[x['level']], -x['rain_1h']))

    rows_html = ""
    for r in sorted_r[:30]:
        mc = {'critical':'#ff3366','warning':'#ffaa00','watch':'#ffdd55','normal':'#00cc66'}.get(r['level'],'#aaa')
        badge_bg = {'critical':'#2a0818','warning':'#2a1a00','watch':'#1a1800','normal':'#081a08'}.get(r['level'],'#111')
        rows_html += f"""
        <div class="seg-row">
          <div class="seg-dot" style="background:{mc}"></div>
          <div class="seg-name">{r['region']}<br>
            <span style="font-size:0.68rem;color:#3a5a7a">{r['lat']:.2f}°N {r['lon']:.2f}°E</span>
          </div>
          <div class="seg-rain" style="color:{mc}">{r['rain_1h']:.1f}<span style="font-size:0.65rem;color:#5a7a9a"> mm/hr</span></div>
          <span class="seg-badge" style="background:{badge_bg};color:{mc};border:1px solid {mc}40">{r['level'].upper()}</span>
        </div>"""

    st.markdown(f"""
    <div style="background:#0a0e1a;border:1px solid #1e3a5f;border-radius:6px;max-height:460px;overflow-y:auto">
    {rows_html}
    </div>""", unsafe_allow_html=True)

# ─── Detail section ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">ข้อมูลสภาพอากาศตามภาค</div>', unsafe_allow_html=True)
regions_order = ["ภาคเหนือ","ภาคกลาง-เหนือ","ภาคกลาง","ภาคตะวันออก/ตะวันตก","ภาคใต้"]

for region in regions_order:
    pts = [r for r in results if r['region'] == region]
    if not pts: continue
    max_r = max(p['rain_1h'] for p in pts)
    level, mc = rain_level(max_r)
    with st.expander(f"{'🔴' if level=='critical' else '🟡' if level in ('warning','watch') else '🟢'} {region} — {len(pts)} จุด · สูงสุด {max_r:.1f} mm/hr"):
        c1, c2, c3 = st.columns(3)
        for i, p in enumerate(sorted(pts, key=lambda x: -x['rain_1h'])):
            col = [c1, c2, c3][i % 3]
            lv, lc = rain_level(p['rain_1h'])
            with col:
                st.markdown(f"""
                <div style="background:#0d1a2e;border:1px solid #1e3a5f;border-left:3px solid {lc};border-radius:4px;padding:10px;margin-bottom:8px;font-size:0.8rem">
                  <div style="color:{lc};font-weight:700;font-family:monospace">{p['rain_1h']:.1f} mm/hr</div>
                  <div style="color:#7a9ec0">{p['description']}</div>
                  <div style="color:#5a7a9a;font-size:0.72rem">🌡 {p['temp']:.1f}°C · 💧 {p['humidity']}% · 💨 {p['wind_speed']:.1f} m/s</div>
                  <div style="color:#3a5a7a;font-size:0.68rem;margin-top:2px">{p['lat']:.3f}°N {p['lon']:.3f}°E</div>
                </div>""", unsafe_allow_html=True)

# ─── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:32px;padding:16px;border-top:1px solid #1e3a5f;text-align:center;font-size:0.72rem;color:#3a5a7a;font-family:monospace">
  RAIL WEATHER MONITOR · ข้อมูลจาก OpenWeatherMap / กรมอุตุนิยมวิทยา · Right of Way: การรถไฟแห่งประเทศไทย
</div>""", unsafe_allow_html=True)
