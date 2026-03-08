import httpx
import os

class CoreEngineService:
    def __init__(self):
        self.quant_url = os.getenv("QUANT_SERVICE_URL", "http://quant_engine:8001")
        self._client = httpx.AsyncClient(timeout=60.0)

    async def get_market_signal(self, ticker: str):
        try:
            resp = await self._client.post(
                f"{self.quant_url}/predict", 
                json={"ticker": ticker},
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"Quant Error: {resp.text}"}
        except Exception as e:
            return {"error": f"Connection failed: {str(e)}"}

    async def get_backtest_list(self):
        try:
            resp = await self._client.get(f"{self.quant_url}/backtest/list", timeout=15.0)
            if resp.status_code == 200:
                return resp.json()
            print(f"Quant service returned error: {resp.status_code} - {resp.text}")
            return []
        except Exception as e:
            print(f"Backtest list connection error: {str(e)}")
            return []

    async def get_backtest_results(self, run_id: str):
        try:
            resp = await self._client.get(f"{self.quant_url}/backtest/results/{run_id}", timeout=60.0)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Backend Error: {resp.status_code}"}
        except Exception as e:
            return {"error": f"Connection Failure: {str(e)}"}

    async def trigger_training(self):
        try:
            resp = await self._client.post(f"{self.quant_url}/train/trigger", timeout=5.0)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def run_custom_backtest(self, start_date: str, end_date: str):
        try:
            resp = await self._client.post(
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
