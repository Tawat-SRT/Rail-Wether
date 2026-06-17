import streamlit as st
import folium
from streamlit_folium import st_folium
import zipfile
import requests
from fastkml import kml
from shapely.geometry import LineString

# ตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide", page_title="Railway Weather Monitor")

# ฟังก์ชันดึงข้อมูลจาก TMD API
def get_rainfall_tmd(lat, lon):
    url = "https://data.tmd.go.th/api/v1/Weather/Current"
    headers = {"Authorization": f"Bearer {st.secrets['TMD_TOKEN']}"}
    # พารามิเตอร์อาจต้องปรับตาม API Documentation ของ TMD
    params = {"lat": lat, "lon": lon}
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        # ปรับการดึงค่าตามโครงสร้าง JSON ของ TMD จริงๆ
        return data.get('rain', 0) 
    except:
        return 0

# ฟังก์ชันโหลดเส้นทางรถไฟจาก KMZ
@st.cache_data
def load_rail_lines():
    lines = []
    with zipfile.ZipFile('แผนที่โครงข่ายทางรถไฟ (OneMap of Rail Network) (Draft by กองทางถาวร รฟท.).kmz', 'r') as kmz:
        with kmz.open('doc.kml') as kml_file:
            k = kml.KML()
            k.from_string(kml_file_read().decode('utf-8'))
            for feature in k.features():
                if hasattr(feature, 'geometry') and feature.geometry:
                    lines.append(list(feature.geometry.coords))
    return lines

# Dashboard UI
st.title("ระบบแจ้งเตือนน้ำฝนบนเส้นทางรถไฟ 🚄")

# สร้างแผนที่
m = folium.Map(location=[13.75, 100.5], zoom_start=6)
rail_paths = load_rail_lines()

for path in rail_paths:
    folium.PolyLine([(lat, lon) for lon, lat in path], color="blue").add_to(m)

col1, col2 = st.columns([3, 1])
with col1:
    st_folium(m, width=900, height=500)

with col2:
    st.subheader("ตรวจสอบสภาพอากาศ")
    lat = st.number_input("ละติจูด", value=13.75)
    lon = st.number_input("ลองจิจูด", value=100.5)
    if st.button("เช็คข้อมูล"):
        rain = get_rainfall_tmd(lat, lon)
        st.metric("ปริมาณฝน", f"{rain} มม.")
