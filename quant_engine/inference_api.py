from typing import Optional
import sys
import os
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import qlib
from qlib.data import D

# Lazy initialization helper
_qlib_initialized = False
loaded_model = None

MODEL_PATH = "mlruns/models/latest_model.joblib"

app = FastAPI(title="Quant Engine API")

class PredictionRequest(BaseModel):
    ticker: str

def get_qlib():
    global _qlib_initialized
    if not _qlib_initialized:
        print("Initializing Qlib...")
        qlib.init(provider_uri='/data/qlib_data/my_data')
        _qlib_initialized = True
    return qlib

_loaded_mtime = 0.0

def get_model():
    global loaded_model, _loaded_mtime
    
    if os.path.exists(MODEL_PATH):
        current_mtime = os.path.getmtime(MODEL_PATH)
        if loaded_model is None or current_mtime > _loaded_mtime:
            print(f"Loading/Updating model from {MODEL_PATH} (mtime: {current_mtime})...")
            loaded_model = joblib.load(MODEL_PATH)
            _loaded_mtime = current_mtime
            print("Model loaded successfully.")
    else:
        if loaded_model is None:
            print("WARNING: No trained model found at", MODEL_PATH)

    return loaded_model

@app.on_event("startup")
async def startup_event():
    # Only log readiness, don't block on heavy loads
    print("API server is starting up...")

@app.post("/predict")
def predict(req: PredictionRequest):
    model = get_model()
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded or not found")
    
    get_qlib()
    
    # 1. Подготовка фичей через Qlib Data Handler
    try:
        from qlib.utils import init_instance_by_config
        import yaml
        
        # Загружаем конфиг для получения описания фичей
        CONFIG_PATH = "configs/workflow_config.yaml"
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        
        # Создаем обработчик данных (на лету для одного тикера)
        dataset_config = config["dataset_config"]
        # Ограничиваем инструменты только одним тикером
        dataset_config["kwargs"]["handler"]["kwargs"]["instruments"] = [req.ticker]
        
        dataset = init_instance_by_config(dataset_config)
        # Получаем последние доступные фичи
        # В Qlib сегмент 'test' или 'valid' обычно содержит нужные данные
        # Здесь мы берем последние доступные данные через prepare
        pred_data = dataset.prepare("test", col_set="feature")
        
        if pred_data.empty:
            # Если в 'test' нет данных для этого тикера, пробуем за весь период
            pred_data = dataset.prepare(slice(None, None), col_set="feature")
            
        last_row = pred_data.iloc[-1:] 
        
        # 2. Прогноз
        # Используем подлежащую модель напрямую, так как обертка Qlib требует Dataset
        if hasattr(loaded_model, 'model'):
            score = loaded_model.model.predict(last_row)
        else:
            score = loaded_model.predict(last_row)

        # Если score это Series/DataFrame/ndarray, берем значение
        if hasattr(score, 'iloc'):
            signal = float(score.iloc[0])
        elif hasattr(score, 'tolist'):
            signal = float(score[0])
        else:
            signal = float(score)
            
        return {"ticker": req.ticker, "signal": signal, "confidence": "high"}
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/train/trigger")
def trigger_training():
    # Запускаем задачу в Celery
    from tasks import run_full_pipeline
    run_full_pipeline.delay()
    return {"status": "Training started in background"}

@app.get("/backtest/list")
def get_backtests():
    from scripts.backtest_utils import list_experiments
    return list_experiments()

@app.get("/backtest/results/{run_id}")
def get_backtest_results(run_id: str):
    from scripts.backtest_utils import get_backtest_plotly_data
    return get_backtest_plotly_data(run_id)

class BacktestRequest(BaseModel):
    start_time: str
    end_time: str

@app.post("/backtest/run")
def run_backtest_api(req: BacktestRequest):
    from tasks import run_backtest_task
    run_backtest_task.delay(req.start_time, req.end_time)
    return {"status": "Backtest started", "start_time": req.start_time, "end_time": req.end_time}