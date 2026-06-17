import requests

# ใช้ Token ที่คุณได้รับมา
TMD_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..." # ใส่ Token เต็มของคุณที่นี่

def get_rainfall_tmd(lat, lon):
    """
    ดึงข้อมูลน้ำฝนจากสถานีตรวจวัดที่ใกล้ที่สุดของ TMD
    """
    # URL ของ TMD อาจเปลี่ยนแปลงตาม Endpoint ที่คุณเลือกใช้
    # ตัวอย่าง: ใช้ API สำหรับดึงข้อมูลสภาพอากาศปัจจุบัน
    url = "https://data.tmd.go.th/api/v1/Weather/Current"
    
    headers = {
        "Authorization": f"Bearer {TMD_TOKEN}",
        "Accept": "application/json"
    }
    
    # อาจต้องส่ง params เช่น พิกัด หรือรหัสสถานี (ขึ้นอยู่กับ documentation ของ Endpoint นั้นๆ)
    params = {
        "lat": lat,
        "lon": lon
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # NOTE: การ parse ข้อมูลต้องดูจากโครงสร้าง JSON ที่ TMD ส่งกลับมาจริง 
        # (คุณสามารถใช้ print(data) เพื่อดูโครงสร้างก่อนนำไปใช้งาน)
        # ตัวอย่างสมมติ:
        # return data['WeatherElement']['Rainfall']['Value']
        return 0 # เปลี่ยนเป็น path ของค่าฝนจริง
    except Exception as e:
        print(f"Error calling TMD API: {e}")
        return 0