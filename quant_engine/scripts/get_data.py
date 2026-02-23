import os
import sys
import shutil
import requests
import subprocess
import pandas as pd
import yfinance as yf

# === НАСТРОЙКИ ===
DATA_DIR = "/data/qlib_data/source/my_data"
QLIB_DIR = "/data/qlib_data/my_data"
SCRIPT_PATH = "/app/scripts/dump_bin.py"

# Топ-30 акций Китая + ИНДЕКС (обязательно!)
TICKERS = [
    "600519.SS", "601318.SS", "600036.SS", "601012.SS", "300750.SZ", "002594.SZ",
    "000858.SZ", "000001.SZ", "601888.SS", "600900.SS", "600030.SS", "600276.SS",
    "601668.SS", "000333.SZ", "600887.SS", "601398.SS", "600000.SS", "601328.SS",
    "601166.SS", "000651.SZ", "601988.SS", "601288.SS", "000725.SZ", "601319.SS",
    "601818.SS", "600104.SS", "600585.SS", "000002.SZ", "601601.SS", "601628.SS",
    "601169.SS", "600048.SS", "601857.SS", "601088.SS", "600016.SS", "002304.SZ",
    "600309.SS", "000157.SZ", "002415.SZ", "000063.SZ", "603259.SS", "601211.SS",
    "601688.SS", "000069.SZ", "600690.SS", "601939.SS", "600019.SS", "601111.SS",
    "000300.SS" # Бенчмарк
]

def prepare_dirs():
    if os.path.exists(DATA_DIR): shutil.rmtree(DATA_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(QLIB_DIR, exist_ok=True)

def download_dump_script():
    if not os.path.exists(SCRIPT_PATH):
        print("Скачиваем dump_bin.py...")
        url = "https://raw.githubusercontent.com/microsoft/qlib/main/scripts/dump_bin.py"
        r = requests.get(url)
        with open(SCRIPT_PATH, 'w', encoding='utf-8') as f:
            f.write(r.text)

def download_data():
    print(f"Скачиваем {len(TICKERS)} тикеров...")
    for t in TICKERS:
        try:
            # Скачиваем данные
            df = yf.download(t, start="2010-01-01", end="2026-12-31", auto_adjust=True, progress=False)
            if df.empty: continue
            
            # Убираем мультииндекс и форматируем
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'date': 'date', 'time': 'date'}) # на всякий случай
            df = df.reset_index()
            
            # Переименование колонок даты, если они в индексе
            if 'Date' in df.columns: df = df.rename(columns={'Date': 'date'})
            if 'date' not in df.columns: df = df.rename(columns={df.columns[0]: 'date'})

            # Обязательные поля для Qlib
            df['factor'] = 1.0
            needed = ['date', 'open', 'high', 'low', 'close', 'volume', 'factor']
            if not all(col in df.columns for col in needed): continue

            # ИМЕНОВАНИЕ ФАЙЛОВ (КРИТИЧНО!)
            # 000300.SS -> sh000300 (Бенчмарк)
            # 600519.SS -> sh600519
            # 000001.SZ -> sz000001
            code = t.split('.')[0]
            exch = t.split('.')[1]
            if code == "000300": # Особая обработка для индекса
                qlib_code = "sh000300"
            else:
                prefix = "sh" if exch == "SS" else "sz"
                qlib_code = f"{prefix}{code}"

            df[needed].to_csv(f"{DATA_DIR}/{qlib_code}.csv", index=False)
            print(f"OK: {qlib_code}")
        except Exception as e:
            print(f"ERR {t}: {e}")

def convert_to_bin():
    print("\nКонвертация в Qlib BIN...")
    cmd = [
        sys.executable, SCRIPT_PATH, "dump_all",
        "--data_path", DATA_DIR,
        "--qlib_dir", QLIB_DIR,
        "--include_fields", "open,close,high,low,volume,factor",
        "--symbol_field_name", "None", 
        "--date_field_name", "date"
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    prepare_dirs()
    download_dump_script()
    download_data()
    convert_to_bin()
    print("\n✅ Данные готовы! Теперь у вас есть и акции, и РЕАЛЬНЫЙ бенчмарк.")