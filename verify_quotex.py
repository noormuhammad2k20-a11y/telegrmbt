import asyncio
import logging
import os
from pyquotex.stable_api import Quotex
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

async def verify_quotex():
    # Load credentials from .env or config/.env
    if os.path.exists(".env"):
        load_dotenv(".env")
    else:
        load_dotenv("config/.env")
        
    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        print("ERROR: QUOTEX_EMAIL or QUOTEX_PASSWORD not found in config/.env")
        return

    # You can also pass host="quotex.com", the library will still route WS to ws2.quotex.io
    client = Quotex(email=email, password=password, host="market-qx.trade")
    print("Testing connection...")
    ok, msg = await client.connect()
    print(f"Connect result: {ok}, msg: {msg}")
    
    if ok:
        print("Connected to WebSocket successfully!")
        
        # Test fetching candles for EURUSD_otc (weekend market)
        print("Fetching candles for EURUSD_otc...")
        candles = await client.get_candles("EURUSD_otc", end_from_time=None, offset=3600, period=60)
        
        if candles:
            print(f"Success! Retrieved {len(candles)} candles.")
            print("Latest candle:", candles[-1])
        else:
            print("Failed to fetch candles or received empty data.")
            
        await client.close()
    else:
        print("Failed to authenticate/connect.")

if __name__ == "__main__":
    asyncio.run(verify_quotex())
