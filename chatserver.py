import asyncio
import math
import base64
import numpy as np
import json

import websockets
from websockets.asyncio.server import serve

DISTANCE = 5000

class Client:
    connected_clients = set()
    
    def __init__(self, websocket):
        self.websocket = websocket
        self.display_name = ""
        self.xyz = (0, 0, 0)
        self.zone_id = 0
        Client.connected_clients.add(self)
    
    def update_location(self, xyz, zone_id):
        self.xyz = xyz
        self.zone_id = zone_id
        
    def distance(self, other: 'Client'):
        return math.sqrt(math.pow(other.xyz[0] - self.xyz[0], 2) + math.pow(other.xyz[1] - self.xyz[1], 2) + math.pow(other.xyz[2] - self.xyz[2], 2))
    
    def in_range_of(self, other: 'Client'):
        if other.zone_id != self.zone_id:
            return False
        
        dist = self.distance(other)
        
        if dist > DISTANCE:
            return False
        
        return True
    

async def handle_client(websocket):
    client = Client(websocket)
    print(f"Connected User")
    try:
        async for data in websocket:
            try:
                event = json.loads(data)
                voice_data = event["data"]
                client.display_name = event["name"]
                client.update_location((event["x"], event["y"], event["z"]), event["zone_id"])

                async def send_to_client(other_client):
                    in_range = client.in_range_of(other_client)
                    if in_range and other_client.websocket != client.websocket: 
                        event = {
                            "name": other_client.display_name,
                            "data": voice_data
                        }
                        
                        await other_client.websocket.send(json.dumps(event))
                
                await asyncio.gather(*[send_to_client(p) for p in Client.connected_clients])
            except websockets.exceptions.ConnectionClosed as e:
                print(f"{client.display_name} cause {e}")
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        Client.connected_clients.remove(client)
        print("Disconnected User")

async def main():
    server = await serve(handle_client, "0.0.0.0", 8765)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())