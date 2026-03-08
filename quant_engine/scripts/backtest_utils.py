import pandas as pd
import numpy as np
from qlib.workflow import R
import os

def _get_all_experiments_manual():
    """
    Helper to manually scan mlruns directory and return a list of {id, name}
    """
    import yaml
    experiments = []
    mlruns_path = 'mlruns'
    if os.path.exists(mlruns_path):
        for eid in os.listdir(mlruns_path):
            meta_path = os.path.join(mlruns_path, eid, 'meta.yaml')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = yaml.safe_load(f)
                        if meta:
                            experiments.append({
                                "id": eid,
                                "name": meta.get("name")
                            })
                except Exception: continue
    return experiments

# Глобальная переменная для отслеживания инициализации Qlib
_QLIB_INITIALIZED = False

def list_experiments():
    """
    Lists all available experiments and their runs using manual filesystem scan.
    Bypasses slow MLflow API to avoid timeouts.
    """
    import qlib
    import yaml
    global _QLIB_INITIALIZED
    
    # Регулярная инициализация, если вдруг не вызван
    if not _QLIB_INITIALIZED:
        try:
            qlib.init(provider_uri='/data/qlib_data/my_data')
            _QLIB_INITIALIZED = True
        except Exception as e:
            print(f"Qlib initial init error: {e}")
    
    experiments = _get_all_experiments_manual()
    
    results = []
    mlruns_path = 'mlruns'
    
    for exp in experiments:
        try:
            exp_id = str(exp["id"])
            exp_name = exp["name"]
            exp_dir = os.path.join(mlruns_path, exp_id)
            
            if not os.path.exists(exp_dir): continue
            
            # Сканируем директории забегов вручную
            for rid in os.listdir(exp_dir):
                run_meta_path = os.path.join(exp_dir, rid, 'meta.yaml')
                if os.path.exists(run_meta_path):
                    try:
                        with open(run_meta_path, 'r') as f:
                            run_meta = yaml.safe_load(f)
                            if run_meta:
                                results.append({
                                    "experiment_id": exp_id,
                                    "experiment_name": exp_name,
                                    "run_id": rid,
                                    "run_name": run_meta.get("run_name") or rid,
                                    "start_time": run_meta.get("start_time"),
                                    "status": run_meta.get("status")
                                })
                    except Exception: continue
            
        except Exception as e:
            print(f"Error listing runs for {exp.get('name')}: {e}")
    
    # Sort by start_time descending
    results.sort(key=lambda x: x.get("start_time") or 0, reverse=True)
    return results

def _extract_ic_data(recorder, pred):
    """Tiered IC extraction."""
    try:
        label = recorder.load_object("label")
        df = pd.DataFrame()
        if pred is not None:
            if isinstance(pred, pd.Series): df['score'] = pred
            else: df['score'] = pred.iloc[:, 0]
        if label is not None:
            if isinstance(label, pd.Series): df['label'] = label
            else: df['label'] = label.iloc[:, 0]
        
        df = df.dropna()
        if df.empty: return {}

        ic = df.groupby('datetime').apply(lambda x: x['score'].corr(x['label']))
        dates = ic.index.strftime('%Y-%m-%d').tolist() if hasattr(ic.index, 'strftime') else [str(x)[:10] for x in ic.index]
        ic_mean = float(ic.mean()) if not isinstance(ic.mean(), (pd.Series, np.ndarray)) else float(ic.mean()[0])

        return {"dates": dates, "values": ic.values.tolist(), "mean": ic_mean}
    except Exception as e:
        print(f"IC extraction failed: {e}")
        return {"dates": [], "values": [], "mean": 0.0}

def _extract_performance_from_report(recorder):
    """Tier 1: Extract from 'report' artifact."""
    try:
        report = recorder.load_object("report")
        if isinstance(report, (list, tuple)) and len(report) > 0: report = report[0]
        if isinstance(report, dict):
            if "return" in report:
                ret_data = report["return"]
                if isinstance(ret_data, pd.Series):
                    report = ret_data.to_frame(name="return")
                else:
                    report = pd.DataFrame(ret_data)
            else:
                for v in report.values():
                    if isinstance(v, pd.DataFrame): report = v; break
        
        if not isinstance(report, pd.DataFrame) or report.empty: return None

        report.columns = [str(c).lower() for c in report.columns]
        ret_col = next((c for c in ['return', 'total_return', 'strat_ret'] if c in report.columns), report.columns[0])
        
        strategy_ret = report[ret_col]
        strategy_cum = (strategy_ret + 1).cumprod()
        bench_cum = (report['bench'] + 1).cumprod() if 'bench' in report.columns else None
        dates = report.index.strftime('%Y-%m-%d').tolist() if hasattr(report.index, 'strftime') else [str(x)[:10] for x in report.index]

        return {
            "dates": dates,
            "strategy_cum": strategy_cum.values.tolist(),
            "benchmark_cum": bench_cum.values.tolist() if bench_cum is not None else None,
            "sharpe": float((strategy_ret.mean() / strategy_ret.std()) * (252**0.5)) if strategy_ret.std() != 0 else 0,
            "max_drawdown": float(((strategy_cum - strategy_cum.cummax()) / strategy_cum.cummax()).min()),
            "source": "report"
        }
    except Exception: return None

