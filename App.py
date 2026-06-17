import streamlit as st
import folium
from streamlit_folium import st_folium
import zipfile
import os
from fastkml import kml
from shapely.geometry import LineString

# --- ตั้งค่า ---
st.set_page_config(layout="wide", page_title="Railway Weather Monitor")
FILE_NAME = "rail_network.kmz" 

# --- ฟังก์ชันอ่าน KML แบบ Recursive (แก้ปัญหา TypeError/AttributeError) ---
def parse_features(features, rail_lines):
    for feature in features:
        # ถ้าเจอ Folder/Document ให้เข้าไปหาต่อ
        if hasattr(feature, 'features') and feature.features:
            parse_features(feature.features(), rail_lines)
        # ถ้าเจอ Placemark และมี Geometry ประเภท LineString
        elif hasattr(feature, 'geometry') and feature.geometry:
            if feature.geometry.geom_type == 'LineString':
                rail_lines.append(list(feature.geometry.coords))

@st.cache_data
def load_rail_lines(kmz_path):
    if not os.path.exists(kmz_path):
        return None
    
    rail_lines = []
    with zipfile.ZipFile(kmz_path, 'r') as kmz:
        # อ่านไฟล์ kml ภายใน
        with kmz.open('doc.kml') as kml_file:
            k = kml.KML()
            k.from_string(kml_file.read().decode('utf-8'))
            # วนลูปเริ่มจาก root features
            parse_features(list(k.features()), rail_lines)
    return rail_lines

# --- ส่วนแสดงผล Dashboard ---
st.title("🚄 ระบบแจ้งเตือนน้ำฝนบนเส้นทางรถไฟ")

rail_paths = load_rail_lines(FILE_NAME)

if rail_paths is None:
    st.error(f"ไม่พบไฟล์ {FILE_NAME} ในระบบ")
else:
    # สร้างแผนที่
    m = folium.Map(location=[13.75, 100.5], zoom_start=6, tiles="CartoDB positron")
    
    # วาดเส้นทางรถไฟ
    for path in rail_paths:
        # folium ใช้ (lat, lon) แต่ kml มักจะเป็น (lon, lat)
        folium.PolyLine([(lat, lon) for lon, lat in path], color="#2980b9", weight=3, opacity=0.7).add_to(m)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st_folium(m, width=900, height=600)
    
    with col2:
        st.subheader("สถานะการเดินรถ")
        st.info("ระบบตรวจสอบข้อมูลล่าสุด")
        # ใส่ฟังก์ชันเรียก API ตรงนี้ในอนาคต
        st.metric("ความเสี่ยงน้ำท่วม", "ต่ำ", delta="-5%")
        st.success("ทุกเส้นทางอยู่ในสถานะปกติ")

#
