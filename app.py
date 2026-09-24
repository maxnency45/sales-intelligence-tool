import streamlit as st
import pandas as pd
from serpapi import GoogleSearch
import time
import re
from datetime import datetime

# Cấu hình giao diện
st.set_page_config(page_title="Global Sales Intelligence Tool", layout="wide")

st.sidebar.title("⚙️ Cài đặt")
serpapi_key = st.sidebar.text_input("SerpApi API key", type="password", help="Nhập API Key lấy từ serpapi.com")

st.title("🌐 Global Sales Intelligence Tool - Tìm Nhà Phân Phối Toàn Cầu")

# Cấu hình từ khóa
col_input1, col_input2 = st.columns(2)
with col_input1:
    raw_product = st.text_input("Sản phẩm xuất khẩu (Chỉ nhập tên SP, ví dụ: food, coffee, furniture, seafood):", "food")
with col_input2:
    country = st.text_input("Thị trường / Quốc gia (Nhập tên nước hoặc 'Worldwide' / 'Global'):", "Worldwide").strip()

num_per_query = st.slider("Số lượng kết quả lấy cho mỗi câu lệnh", 5, 20, 10)

# Làm sạch từ khóa sản phẩm để tránh bị lặp từ
product = raw_product.strip()
for word in ["importers", "importer", "distributors", "distributor", "buyers", "buyer", "list of", "suppliers", "supplier"]:
    if word in product.lower():
        product = re.sub(rf'\b{word}\b', '', product, flags=re.IGNORECASE).strip()

# Định hình phạm vi địa lý
location_str = f'"{country}"' if country.lower() not in ["worldwide", "global", ""] else ""

# Các câu lệnh Google Dork quét Nhà phân phối B2B & Decision Maker TOÀN CẦU
queries_to_run = [
    f'"{product}" (distributor OR importer OR "wholesale buyer") {location_str}'.strip(),
    f'site:kompass.com "{product}" (distributor OR importer) {location_str}'.strip(),
    f'site:europages.com "{product}" (distributor OR importer) {location_str}'.strip(),
    f'site:thomasnet.com OR site:tradekey.com "{product}" {location_str}'.strip(),
    f'site:linkedin.com/in/ "{product}" ("purchasing manager" OR "import manager" OR "buyer" OR "CEO") {location_str}'.strip()
]

with st.expander("📋 Xem trước 5 câu lệnh Google Dork Toàn Cầu sẽ tự động chạy:"):
    for q in queries_to_run:
        st.code(q)

btn_start_search = st.button("🚀 BẮT ĐẦU TÌM NHÀ PHÂN PHỐI TOÀN CẦU", type="primary")

# Danh sách tên miền rác/không phải đối tượng mua hàng cần loại bỏ
BLOCKED_DOMAINS = [
    "wikipedia.org", "youtube.com", "reddit.com", "state.gov", "britannica.com", 
    "facebook.com", "instagram.com", "amazon.com", "tripadvisor.com", "europa.eu",
    "quora.com", "pinterest.com", "tiktok.com"
]

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', str(text))
    return match.group(0) if match else "N/A"

def extract_phone(text):
    match = re.search(r'(\+\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', str(text))
    return match.group(0) if match and len(match.group(0)) > 7 else "N/A"

if btn_start_search:
    if not serpapi_key:
        st.error("⚠️ Vui lòng nhập SerpApi API Key ở thanh Cài đặt bên trái!")
    elif not product:
        st.warning("⚠️ Vui lòng điền tên Sản phẩm!")
    else:
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, query in enumerate(queries_to_run):
            status_text.text(f"🔍 [Lệnh {index+1}/{len(queries_to_run)}] Đang quét thị trường toàn cầu: {query}")
            
            try:
                params = {
                    "q": query,
                    "engine": "google",
                    "num": num_per_query,
                    "api_key": serpapi_key
                }
                search = GoogleSearch(params)
                results = search.get_dict().get("organic_results", [])
                
                for item in results:
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")
                    title = item.get("title", "")
                    domain = link.split("/")[2] if "//" in link else link
                    
                    # Lọc bỏ tên miền rác
                    if any(blocked in domain.lower() for blocked in BLOCKED_DOMAINS):
                        continue
                    
                    all_results.append({
                        "Câu lệnh sử dụng": query,
                        "Tên Công ty / Tiêu đề": title,
                        "Website Domain": domain,
                        "Email (nếu tìm thấy)": extract_email(snippet + " " + title),
                        "SĐT (nếu tìm thấy)": extract_phone(snippet),
                        "Link chi tiết": link,
                        "Mô tả / Thông tin chi tiết": snippet
                    })
            except Exception as e:
                st.error(f"Lỗi khi chạy lệnh '{query}': {e}")
            
            progress_bar.progress((index + 1) / len(queries_to_run))
            time.sleep(0.5)

        status_text.text("✅ Đã hoàn tất tìm kiếm toàn cầu!")
        
        if all_results:
            df = pd.DataFrame(all_results)
            df_clean = df.drop_duplicates(subset=["Website Domain"])
            
            st.success(f"🎉 Tổng cộng tìm thấy **{len(df_clean)}** Nhà phân phối/Khách hàng tiềm năng toàn cầu!")
            st.dataframe(df_clean, use_container_width=True)
            
            csv_data = df_clean.to_csv(index=False, encoding='utf-8-sig')
            clean_filename = f"Global_Distributors_{product}_{country.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            
            st.download_button(
                label="📥 Tải danh sách Nhà phân phối về Excel (.CSV)",
                data=csv_data,
                file_name=clean_filename,
                mime="text/csv"
            )
        else:
            st.warning("Không tìm thấy kết quả. Thử kiểm tra lại từ khóa sản phẩm!")