def _extract_performance_from_positions(recorder):
    """Tier 2: Extract from 'positions' artifact."""
    try:
        positions = recorder.load_object("positions")
        pos_df = pd.DataFrame()
        if isinstance(positions, pd.DataFrame): pos_df = positions
        elif isinstance(positions, (list, tuple)) and len(positions) > 0: pos_df = positions[0]
        elif isinstance(positions, dict):
            for v in positions.values():
                if isinstance(v, pd.DataFrame): pos_df = v; break
            if pos_df.empty: # Legacy Position objects
                history = []
                for dt, pos in positions.items():
                    val = getattr(pos, 'calculate_value', lambda: 0)() if not isinstance(pos, (int, float)) else pos
                    history.append({'datetime': dt, 'value': val})
                pos_df = pd.DataFrame(history).set_index('datetime').sort_index()

        if pos_df.empty: return None

        target_col = next((c for c in ['value', 'total_value', 'total'] if c in pos_df.columns), pos_df.columns[-1])
        base_val = pos_df[target_col].replace(0, np.nan).dropna().iloc[0]
        strategy_cum = (pos_df[target_col] / base_val).fillna(1.0)
        dates = pos_df.index.strftime('%Y-%m-%d').tolist() if hasattr(pos_df.index, 'strftime') else [str(x)[:10] for x in pos_df.index]

        return {
            "dates": dates,
            "strategy_cum": strategy_cum.values.tolist(),
            "benchmark_cum": None,
            "sharpe": 0,
            "max_drawdown": float(((strategy_cum - strategy_cum.cummax()) / strategy_cum.cummax()).min()),
            "source": "positions"
        }
    except Exception: return None

def _reconstruct_performance_from_signals(recorder, pred):
    """Tier 3: Reconstruct ESTIMATED performance from signals/labels if artifacts are missing."""
    try:
        label = recorder.load_object("label")
        df = pd.DataFrame()
        if pred is not None: df['score'] = pred if isinstance(pred, pd.Series) else pred.iloc[:, 0]
        if label is not None: df['label'] = label if isinstance(label, pd.Series) else label.iloc[:, 0]
        df = df.dropna()
        if df.empty: return None

        # Simple simulation: Strategy return = average label of Top-K stocks
        def top_k_ret(group):
            top_k = group.sort_values('score', ascending=False).head(50)
            return top_k['label'].mean()
        
        strat_ret = df.groupby('datetime').apply(top_k_ret)
        
        # Fill NaNs in returns to avoid breaking cumprod
        strat_ret = strat_ret.fillna(0.0)

        strategy_cum = (strat_ret + 1).cumprod()
        dates = strat_ret.index.strftime('%Y-%m-%d').tolist() if hasattr(strat_ret.index, 'strftime') else [str(x)[:10] for x in strat_ret.index]

        print("INFO: Reconstructed performance from signals (Tier 3)")
        return {
            "dates": dates,
            "strategy_cum": strategy_cum.values.tolist(),
            "benchmark_cum": None,
            "sharpe": float((strat_ret.mean() / strat_ret.std()) * (252**0.5)) if strat_ret.std() != 0 else 0,
            "max_drawdown": float(((strategy_cum - strategy_cum.cummax()) / strategy_cum.cummax()).min()),
            "source": "reconstructed"
        }
    except Exception as e:
        print(f"Reconstruction failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_backtest_plotly_data(run_id):
    """
    Orchestrates tiered extraction and caching of backtest data.
    """
    import json, qlib
    from qlib.workflow import R
    global _QLIB_INITIALIZED
    
    # 1. Cache Check
    cache_dir = '.cache_backtests'
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{run_id}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f: return json.load(f)
        except Exception: pass

    if not _QLIB_INITIALIZED:
        try: qlib.init(provider_uri='/data/qlib_data/my_data'); _QLIB_INITIALIZED = True
        except Exception: pass

    # 2. Fast Lookup & Recorder Access
    mlruns_path = 'mlruns'
    eid = None
    if os.path.exists(mlruns_path):
        for potential_eid in os.listdir(mlruns_path):
            if os.path.isdir(os.path.join(mlruns_path, potential_eid)):
                if run_id in os.listdir(os.path.join(mlruns_path, potential_eid)):
                    eid = potential_eid; break
    
    if not eid: return {"error": f"Run {run_id} not found."}
    try: recorder = R.get_recorder(recorder_id=run_id, experiment_id=eid)
    except Exception as e: return {"error": f"Recorder access failed: {e}"}

    # 3. Data Extraction Pipeline
    pred = None
    try: pred = recorder.load_object("pred_score")
    except Exception: pass

    ic_data = _extract_ic_data(recorder, pred)
    
    # Tiered Performance Search
    perf_data = _extract_performance_from_report(recorder)
    if not perf_data: perf_data = _extract_performance_from_positions(recorder)
    if not perf_data: perf_data = _reconstruct_performance_from_signals(recorder, pred)

    if not perf_data: return {"error": "No performance data could be retrieved or reconstructed."}

    # 4. Metrics & PnL
    initial_capital = 100_000_000
    pnl_data = {"dates": perf_data["dates"], "values": [initial_capital * (v - 1) for v in perf_data["strategy_cum"]]}
    
    final_mult = perf_data["strategy_cum"][-1] if perf_data["strategy_cum"] else 1.0
    summary_metrics = {
        "final_capital": initial_capital * final_mult,
        "net_profit": (final_mult - 1) * initial_capital,
        "return_pct": (final_mult - 1) * 100.0,
        "confidence_score": float(np.mean(np.abs(pred.values))) if pred is not None else 0.0,
        "source": perf_data.get("source", "unknown")
    }

    result = {"ic": ic_data, "performance": perf_data, "pnl": pnl_data, "metrics": summary_metrics}
    
    # 5. Cache & Return
    try:
        with open(cache_path, 'w') as f: json.dump(result, f)
    except Exception: pass

    # Manually free Qlib memory footprint for this scope
    import gc
    del recorder, pred, ic_data, perf_data
    gc.collect()

    return result
