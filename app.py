import streamlit as st
import folium
from streamlit_folium import st_folium
import zipfile
import os
import xml.etree.ElementTree as ET
import requests
import math

# --- ตั้งค่าหน้าเว็บ ---
st.set_page_config(layout="wide", page_title="Railway Weather Monitor")
FILE_NAME = "rail_network.kmz" 

# ==========================================
# ส่วนที่ 1: ระบบจัดการข้อมูลแผนที่ (KMZ/KML)
# ==========================================
@st.cache_data
def load_rail_lines(kmz_path):
    if not os.path.exists(kmz_path):
        return None
    
    rail_lines = []
    try:
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            with kmz.open('doc.kml') as kml_file:
                tree = ET.parse(kml_file)
                root = tree.getroot()
                
                for elem in root.iter():
                    if elem.tag.endswith('LineString'):
                        for child in elem:
                            if child.tag.endswith('coordinates') and child.text:
                                coord_text = child.text.strip()
                                path = []
                                for pt in coord_text.split():
                                    parts = pt.split(',')
                                    if len(parts) >= 2:
                                        lon, lat = float(parts[0]), float(parts[1])
                                        path.append((lat, lon))
                                if path:
                                    rail_lines.append(path)
        return rail_lines
    except Exception as e:
        return []

# ==========================================
# ส่วนที่ 2: ระบบเชื่อมต่อ TMD API และคำนวณระยะทาง
# ==========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """คำนวณระยะทางระหว่าง 2 พิกัด (กิโลเมตร)"""
    R = 6371.0 # รัศมีโลก
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@st.cache_data(ttl=1800) # Cache ข้อมูลไว้ 30 นาที (ลดการเรียก API ซ้ำซ้อน)
def fetch_tmd_weather():
    """ดึงข้อมูลสภาพอากาศทั้งหมดจาก TMD"""
    url = "https://data.tmd.go.th/api/WeatherToday/V2/"
    
    # ตรวจสอบว่ามีการตั้งค่า Secrets ไว้หรือไม่
    if "TMD_TOKEN" not in st.secrets:
        st.error("⚠️ ไม่พบ TMD_TOKEN ในไฟล์ st.secrets กรุณาตั้งค่าก่อนใช้งาน")
        return None

    headers = {
        "Authorization": f"Bearer {st.secrets['TMD_TOKEN']}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก API: {e}")
        return None

def get_nearest_station(weather_data, target_lat, target_lon):
    """ค้นหาสถานีที่ใกล้พิกัดเป้าหมายที่สุด"""
    if not weather_data or 'Stations' not in weather_data:
        return None, 0
    
    nearest_station = None
    min_dist = float('inf')
    
    for station in weather_data['Stations']:
        try:
            stat_lat = float(station.get('Latitude', 0))
            stat_lon = float(station.get('Longitude', 0))
            dist = haversine_distance(target_lat, target_lon, stat_lat, stat_lon)
            
            if dist < min_dist:
                min_dist = dist
                nearest_station = station
        except ValueError:
            continue
            
    return nearest_station, min_dist

# ==========================================
# ส่วนที่ 3: UI Dashboard
# ==========================================
st.title("🚄 ระบบประเมินความเสี่ยงน้ำท่วมเส้นทางรถไฟ")

rail_paths = load_rail_lines(FILE_NAME)

if rail_paths is None:
    st.error(f"ไม่พบไฟล์ `{FILE_NAME}` ในระบบ")
else:
    # 1. โหลดข้อมูลแผนที่
    m = folium.Map(location=[13.75, 100.5], zoom_start=6, tiles="CartoDB positron")
    for path in rail_paths:
        folium.PolyLine(path, color="#2980b9", weight=2.5, opacity=0.8).add_to(m)
    
    col1, col2 = st.columns([2.5, 1.5])
    
    with col1:
        st.write("แผนที่โครงข่ายทางรถไฟ")
        st_folium(m, width=800, height=550)
    
    with col2:
        st.subheader("ตรวจสอบสภาพอากาศพื้นที่")
        st.info("ระบุพิกัดที่ต้องการ เพื่อค้นหาสถานีตรวจวัดที่ใกล้ที่สุด")
        
        # ฟอร์มรับค่าพิกัด
        input_lat = st.number_input("ละติจูด (Latitude)", value=13.7500, format="%.4f")
        input_lon = st.number_input("ลองจิจูด (Longitude)", value=100.5000, format="%.4f")
        
        if st.button("🔍 ตรวจสอบความเสี่ยง", use_container_width=True):
            with st.spinner("กำลังดึงข้อมูลจากกรมอุตุนิยมวิทยา..."):
                tmd_data = fetch_tmd_weather()
                
                if tmd_data:
                    station, distance = get_nearest_station(tmd_data, input_lat, input_lon)
                    
                    if station:
                        name = station.get('StationNameThai', 'ไม่ทราบชื่อ')
                        prov = station.get('Province', 'ไม่ทราบจังหวัด')
                        
                        # ค่าฝนขึ้นอยู่กับ Endpoint (ลองใช้ Rainfall24Hr หรือปรับแต่งให้ตรงกับ JSON จริง)
                        rain = float(station.get('Observe', {}).get('Rainfall24Hr', 0))
                        
                        st.markdown("---")
                        st.write(f"📍 **สถานีอ้างอิง:** {name} จ.{prov}")
                        st.caption(f"ระยะห่างจากพิกัดเป้าหมาย: {distance:.2f} กิโลเมตร")
                        
                        st.metric("ปริมาณน้ำฝน (24 ชม.)", f"{rain} มม.")
                        
                        # ประเมินความเสี่ยง
                        if rain > 90:
                            st.error("🚨 เสี่ยงน้ำท่วมสูงมาก! ฝนตกหนักเกินเกณฑ์")
                        elif rain > 35:
                            st.warning("⚠️ เฝ้าระวัง: ฝนตกปานกลางถึงหนัก")
                        else:
                            st.success("✅ สถานะปกติ")
                    else:
                        st.warning("ไม่พบข้อมูลสถานีในระบบ")
