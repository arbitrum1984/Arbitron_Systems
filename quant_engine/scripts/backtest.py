import qlib
from qlib.workflow import R
from qlib.backtest import backtest as qlib_backtest
import pandas as pd

def run_backtest(prediction_score, start_time, end_time):
    print(f"Запуск бэктеста с {start_time} по {end_time}...")
    
    # 1. Устранение Look-Ahead Bias (Сдвиг сигнала)
    # Ручной сдвиг через Pandas (shift) ломает внутренний календарь Qlib и приводит к 0 сделок.
    # Вместо этого мы будем использовать нативные настройки Qlib Executor/Strategy.
    # Prediction Score передается "как есть" с оригинальными датами.
    
    # 2. Оставляем тикеры в оригинальном регистре.
    # Ранее мы принудительно делали .lower(), что ломало US тикеры (aapl вместо AAPL),
    # так как они скачивались из yfinance в верхнем регистре.

    # Стратегия: Top X, продаем если выпадает из топа.
    strategy_config = {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy",
        "kwargs": {
            "topk": 10,
            "n_drop": 5,
            "signal": prediction_score,
            "hold_thresh": 10,
        }
    }

    executor_config = {
        "class": "SimulatorExecutor",
        "module_path": "qlib.backtest.executor",
        "kwargs": {
            "time_per_step": "day",
            "generate_account_profile": True,
            "verbose": True, 
        },
    }

    # ВАЖНО: Указываем benchmark='sh000300' 
    report_normal, positions = qlib_backtest(
        strategy=strategy_config,
        executor=executor_config,
        start_time=start_time,
        end_time=end_time,
        account=100_000_000,
        benchmark=None, 
        exchange_kwargs={
            "limit_threshold": 0.15,
            "deal_price": "close",
            "open_cost": 0.0015,
            "close_cost": 0.0015,
            "min_cost": 5,
        }
    )
    return report_normal, positions

def analyze_results(report):
    #R.save_objects(report=report)
    print("Отчет сохранен.")