import asyncio
import math
import base64
import numpy as np
import json

import websockets
from websockets.asyncio.server import serve

DISTANCE = 1200

class Client:
    connected_clients = set()
    
    def __init__(self, websocket):
        self.websocket = websocket
        self.display_name = ""
        self.xyz = (0, 0, 0)
        self.zone = ""
        self.realm = ""
        self.area = 0
        self.volume_setting = 100
        Client.connected_clients.add(self)
    
    def update_location(self, xyz, zone, realm, area):
        self.xyz = xyz
        self.zone = zone
        self.realm = realm
        self.area = area
        
    def distance(self, other: 'Client'):
        return math.sqrt(math.pow(other.xyz[0] - self.xyz[0], 2) + math.pow(other.xyz[1] - self.xyz[1], 2) + math.pow(other.xyz[2] - self.xyz[2], 2))
    
    def in_range_of(self, other: 'Client'):
        if other.zone != self.zone:
            return (False, 0)
        
        if other.realm != self.realm:
            return (False, 0)
        
        if other.area != self.area:
            return (False, 0)
        
        dist = self.distance(other)
        
        if dist > DISTANCE:
            return (False, 0)
        
        return (True, 1-((dist-self.volume_setting)/DISTANCE))
    

async def handle_client(websocket):
    client = Client(websocket)
    try:
        async for data in websocket:
            event = json.loads(data)
            client.display_name = event["name"]
            client.volume_setting = event["volume_setting"]
            client.update_location((event["x"], event["y"], event["z"]), event["zone"], event["realm"], event["area"])
            
            voice_data = base64.b64decode(event["data"])
            
            for other_client in Client.connected_clients:
                other_client: Client
                
                in_range, volume = client.in_range_of(other_client)
                if in_range and other_client.websocket != client.websocket: 
                    audio_samples = np.frombuffer(voice_data, dtype=np.int16)
                    adjusted_samples = np.clip(audio_samples * volume, -32768, 32767).astype(np.int16)
                    adjusted_data = adjusted_samples.tobytes()
                    
                    event = {
                        "name": other_client.display_name,
                        "data": base64.b64encode(adjusted_data).decode("utf-8")
                    }
                    
                    await client.websocket.send(json.dumps(event))
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        Client.connected_clients.remove(client)
        

async def main():
    server = await serve(handle_client, "0.0.0.0", 8765)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())