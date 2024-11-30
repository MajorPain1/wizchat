import asyncio
import pyaudio
import queue
import base64
import webrtcvad
import json

from websockets.asyncio.client import connect

from wizwalker.extensions.wizsprinter import WizSprinter, SprintyClient

sprinter = WizSprinter()
sprinter.get_new_clients()
client = sprinter.get_foreground_client()

uri = "ws://69.48.206.144:8765"

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
JITTER_BUFFER_SIZE = 50
FRAME_DURATION = 20
CHUNK = int(RATE * FRAME_DURATION / 1000)

vad = webrtcvad.Vad(mode=0)

audio = pyaudio.PyAudio()

jitter_buffer = queue.Queue(maxsize=JITTER_BUFFER_SIZE)

# Function to send and receive audio
async def send_and_receive_data():
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True, output=True,
                        frames_per_buffer=CHUNK)

    async with connect(uri) as websocket:
        async def send_data():
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                
                is_speaking = vad.is_speech(data, RATE)
                
                if is_speaking:
                    #display_name =  await client.client_object.display_name()
                    #xyz = await client.client_object.read_xyz()
                    #zone_name = await client.zone_name()
                    
                    event = {
                        "name": "Pants",
                        "volume_setting": 100,
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "zone": "zone_name",
                        "realm": "Ambrose", # Need wizwalker method
                        "area": 1, # Need wizwalker method
                        "data": base64.b64encode(data).decode("utf-8")
                    }
                    await websocket.send(json.dumps(event))
                    
                await asyncio.sleep(0.001)

        async def receive_data():
            prefill = 10  # Prefill buffer before playback
            while True:
                data = await websocket.recv()
                event = json.loads(data)
                voice_data = base64.b64decode(event["data"])
                talking_client = event["name"]
                
                print(f"{talking_client} >>>")
                
                if jitter_buffer.qsize() < JITTER_BUFFER_SIZE:
                    jitter_buffer.put(voice_data)

                # Start playback only after prefill
                if jitter_buffer.qsize() > prefill:
                    stream.write(jitter_buffer.get())
                        
                await asyncio.sleep(0.001)

        # Run send and receive simultaneously
        await asyncio.gather(send_data(), receive_data())

async def setup_wizwalker():
    await client.hook_handler.activate_client_hook()
    await client.hook_handler.activate_player_hook()

async def close_wizwalker():
    await client.close()

async def main():
    #await setup_wizwalker()
    await send_and_receive_data()
    #await close_wizwalker()

if __name__ == "__main__":
    asyncio.run(main())