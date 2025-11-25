import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
import json

# === Настройки ===
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
DEFAULT_PROPERTY = "sc-domain:cable.ru"  # Измени, если нужно

st.set_page_config(page_title="Google Indexing Checker", page_icon="🔍", layout="wide")
st.title("🔍 Проверка индексации URL в Google")

# === Получение учётных данных из Streamlit Secrets ===
try:
    credentials_info = st.secrets["google_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES
    )
    webmasters = build('searchconsole', 'v1', credentials=credentials)
except Exception as e:
    st.error("❌ Не удалось подключиться к Google Search Console API. Проверьте Secrets.")
    st.stop()

# === Функция проверки одного URL ===
def inspect_url(url, property_url):
    try:
        request_body = {"inspectionUrl": url, "siteUrl": property_url}
        response = webmasters.urlInspection().index().inspect(body=request_body).execute()
        inspection_result = response.get('inspectionResult', {})
        if not inspection_result:
            return {"indexed": False, "error": "Нет данных от API"}
        
        verdict = inspection_result.get('inspectionResult', {}).get('verdict')
        coverage = inspection_result.get('inspectionResult', {}).get('coverageState', 'UNKNOWN')
        last_crawl = inspection_result.get('inspectionResult', {}).get('lastCrawlTime', '—')
        google_canonical = inspection_result.get('inspectionResult', {}).get('googleCanonical', '—')
        
        return {
            "indexed": verdict == "PASS",
            "coverage_state": coverage,
            "last_crawl_date": last_crawl,
            "gsc_canonical": google_canonical,
            "error": ""
        }
    except Exception as e:
        return {"indexed": False, "error": str(e)}

# === Ввод URL ===
st.subheader("📥 Введите URL для проверки")

input_method = st.radio("Способ ввода:", ["Вручную", "Через Excel-файл"], horizontal=True)

urls = []
if input_method == "Вручную":
    urls_input = st.text_area("Введите URL по одному на строке", height=150)
    if urls_input.strip():
        urls = [u.strip() for u in urls_input.strip().split("\n") if u.strip().startswith("http")]
else:
    uploaded_file = st.file_uploader("Загрузите Excel-файл с колонкой 'URL'", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            if "URL" not in df.columns:
                st.error("Файл должен содержать колонку с названием 'URL'")
            else:
                urls = df["URL"].dropna().astype(str).tolist()
                urls = [u for u in urls if u.startswith("http")]
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")

# === Проверка ===
if urls:
    st.info(f"Найдено {len(urls)} URL для проверки.")
    
    property_url = st.text_input("URL собственности в Search Console", value=DEFAULT_PROPERTY)
    delay = st.slider("Задержка между запросами (сек)", 1, 5, 2)
    
    if st.button("🚀 Проверить индексацию в Google", type="primary"):
        if not property_url.startswith(("http", "sc-domain:")):
            st.error("URL собственности должен начинаться с 'http://' или 'sc-domain:'")
        else:
            progress = st.progress(0)
            status = st.empty()
            results = {}

            for i, url in enumerate(urls):
                status.text(f"Проверка {i+1}/{len(urls)}: {url}")
                res = inspect_url(url, property_url)
                results[url] = res
                time.sleep(delay)
                progress.progress((i + 1) / len(urls))

            # === Отображение результатов ===
            st.success("✅ Проверка завершена!")
            
            # Статистика
            indexed = sum(1 for r in results.values() if r["indexed"])
            total = len(results)
            st.metric("Проиндексировано", f"{indexed} из {total} ({indexed/total*100:.1f}%)")
            
            # Таблица
            data = []
            for url, res in results.items():
                if res["error"]:
                    status_text = f"❌ Ошибка: {res['error']}"
                else:
                    status_text = "✅ Да" if res["indexed"] else "❌ Нет"
                data.append({
                    "URL": url,
                    "Индексирован": status_text,
                    "Покрытие": res["coverage_state"],
                    "Последний краул": res["last_crawl_date"],
                    "Канонический URL": res["gsc_canonical"]
                })
            
            df_results = pd.DataFrame(data)
            st.dataframe(df_results, use_container_width=True)
            
            # Экспорт
            csv = df_results.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 Скачать результаты (CSV)", csv, "google_indexing_results.csv", "text/csv")

st.markdown("---")
st.caption("💡 Приложение использует официальный Google Search Console API. Все данные точны и актуальны.")