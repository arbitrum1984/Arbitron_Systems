import pandas as pd
import matplotlib.pyplot as plt
import qlib
import numpy as np
import os
from sklearn.metrics import mean_absolute_error, accuracy_score
from qlib.contrib.evaluate import backtest_daily
from qlib.contrib.strategy import TopkDropoutStrategy

# Создаем папку для отчетов, если её нет
os.makedirs("analysis", exist_ok=True)

def plot_signal_quality(recorder):
    """
    Анализ качества сигнала (IC, Rank IC) + Метрики ошибок (MAE, Accuracy).
    """
    print("\n--- Запуск анализа качества сигналов (Signal Quality) ---")
    try:
        pred = recorder.load_object("pred_score")
        label = recorder.load_object("label")
    except Exception as e:
        print(f"❌ Ошибка загрузки данных для IC: {e}")
        return

    # Совмещаем данные в один DataFrame
    df = pd.DataFrame()
    
    # Обработка предсказаний
    if isinstance(pred, pd.DataFrame):
        df['score'] = pred.iloc[:, 0]
    elif isinstance(pred, pd.Series):
        df['score'] = pred
    else:
        print(f"Неизвестный формат pred: {type(pred)}")
        return

    # Обработка меток (реальных данных)
    if isinstance(label, pd.DataFrame):
        df['label'] = label.iloc[:, 0]
    elif isinstance(label, pd.Series):
        df['label'] = label
        
    df = df.dropna()

    if df.empty:
        print("⚠️ Внимание: после объединения pred и label данные пусты. Проверьте индексы.")
        return

    # --- РАСЧЕТ МЕТРИК ОШИБОК (Для отчета заказчику) ---
    # MAE: Средняя абсолютная ошибка
    mae = mean_absolute_error(df['label'], df['score'])
    
    # Accuracy: Точность направления (угадали ли знак доходности)
    # 1 если знаки совпадают, 0 если нет.
    pred_sign = np.sign(df['score'])
    label_sign = np.sign(df['label'])
    # Исключаем нулевые значения для чистоты эксперимента, либо считаем 0 как неугадывание
    valid_dirs = df[df['label'] != 0]
    if not valid_dirs.empty:
        acc = accuracy_score(np.sign(valid_dirs['label']), np.sign(valid_dirs['score']))
    else:
        acc = 0.0

    print("="*40)
    print(" 📊 МЕТРИКИ МОДЕЛИ (Model Metrics) ")
    print(f" • Direction Accuracy (Точность): {acc:.2%}")
    print(f" • Mean Absolute Error (MAE):     {mae:.5f}")
    print("="*40)

    # --- РАСЧЕТ IC (Information Coefficient) ---
    # Группируем по дате, чтобы смотреть стабильность во времени
    ic = df.groupby('datetime').apply(lambda x: x['score'].corr(x['label']))
    ric = df.groupby('datetime').apply(lambda x: x['score'].corr(x['label'], method='spearman'))
    
    mean_ic = ic.mean()
    mean_ric = ric.mean()

    print(f" • Mean IC:      {mean_ic:.4f}")
    print(f" • Mean Rank IC: {mean_ric:.4f}")
    print("="*40)

    # Отрисовка графика
    plt.figure(figsize=(12, 6))
    ic.plot(kind="bar", width=0.9)
    
    # Убираем подписи оси X, если их слишком много, оставляем структуру
    plt.xticks([]) 
    
    # Линия среднего
    plt.axhline(mean_ic, color='r', linestyle='--', label=f'Mean IC: {mean_ic:.4f}')
    
    # Заголовок с метриками (чтобы сразу было видно на скрине)
    plt.title(f"Information Coefficient (IC)\nAccuracy: {acc:.1%} | MAE: {mae:.4f} | Mean IC: {mean_ic:.4f}")
    
    plt.legend()
    plt.tight_layout()
    
    save_path = "analysis/ic_report.png"
    plt.savefig(save_path)
    plt.close()
    print(f"✅ График сохранен: {save_path}")


