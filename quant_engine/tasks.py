import os
import gc
import pandas as pd
from celery import Celery
from scripts.train import train_model
from scripts.get_data import download_data, convert_to_bin
import joblib

# Настройка Celery (брокер Redis)
celery_app = Celery('quant_tasks', broker='redis://redis:6379/0')

def init_qlib():
    # Lazy init inside tasks
    if not getattr(init_qlib, "_done", False):
        import qlib
        print("Initializing Qlib in Celery worker...")
        qlib.init(provider_uri='/data/qlib_data/my_data', dataset_cache=None, expression_cache=None)
        init_qlib._done = True

@celery_app.task
def run_full_pipeline():
    """
    1. Качает данные (Yahoo + FRED + EDGAR)
    2. Конвертирует в BIN
    3. Обучает модель
    4. Сохраняет .pkl
    """
    print("--- STARTING DATA INGESTION ---")
    init_qlib()

    # 1. Твой скрипт get_data.py
    download_data()
    convert_to_bin()

    # 2. Здесь можно добавить вызовы для FRED / EDGAR
    # sync_fred_data()
    # sync_edgar_filings()

    print("--- STARTING TRAINING ---")

    # 3. Обучение (используем твой train.py, но модифицируем его return)
    model, score = train_model("configs/workflow_config.yaml", "daily_exp")

    # 4. Сохранение для Online Inference
    save_path = "mlruns/models/latest_model.joblib"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    joblib.dump(model, save_path)

    return "Pipeline Finished. Model Updated."

@celery_app.task
def run_backtest_task(start_time: str, end_time: str):
    """
    Runs a backtest for a given period.
    """
    init_qlib()
    print(f"DEBUG: Starting run_backtest_task with start={start_time}, end={end_time}")
    from scripts.backtest import run_backtest
    from qlib.workflow import R
    
    # We need a prediction score to run backtest. 
    # Usually we use the one from the latest experiment/recorder.
    # For now, let's assume we use the global 'daily_exp' latest recorder pred_score.
    try:
        # 1. Find the latest 'daily_exp' experiment ID manually by scanning mlruns
        # This is the most robust way to handle duplicate experiment names
        import yaml
        daily_exps_list = []
        mlruns_path = 'mlruns'
        if os.path.exists(mlruns_path):
            for eid in os.listdir(mlruns_path):
                meta_path = os.path.join(mlruns_path, eid, 'meta.yaml')
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as f:
                            meta = yaml.safe_load(f)
                            if meta and meta.get("name") == "daily_exp":
                                daily_exps_list.append({
                                    "id": eid,
                                    "creation_time": meta.get("creation_time", 0)
                                })
                    except Exception: continue
        
        if not daily_exps_list:
             return "No experiment named 'daily_exp' found in mlruns."
             
        # Sort by creation_time descending
        latest_exp_info = sorted(daily_exps_list, key=lambda x: x["creation_time"], reverse=True)[0]
        latest_exp_id = str(latest_exp_info["id"])
        
        print(f"DEBUG: Selected latest experiment ID: {latest_exp_id}")

        # 2. List recorders from the latest experiment ID
        from qlib.workflow import R
        recorders = R.list_recorders(experiment_id=latest_exp_id)
        print(f"DEBUG: Found {len(recorders)} recorders for experiment {latest_exp_id}")
        if not recorders:
            return f"No recorders found in daily_exp (ID: {latest_exp_id}) to run backtest."

        # Get the latest recorder by start_time
        # Recorders dict is {rid: RecorderObject}
        # We need to sort them to find the latest
        sorted_recorders = sorted(
            recorders.items(), 
            key=lambda x: x[1].info.get("start_time") or "", 
            reverse=True
        )
        if not sorted_recorders:
            return "No valid recorders found in daily_exp."
            
        latest_rid, recorder = sorted_recorders[0]
        pred_score = recorder.load_object("pred_score")
        
        # Try to load label as well so we can calculate IC later
        label = None
        try:
            label = recorder.load_object("label")
        except Exception:
            print("Warning: Could not load label from source recorder.")
        
        with R.start(experiment_name="custom_backtests", recorder_name=f"backtest_{start_time}_{end_time}"):
            report, positions = run_backtest(pred_score, start_time, end_time)
            
            # Check if report is empty (handles both DataFrame and dict)
            is_empty = False
            if report is None:
                is_empty = True
            elif isinstance(report, pd.DataFrame):
                is_empty = report.empty
            elif isinstance(report, dict):
                is_empty = not report
                
            if is_empty:
                print(f"WARNING: Backtest from {start_time} to {end_time} resulted in an EMPTY report (no trades).")
            if label is not None:
                R.save_objects(report=report, positions=positions, pred_score=pred_score, label=label)
            else:
                R.save_objects(report=report, positions=positions, pred_score=pred_score)
            
        # Manually trigger garbage collection to prevent Pandas memory leaks in Docker worker
        del report, positions, pred_score, label
        gc.collect()

        return f"Backtest from {start_time} to {end_time} finished."
    except Exception as e:
        import traceback
        return f"Backtest failed: {str(e)}\n{traceback.format_exc()}"