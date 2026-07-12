import asyncio
import logging
from pyquotex.stable_api import Quotex

logging.basicConfig(level=logging.INFO)

async def verify_quotex():
    client = Quotex(email="test@example.com", password="password", host="quotex.io")
    print("Testing connection...")
    ok, msg = await client.connect()
    print(f"Connect result: {ok}, msg: {msg}")

if __name__ == "__main__":
    asyncio.run(verify_quotex())
