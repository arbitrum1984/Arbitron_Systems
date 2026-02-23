import qlib
from qlib.workflow import R
from qlib.backtest import backtest as qlib_backtest
import pandas as pd

def run_backtest(prediction_score, start_time, end_time):
    print(f"Запуск бэктеста с {start_time} по {end_time}...")
    
    # Критично: Приводим тикеры к нижнему регистру для соответствия бинарным данным.
    if isinstance(prediction_score.index, pd.MultiIndex):
        level_names = [n.lower() if n else '' for n in prediction_score.index.names]
        if 'instrument' in level_names:
            idx = level_names.index('instrument')
            prediction_score.index = prediction_score.index.set_levels(
                prediction_score.index.levels[idx].str.lower(),
                level=idx
            )
        elif len(prediction_score.index.levels) > 1:
            # Fallback: usually level 1 is instrument
            prediction_score.index = prediction_score.index.set_levels(
                prediction_score.index.levels[1].str.lower(),
                level=1
            )
    

    # Стратегия: Top X, продаем если выпадает из топа.
    strategy_config = {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy",
        "kwargs": {
            "topk": 5,
            "n_drop": 2,
            "signal": prediction_score,
            "hold_thresh": 5,
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

    # ВАЖНО: Указываем benchmark='sh000300' (мы его скачали в get_data.py)
    report_normal, positions = qlib_backtest(
        strategy=strategy_config,
        executor=executor_config,
        start_time=start_time,
        end_time=end_time,
        account=100_000_000,
        benchmark=None, 
        exchange_kwargs={
            "limit_threshold": 0.095,
            "deal_price": "open",
            "open_cost": 0.0015,
            "close_cost": 0.0015,
            "min_cost": 5,
        }
    )
    return report_normal, positions

def analyze_results(report):
    #R.save_objects(report=report)
    print("Отчет сохранен.")