import asyncio
import traceback
from pyquotex.stable_api import Quotex

async def test_auth():
    print("Testing quotex.com")
    client_com = Quotex(email="test@example.com", password="password", host="quotex.com")
    try:
        ok, msg = await client_com.connect()
        print("COM Connect result:", ok, msg)
    except Exception as e:
        print("COM Error:")
        traceback.print_exc()

asyncio.run(test_auth())
