import httpx
import os

class CoreEngineService:
    def __init__(self):
        # Имя хоста 'quant_engine' берется из docker-compose
        self.quant_url = os.getenv("QUANT_SERVICE_URL", "http://quant_engine:8001")

    async def get_market_signal(self, ticker: str):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.quant_url}/predict", 
                    json={"ticker": ticker},
                    timeout=5.0 # Не ждем вечно
                )
                if resp.status_code == 200:
                    return resp.json()
                else:
                    return {"error": f"Quant Error: {resp.text}"}
            except Exception as e:
                return {"error": f"Connection failed: {str(e)}"}

    async def get_backtest_list(self):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.quant_url}/backtest/list", timeout=15.0)
                if resp.status_code == 200:
                    return resp.json()
                print(f"Quant service returned error: {resp.status_code} - {resp.text}")
                return []
            except Exception as e:
                print(f"Backtest list connection error: {str(e)}")
                return []

    async def get_backtest_results(self, run_id: str):
        async with httpx.AsyncClient() as client:
            try:
                # Increase timeout to 60s as complex extractions can take time
                resp = await client.get(f"{self.quant_url}/backtest/results/{run_id}", timeout=60.0)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Backend Error: {resp.status_code}"}
            except Exception as e:
                return {"error": f"Connection Failure: {str(e)}"}

    async def trigger_training(self):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{self.quant_url}/train/trigger", timeout=5.0)
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def run_custom_backtest(self, start_date: str, end_date: str):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.quant_url}/backtest/run",
                    json={"start_time": start_date, "end_time": end_date},
                    timeout=5.0
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def get_volatility_surface(self, ticker: str):
        pass

core_engine = CoreEngineService()