def plot_strategy_performance(recorder):
    """
    Рисует кривую доходности и считает финансовые метрики (Sharpe, Drawdown).
    """
    print("\n--- Запуск анализа стратегии (Strategy Performance) ---")
    df = None
    
    # 1. ПОПЫТКА ЗАГРУЗИТЬ ГОТОВЫЙ ОТЧЕТ ИЗ RECORDER
    try:
        raw_obj = recorder.load_object("report")
        if isinstance(raw_obj, pd.DataFrame) and not raw_obj.empty:
            df = raw_obj
        elif isinstance(raw_obj, dict) and raw_obj:
            for key in ['return', 'account', 'portfolio', 'value']:
                if key in raw_obj and isinstance(raw_obj[key], pd.DataFrame):
                    df = raw_obj[key]
                    break
            if df is None:
                for v in raw_obj.values():
                    if isinstance(v, pd.DataFrame) and not v.empty:
                        df = v
                        break
    except Exception:
        pass # Игнорируем ошибки загрузки, переходим к fallback

    # 2. FALLBACK: ЕСЛИ ОТЧЕТА НЕТ, ЗАПУСКАЕМ БЭКТЕСТ ЗАНОВО
    if df is None or df.empty:
        print("⚠️ Сохраненный отчет не найден. Запускаем симуляцию (Backtest)...")
        try:
            pred = recorder.load_object("pred_score")
            if isinstance(pred, pd.Series):
                pred = pred.to_frame(name='score')
            
            # Настройки стратегии (Top 30 акций, отсеиваем 5)
            STRATEGY_CONFIG = {
                "topk": 10,
                "n_drop": 2,
                "signal": pred,
            }
            
            df, _ = backtest_daily(
                start_time=pred.index.get_level_values("datetime").min(),
                end_time=pred.index.get_level_values("datetime").max(),
                strategy=TopkDropoutStrategy(**STRATEGY_CONFIG),
            )
            print("Симуляция завершена.")
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА БЭКТЕСТА: {e}")
            return

    # 3. ПОДГОТОВКА ДАННЫХ
    df.columns = [str(c).lower() for c in df.columns]
    
    # Определяем доходность стратегии
    if 'return' in df.columns:
        df['strategy_return'] = df['return']
    elif 'account' in df.columns:
        df['strategy_return'] = df['account'].pct_change().fillna(0)
    else:
        df['strategy_return'] = df.iloc[:, 0]

    # Определяем бенчмарк
    if 'bench' in df.columns:
        df['benchmark_return'] = df['bench']
    elif 'index' in df.columns:
        df['benchmark_return'] = df['index']
    else:
        df['benchmark_return'] = 0.0

    # --- РАСЧЕТ ФИНАНСОВЫХ МЕТРИК (Для AI Asset Manager) ---
    strategy_ret = df['strategy_return']
    
    # Sharpe Ratio (Ann.) - предполагаем 252 торговых дня
    if strategy_ret.std() != 0:
        sharpe = (strategy_ret.mean() / strategy_ret.std()) * (252 ** 0.5)
    else:
        sharpe = 0.0
    
    # Max Drawdown
    cum_ret = (strategy_ret + 1).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / running_max
    max_dd = drawdown.min() # Отрицательное число

    # Annualized Return
    days = (df.index.max() - df.index.min()).days
    if days > 0:
        total_ret = cum_ret.iloc[-1] - 1
        annual_ret = (1 + total_ret) ** (365/days) - 1
    else:
        annual_ret = 0.0

    print("="*40)
    print(" 💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ (Financial Metrics) ")
    print(f" • Annual Return (Годовые): {annual_ret:.2%}")
    print(f" • Sharpe Ratio:            {sharpe:.2f}")
    print(f" • Max Drawdown (Просадка): {max_dd:.2%}")
    print("="*40)

    # 4. ОТРИСОВКА
    plt.figure(figsize=(12, 6))
    
    strategy_cum = (df['strategy_return'] + 1).cumprod()
    strategy_cum.plot(label='AI Strategy', linewidth=2)
    
    if (df['benchmark_return'] != 0).any():
        bench_cum = (df['benchmark_return'] + 1).cumprod()
        bench_cum.plot(label='Market Benchmark', alpha=0.7, linestyle='--')
    
    # Заголовок с метриками
    title_str = f"Strategy Performance\nSharpe: {sharpe:.2f} | Max Drawdown: {max_dd:.1%} | Ann. Ret: {annual_ret:.1%}"
    
    plt.title(title_str)
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    save_path = "analysis/strategy_performance.png"
    plt.savefig(save_path)
    plt.close()
    print(f"✅ График сохранен: {save_path}")
    print("-------------------------------------------------------")

