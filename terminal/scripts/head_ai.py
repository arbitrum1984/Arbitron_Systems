
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_service import ai_engine

async def head_check(ticker):
    resp = await ai_engine.get_response(f"Analyze {ticker}")
    lines = resp['text'].split('\n')
    for i, line in enumerate(lines[:15]):
        print(f"{i+1:2}: {line}")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    asyncio.run(head_check(ticker))
