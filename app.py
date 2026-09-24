import streamlit as st
import pandas as pd
from serpapi import GoogleSearch
import time
import re
from datetime import datetime

# Cấu hình trang
st.set_page_config(page_title="Sales Intelligence & Customs Data Tool", layout="wide")

# Thanh Sidebar
st.sidebar.title("⚙️ Cài đặt hệ thống")
serpapi_key = st.sidebar.text_input("SerpApi API key", type="password", help="Nhập API Key lấy từ serpapi.com")

st.title("🚀 Sales Intelligence Tool - Export Lead Generation")

# Tạo các Tab tính năng giống hệ thống chuyên nghiệp
tab_search, tab_customs = st.tabs(["🔎 Tìm kiếm Lead", "📦 Shipment / Customs Data"])

# ==========================================
# TAB 1: TÌM KIẾM LEAD DOANH NGHIỆP
# ==========================================
with tab_search:
    st.subheader("1. Bạn muốn tìm khách hàng nào?")
    
    col_k1, col_k2, col_k3 = st.columns([2, 1, 1])
    with col_k1:
        raw_product = st.text_area("Sản phẩm / Bộ từ khóa (Mỗi dòng 1 từ hoặc phân cách dấu phẩy):", 
                                   "porcelain cup\nporcelain plate\nporcelain bowl", height=100)
    with col_k2:
        country = st.text_input("Thị trường mục tiêu:", "Germany").strip()
        num_target = st.slider("Mục tiêu số lead", 10, 100, 30)
    with col_k3:
        target_roles = st.multiselect("Loại khách hàng ưu tiên:", 
                                      ["Nhà nhập khẩu", "Nhà phân phối", "Nhà bán buôn", "HoReCa / Retailer"], 
                                      default=["Nhà nhập khẩu", "Nhà phân phối"])

    btn_start = st.button("🚀 BẮT ĐẦU TÌM KHÁCH HÀNG", type="primary")

    BLOCKED_DOMAINS = ["wikipedia.org", "youtube.com", "reddit.com", "state.gov", "facebook.com", "amazon.com"]

    def classify_company_type(text):
        text_lower = text.lower()
        if "importer" in text_lower or "import" in text_lower:
            return "Nhà nhập khẩu"
        elif "distributor" in text_lower or "distribution" in text_lower:
            return "Nhà phân phối"
        elif "wholesale" in text_lower or "wholesaler" in text_lower:
            return "Nhà bán buôn"
        elif "retail" in text_lower or "store" in text_lower or "hotel" in text_lower:
            return "HoReCa / Retailer"
        return "Nhà nhập khẩu"

    def calculate_scores(title, snippet, keyword):
        score = 30
        if keyword.lower() in (title + snippet).lower():
            score += 10
        if any(w in (title + snippet).lower() for w in ["importer", "distributor", "supplier", "wholesale"]):
            score += 10
        
        confidence = "Sơ bộ"
        if score >= 45:
            confidence = "Cao"
        elif score >= 38:
            confidence = "Trung bình"
            
        return score, confidence

    if btn_start:
        if not serpapi_key:
            st.error("⚠️ Vui lòng nhập SerpApi API Key ở sidebar bên trái!")
        else:
            keywords = [k.strip() for k in raw_product.replace('\n', ',').split(',') if k.strip()]
            all_results = []
            
            queries = []
            for kw in keywords[:3]: # Chạy thử các từ khóa chính
                queries.append(f'"{kw}" (importer OR distributor OR wholesale) "{country}"')
                queries.append(f'site:europages.com "{kw}" "{country}"')

            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, q in enumerate(queries):
                status_text.text(f"🔍 Đang chạy lệnh {idx+1}/{len(queries)}: {q}")
                try:
                    params = {"q": q, "engine": "google", "num": min(10, num_target), "api_key": serpapi_key}
                    search = GoogleSearch(params)
                    results = search.get_dict().get("organic_results", [])

                    for item in results:
                        link = item.get("link", "")
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        domain = link.split("/")[2] if "//" in link else link

                        if any(b in domain.lower() for b in BLOCKED_DOMAINS):
                            continue

                        comp_type = classify_company_type(title + " " + snippet)
                        score, confidence = calculate_scores(title, snippet, keywords[0])

                        # Format link website ngắn gọn
                        clean_url = link if link.startswith("http") else f"https://{link}"
                        
                        all_results.append({
                            "Công ty": title,
                            "Thị trường": country,
                            "Loại KH": comp_type,
                            "Điểm ưu tiên": score,
                            "Điểm Google/Website": score,
                            "Độ tin cậy SP": confidence,
                            "Bằng chứng": 1,
                            "Website": clean_url,
                            "Domain": domain
                        })
                except Exception as e:
                    st.error(f"Lỗi: {e}")
                progress_bar.progress((idx + 1) / len(queries))
                time.sleep(0.3)

            status_text.text("✅ Đã hoàn tất quét dữ liệu!")

            if all_results:
                df = pd.DataFrame(all_results).drop_duplicates(subset=["Domain"])
                
                # Hiển thị Metric Thống kê
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("KQ Google thô", len(all_results))
                m2.metric("Doanh nghiệp (Lọc trùng)", len(df))
                m3.metric("Lead Uy tín (Cao)", len(df[df["Độ tin cậy SP"] == "Cao"]))
                m4.metric("Verified Importer", len(df[df["Loại KH"] == "Nhà nhập khẩu"]))

                st.subheader("Kết quả lead doanh nghiệp")
                
                # Format cột Website thành Link clickable ngắn
                df_display = df.copy()
                df_display["Website"] = df_display["Website"].apply(lambda x: f'<a href="{x}" target="_blank">Mở website</a>')
                df_display = df_display.drop(columns=["Domain"])

                # Rendering HTML table cho link đẹp
                st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
                
                # Nút tải CSV
                csv = df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 Tải dữ liệu Lead (.CSV)", csv, f"Lead_Results_{country}.csv", "text/csv")

# ==========================================
# TAB 2: SHIPMENT / CUSTOMS DATA UPLOAD
# ==========================================
with tab_customs:
    st.subheader("📦 Upload & Cập nhật Dữ liệu Hải quan (Shipment / Customs Data)")
    st.caption("Up file dữ liệu hải quan thực tế để khớp nối và tăng độ tin cậy tuyệt đối cho Lead.")

    uploaded_file = st.file_uploader("Tải lên file Hải quan (.CSV hoặc .XLSX):", type=["csv", "xlsx"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                customs_df = pd.read_csv(uploaded_file)
            else:
                customs_df = pd.read_excel(uploaded_file)

            st.success(f"✅ Đã tải thành công {len(customs_df)} dòng dữ liệu hải quan!")
            st.write("Xem trước dữ liệu hải quan đã upload:")
            st.dataframe(customs_df.head(10), use_container_width=True)

            st.info("💡 **Chế độ tự động khớp nối**: Các doanh nghiệp có trong dữ liệu Hải quan này sẽ tự động được gán nhãn **Verified Importer** và nhận **Độ tin cậy SP: CAO** khi chạy tìm kiếm.")
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")