def plot_pnl_metrics(recorder):
    print("\n--- Генерация PnL отчета (с авто-восстановлением) ---")
    
    df = None
    # 1. Пытаемся загрузить отчет
    try:
        raw_report = recorder.load_object("report")
        if isinstance(raw_report, pd.DataFrame) and not raw_report.empty:
            df = raw_report
        elif isinstance(raw_report, dict):
            for v in raw_report.values():
                if isinstance(v, pd.DataFrame) and not v.empty:
                    df = v
                    break
    except:
        pass

    # 2. ФОЛБЭК (МАГИЯ): Если данных нет, делаем как в Strategy Performance — запускаем симуляцию
    if df is None or df.empty:
        print("⚠️ Данные PnL не найдены. Запускаю экстренную симуляцию для получения данных...")
        try:
            pred = recorder.load_object("pred_score")
            if isinstance(pred, pd.Series): pred = pred.to_frame(name='score')
            
            # Используем те же параметры, что и в Strategy Performance
            from qlib.contrib.evaluate import backtest_daily
            from qlib.contrib.strategy import TopkDropoutStrategy
            
            df, _ = backtest_daily(
                start_time=pred.index.get_level_values("datetime").min(),
                end_time=pred.index.get_level_values("datetime").max(),
                strategy=TopkDropoutStrategy(topk=30, n_drop=5, signal=pred),
            )
            print("✅ Данные для PnL успешно сгенерированы симуляцией.")
        except Exception as e:
            print(f"❌ Даже симуляция не помогла: {e}")
            return

    # 3. Теперь у нас ТОЧНО есть df. Считаем деньги.
    df.columns = [str(c).lower() for c in df.columns]
    initial_capital = 100_000_000
    
    # Определяем доходность (ищем колонку return)
    ret_col = 'return' if 'return' in df.columns else df.columns[0]
    
    # Считаем PnL в деньгах
    df['total_pnl'] = initial_capital * ((1 + df[ret_col]).cumprod() - 1)
    df['daily_pnl'] = df['total_pnl'].diff().fillna(df['total_pnl'].iloc[0])

    # 4. Рисуем
    try:
        fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        # Накопленный PnL
        axes[0].fill_between(df.index, df['total_pnl'], 0, where=(df['total_pnl'] >= 0), color='g', alpha=0.3)
        axes[0].fill_between(df.index, df['total_pnl'], 0, where=(df['total_pnl'] < 0), color='r', alpha=0.3)
        axes[0].plot(df['total_pnl'], color='black', linewidth=1)
        axes[0].set_title(f"Cumulative PnL (Total Cash: {df['total_pnl'].iloc[-1]:,.2f})", fontsize=14)
        axes[0].grid(True, alpha=0.3)

        # Дневной PnL
        colors = ['g' if v >= 0 else 'r' for v in df['daily_pnl']]
        axes[1].bar(df.index, df['daily_pnl'], color=colors, alpha=0.7)
        axes[1].set_title("Daily PnL (Money Flow)", fontsize=12)
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        save_path = "analysis/pnl_report.png"
        plt.savefig(save_path)
        plt.close()
        print(f"✅ График PnL сохранен: {save_path}")
    except Exception as e:
        print(f"❌ Ошибка отрисовки: {e}")