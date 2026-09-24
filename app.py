import streamlit as st
import pandas as pd
from serpapi import GoogleSearch
import time
import re
from datetime import datetime

# Cấu hình giao diện
st.set_page_config(page_title="Global B2B Sales Intelligence Tool", layout="wide")

st.sidebar.title("⚙️ Cài đặt")
serpapi_key = st.sidebar.text_input("SerpApi API key", type="password", help="Nhập API Key lấy từ serpapi.com")

st.title("🌐 Global B2B Sales Intelligence Tool")
st.caption("Tìm kiếm Importers, Distributors, Wholesalers, Retailers & Buyers trên toàn thế giới")

# Cấu hình từ khóa
col_input1, col_input2 = st.columns(2)
with col_input1:
    raw_product = st.text_input("Sản phẩm xuất khẩu (Chỉ nhập tên SP, ví dụ: food, coffee, furniture, seafood):", "food")
with col_input2:
    country = st.text_input("Thị trường / Quốc gia (Nhập tên nước hoặc 'Worldwide' / 'Global'):", "Worldwide").strip()

num_per_query = st.slider("Số lượng kết quả lấy cho mỗi câu lệnh", 5, 20, 10)

# 1. Tự động làm sạch từ khóa sản phẩm nếu người dùng lỡ nhập kèm tên vai trò
product = raw_product.strip()
role_words = [
    "importers", "importer", "distributors", "distributor", "wholesalers", "wholesaler", 
    "retailers", "retailer", "buyers", "buyer", "purchasers", "purchaser", "list of", "suppliers", "supplier"
]
for word in role_words:
    product = re.sub(rf'\b{word}\b', '', product, flags=re.IGNORECASE).strip()

# 2. Định hình phạm vi địa lý
location_str = f'"{country}"' if country.lower() not in ["worldwide", "global", ""] else ""

# 3. Chuỗi vai trò B2B đầy đủ
b2b_roles = '(importer OR distributor OR wholesaler OR retailer OR buyer OR purchaser)'
linkedin_titles = '("purchasing manager" OR "procurement manager" OR "import manager" OR "buyer" OR "head of import" OR "category manager" OR "CEO")'

# 4. Các câu lệnh Google Dork quét B2B TOÀN CẦU
queries_to_run = [
    f'"{product}" {b2b_roles} {location_str}'.strip(),
    f'site:kompass.com "{product}" {b2b_roles} {location_str}'.strip(),
    f'site:europages.com "{product}" {b2b_roles} {location_str}'.strip(),
    f'site:thomasnet.com OR site:tradekey.com "{product}" {b2b_roles} {location_str}'.strip(),
    f'site:linkedin.com/in/ "{product}" {linkedin_titles} {location_str}'.strip()
]

with st.expander("📋 Xem trước 5 câu lệnh Google Dork Toàn Cầu sẽ tự động chạy:"):
    for q in queries_to_run:
        st.code(q)

btn_start_search = st.button("🚀 BẮT ĐẦU TÌM KHÁCH HÀNG TOÀN CẦU", type="primary")

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
            status_text.text(f"🔍 [Lệnh {index+1}/{len(queries_to_run)}] Đang quét đối tác B2B: {query}")
            
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
            
            st.success(f"🎉 Tổng cộng tìm thấy **{len(df_clean)}** Khách hàng / Đối tác B2B tiềm năng toàn cầu!")
            st.dataframe(df_clean, use_container_width=True)
            
            csv_data = df_clean.to_csv(index=False, encoding='utf-8-sig')
            clean_filename = f"Global_B2B_Buyers_{product}_{country.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            
            st.download_button(
                label="📥 Tải danh sách Khách hàng B2B về Excel (.CSV)",
                data=csv_data,
                file_name=clean_filename,
                mime="text/csv"
            )
        else:
            st.warning("Không tìm thấy kết quả. Thử kiểm tra lại từ khóa sản phẩm!")
