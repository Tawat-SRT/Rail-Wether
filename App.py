import streamlit as st
import folium
from streamlit_folium import st_folium
import zipfile
import requests
import os
from fastkml import kml
from shapely.geometry import LineString

# --- ตั้งค่า ---
st.set_page_config(layout="wide", page_title="Railway Weather Monitor")
FILE_NAME = "rail_network.kmz" # เปลี่ยนชื่อไฟล์ .kmz ของคุณเป็นชื่อนี้

# --- ฟังก์ชันดึงเส้นทาง ---
@st.cache_data
def load_rail_lines(kmz_path):
    if not os.path.exists(kmz_path):
        return None
    
    lines = []
    with zipfile.ZipFile(kmz_path, 'r') as kmz:
        with kmz.open('doc.kml') as kml_file:
            k = kml.KML()
            k.from_string(kml_file.read().decode('utf-8'))
            for feature in k.features():
                # ค้นหา Geometry ในไฟล์
                if hasattr(feature, 'geometry') and feature.geometry:
                    if feature.geometry.geom_type == 'LineString':
                        lines.append(list(feature.geometry.coords))
    return lines

# --- หน้าจอ Dashboard ---
st.title("🚄 ระบบแจ้งเตือนน้ำฝนบนเส้นทางรถไฟ")

# โหลดข้อมูล
rail_paths = load_rail_lines(FILE_NAME)

if rail_paths is None:
    st.error(f"ไม่พบไฟล์ {FILE_NAME} กรุณาตรวจสอบว่าชื่อไฟล์ถูกต้องและอยู่ในโฟลเดอร์เดียวกับ App.py")
else:
    # สร้างแผนที่
    m = folium.Map(location=[13.75, 100.5], zoom_start=6)
    
    # วาดเส้นทาง
    for path in rail_paths:
        folium.PolyLine([(lat, lon) for lon, lat in path], color="blue", weight=2).add_to(m)
    
    # จัดหน้าจอ
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("แผนที่เส้นทางรถไฟ")
        st_folium(m, width=900, height=500)
    
    with col2:
        st.subheader("สถานะความเสี่ยง")
        # จำลองข้อมูลน้ำฝน
        st.metric("ปริมาณน้ำฝน", "25 มม./ชม.")
        st.success("สถานะ: ปลอดภัย")
        
        if st.button("รีเฟรชข้อมูลล่าสุด"):
            st.rerun()

st.info("ใช้ข้อมูลจากโครงข่ายทางรถไฟ (รฟท.) และ API สภาพอากาศ")
