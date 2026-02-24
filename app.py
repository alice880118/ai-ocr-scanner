import streamlit as st
import easyocr
import sqlite3
import numpy as np
from PIL import Image
import datetime
import re
from textblob import TextBlob
import pandas as pd

# --- iOS 視覺風格與資料庫初始化 ---
st.set_page_config(page_title="Scanner AI", layout="centered")

def init_db():
    conn = sqlite3.connect('ios_ocr_v2.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS docs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, content TEXT, tags TEXT, category TEXT, date TEXT)''')
    conn.commit()
    conn.close()

# --- AI 校正邏輯 ---
def ai_refined_text(text):
    fix_map = {r"\bwitlh\b": "with", r"\bonthe\b": "on the", r"\bdarkeyes\b": "dark eyes"} # 簡化示例
    for pattern, rep in fix_map.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return str(TextBlob(text).correct())

# --- 主程式介面 ---
def main():
    init_db()
    st.markdown("<style>.stButton>button {border-radius:12px;}</style>", unsafe_allow_html=True)
    st.title("📄 文字掃描器")
    
    tab_scan, tab_library = st.tabs(["[ 掃描儀 ]", "[ 文件庫 ]"])

    # --- 分頁 1: 掃描功能 ---
    with tab_scan:
        file = st.file_uploader("上傳圖片", type=['png', 'jpg', 'jpeg'], label_visibility="collapsed")
        if file:
            img = Image.open(file)
            st.image(img, use_container_width=True)
            if st.button("🚀 啟動 AI 辨識"):
                reader = easyocr.Reader(['en', 'ch_tra'])
                raw_text = " ".join(reader.readtext(np.array(img), detail=0))
                st.session_state['result'] = ai_refined_text(raw_text)

            if 'result' in st.session_state:
                final_output = st.text_area("校正結果", st.session_state['result'], height=150)
                col1, col2 = st.columns(2)
                with col1:
                    fname = st.text_input("文件名稱", value=final_output[:10])
                with col2:
                    cat = st.selectbox("分類", ["工作", "生活", "學習", "未分類"])
                
                tags = st.text_input("標籤 (用逗號隔開)")
                
                if st.button("📥 儲存文件"):
                    conn = sqlite3.connect('ios_ocr_v2.db')
                    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn.execute("INSERT INTO docs (name, content, tags, category, date) VALUES (?,?,?,?,?)",
                                 (fname, final_output, tags, cat, dt))
                    conn.commit()
                    conn.close()
                    st.success("已存入文件庫！")
                    del st.session_state['result']

    # --- 分頁 2: 文件庫 (核心更新區) ---
    with tab_library:
        st.subheader("🔍 我的文件")
        search_q = st.text_input("搜尋關鍵字...", placeholder="輸入名稱、標籤或分類")
        
        conn = sqlite3.connect('ios_ocr_v2.db')
        df = pd.read_sql_query("SELECT * FROM docs ORDER BY id DESC", conn)
        
        if search_q:
            df = df[df['name'].str.contains(search_q) | df['tags'].str.contains(search_q) | df['category'].str.contains(search_q)]

        if not df.empty:
            for index, row in df.iterrows():
                # iOS 卡片式清單
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**{row['name']}**")
                        st.caption(f"📅 {row['date']}  |  🏷️ {row['category']}  |  # {row['tags']}")
                    with col_btn:
                        # 使用每個 row 的 ID 作為唯一的 key
                        if st.button("詳情", key=f"edit_{row['id']}"):
                            st.session_state['editing_id'] = row['id']
                st.divider()
        else:
            st.write("目前尚無文件紀錄。")

        # --- 彈出式編輯視窗 (Detail Editor) ---
        if 'editing_id' in st.session_state:
            st.markdown("---")
            st.subheader("📝 編輯文件詳情")
            edit_id = st.session_state['editing_id']
            # 從資料庫抓取該筆資料
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM docs WHERE id=?", (edit_id,))
            target = cursor.fetchone()
            
            # 編輯欄位
            new_name = st.text_input("名稱", value=target[1])
            new_content = st.text_area("內容", value=target[2], height=200)
            new_cat = st.selectbox("分類", ["工作", "生活", "學習", "未分類"], index=0)
            new_tags = st.text_input("標籤", value=target[3])

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("✅ 更新儲存"):
                    conn.execute("UPDATE docs SET name=?, content=?, tags=?, category=? WHERE id=?",
                                 (new_name, new_content, new_tags, new_cat, edit_id))
                    conn.commit()
                    st.success("更新成功！")
                    del st.session_state['editing_id']
                    st.rerun()
            with col_cancel:
                if st.button("❌ 取消編輯"):
                    del st.session_state['editing_id']
                    st.rerun()
        conn.close()

if __name__ == "__main__":
    main()