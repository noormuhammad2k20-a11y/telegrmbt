import asyncio
import websockets

async def test_ws():
    uri = "wss://ws2.quotex.io/socket.io/?EIO=3&transport=websocket"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Receiving message...")
            msg = await ws.recv()
            print("Received:", msg)
    except Exception as e:
        print("Error:", e)

asyncio.run(test_ws())
