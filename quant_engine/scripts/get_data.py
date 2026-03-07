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

# US Tech & Global + China Benchmark
TICKERS = [
    # Top US Stocks for terminal predictions
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "JPM", "V", 
    "JNJ", "WMT", "PG", "MA", "HD", "CVX", "MRK", "KO", "PEP", "AVGO", "COST", "MCD",
    # China
    "600519.SS", "601318.SS", "000001.SZ", "000300.SS" # Бенчмарк
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
            if '.' in t:
                code = t.split('.')[0]
                exch = t.split('.')[1]
                if code == "000300": # Особая обработка для индекса
                    qlib_code = "sh000300"
                else:
                    prefix = "sh" if exch == "SS" else "sz"
                    qlib_code = f"{prefix}{code}"
            else:
                # Американские тикеры без суффикса (aapl, msft)
                qlib_code = t.lower()

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