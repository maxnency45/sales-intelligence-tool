import streamlit as st
import pandas as pd
from serpapi import GoogleSearch
import time
from datetime import datetime

# Cấu hình giao diện
st.set_page_config(page_title="Sales Intelligence Tool", layout="wide")

# Thanh Sidebar
st.sidebar.title("⚙️ Cài đặt")
st.sidebar.caption("Nguồn Google")
serpapi_key = st.sidebar.text_input("SerpApi API key", type="password", help="Nhập API Key lấy từ serpapi.com")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Chế độ tự động:** Tự động chạy câu lệnh Google Dork ➔ Gom kết quả ➔ Lọc trùng website.")

# Tiêu đề & Nút bấm
st.title("🔎 Sales Intelligence Tool - Tìm Khách Hàng Xuất Khẩu")
col_top1, col_top2 = st.columns([1, 3])
with col_top1:
    btn_start_search = st.button("🚀 BẮT ĐẦU TÌM KHÁCH HÀNG", type="primary", use_container_width=True)
with col_top2:
    st.caption("Chạy tự động các câu lệnh Google, thu thập danh sách tên công ty + website theo ngành hàng.")

# Cấu hình tìm kiếm
st.subheader("Cấu hình từ khóa & Thị trường xuất khẩu")
col_input1, col_input2 = st.columns(2)
with col_input1:
    product = st.text_input("Sản phẩm xuất khẩu:", "food")
with col_input2:
    country = st.text_input("Thị trường / Quốc gia mục tiêu:", "Sweden")

num_per_query = st.slider("Số lượng kết quả lấy cho mỗi câu lệnh", 5, 20, 10)

queries_to_run = [
    f'"{product}" importers in {country}',
    f'"{product}" distributor wholesale {country}',
    f'site:yellowpages.com "{product}" {country}',
    f'"{product}" "purchasing manager" {country}'
]

with st.expander("📋 Xem trước 4 câu lệnh Google Dork sẽ tự động chạy:"):
    for q in queries_to_run:
        st.code(q)

if btn_start_search:
    if not serpapi_key:
        st.error("⚠️ Vui lòng nhập SerpApi API Key ở thanh Cài đặt bên trái!")
    elif not product or not country:
        st.warning("⚠️ Vui lòng điền đầy đủ tên Sản phẩm và Quốc gia!")
    else:
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, query in enumerate(queries_to_run):
            status_text.text(f"🔍 [Lệnh {index+1}/{len(queries_to_run)}] Đang quét: {query}")
            
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
                    domain = link.split("/")[2] if "//" in link else link
                    
                    all_results.append({
                        "Câu lệnh sử dụng": query,
                        "Tên Công ty / Tiêu đề": item.get("title"),
                        "Website Domain": domain,
                        "Link chi tiết": link,
                        "Mô tả": item.get("snippet")
                    })
            except Exception as e:
                st.error(f"Lỗi khi chạy câu lệnh '{query}': {e}")
            
            progress_bar.progress((index + 1) / len(queries_to_run))
            time.sleep(0.5)

        status_text.text("✅ Đã chạy xong tất cả các câu lệnh!")
        
        if all_results:
            df = pd.DataFrame(all_results)
            df_clean = df.drop_duplicates(subset=["Website Domain"])
            
            st.success(f"🎉 Tổng cộng tìm thấy **{len(df_clean)}** khách hàng không trùng lặp!")
            st.dataframe(df_clean, use_container_width=True)
            
            csv_data = df_clean.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải danh sách khách hàng về Excel (.CSV)",
                data=csv_data,
                file_name=f"Lead_{product}_{country}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
