import socket
domains = ['ws.quotex.io', 'ws2.quotex.io', 'qxbroker.com', 'ws.qxbroker.com', 'ws2.qxbroker.com', 'quotex.io', 'ws.quotex.com', 'ws2.quotex.com', 'quotex.com']
for d in domains:
    try:
        print(d, socket.gethostbyname(d))
    except Exception as e:
        print(d, 'Failed:', e)
