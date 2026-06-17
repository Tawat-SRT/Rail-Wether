import streamlit as st
import folium
from streamlit_folium import st_folium
import zipfile
import os
import xml.etree.ElementTree as ET

# --- ตั้งค่า ---
st.set_page_config(layout="wide", page_title="Railway Weather Monitor")
# เปลี่ยนเป็นชื่อไฟล์ที่คุณตั้งไว้
FILE_NAME = "rail_network.kmz" 

@st.cache_data
def load_rail_lines(kmz_path):
    if not os.path.exists(kmz_path):
        return None
    
    rail_lines = []
    try:
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            with kmz.open('doc.kml') as kml_file:
                # ใช้ ElementTree (ET) อ่านไฟล์ XML โดยตรง
                tree = ET.parse(kml_file)
                root = tree.getroot()
                
                # วนลูปหา 'LineString' ทั้งหมดในไฟล์ (ค้นหาแบบทะลุทะลวงทุก Folder)
                for elem in root.iter():
                    if elem.tag.endswith('LineString'):
                        # หา Tag พิกัด (coordinates)
                        for child in elem:
                            if child.tag.endswith('coordinates') and child.text:
                                coord_text = child.text.strip()
                                path = []
                                # ข้อมูล KML เป็น: lon,lat,alt lon,lat,alt ...
                                for pt in coord_text.split():
                                    parts = pt.split(',')
                                    if len(parts) >= 2:
                                        lon = float(parts[0])
                                        lat = float(parts[1])
                                        # บันทึกเป็น (Lat, Lon) สำหรับ Folium
                                        path.append((lat, lon))
                                if path:
                                    rail_lines.append(path)
        return rail_lines
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ KMZ: {e}")
        return []

# --- ส่วนแสดงผล Dashboard ---
st.title("🚄 ระบบแจ้งเตือนน้ำฝนบนเส้นทางรถไฟ")

rail_paths = load_rail_lines(FILE_NAME)

if rail_paths is None:
    st.error(f"ไม่พบไฟล์ `{FILE_NAME}` ในระบบ กรุณาอัปโหลดไฟล์ให้ถูกต้อง")
elif len(rail_paths) == 0:
    st.warning("เปิดไฟล์ได้ แต่ไม่พบข้อมูลเส้นทางในไฟล์นี้")
else:
    st.success(f"โหลดข้อมูลสำเร็จ: พบเส้นทางทั้งหมด {len(rail_paths)} เส้น")
    
    # สร้างแผนที่
    m = folium.Map(location=[13.75, 100.5], zoom_start=6, tiles="CartoDB positron")
    
    # วาดเส้นทางรถไฟ
    for path in rail_paths:
        folium.PolyLine(path, color="#2980b9", weight=2.5, opacity=0.8).add_to(m)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st_folium(m, width=900, height=600)
    
    with col2:
        st.subheader("สถานะการเดินรถ")
        st.info("ระบบตรวจสอบข้อมูลล่าสุด")
        st.metric("ความเสี่ยงน้ำท่วม", "ต่ำ")
        st.success("ทุกเส้นทางอยู่ในสถานะปกติ")
