import asyncio
import pyaudio
import queue
import base64
import webrtcvad
import json
import numpy as np

from websockets.asyncio.client import connect

from wizwalker.extensions.wizsprinter import WizSprinter, SprintyClient

sprinter = WizSprinter()
sprinty_client = (sprinter.get_new_clients())[0]

uri = "ws://69.48.206.144:8765"

MICROPHONE = 100
VOLUME = 100
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
JITTER_BUFFER_SIZE = 50
FRAME_DURATION = 20
CHUNK = int(RATE * FRAME_DURATION / 1000)

vad = webrtcvad.Vad(mode=1)

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
                audio_samples = np.frombuffer(data, dtype=np.int16)
                adjusted_samples = np.clip(audio_samples * (MICROPHONE / 100), -32768, 32767).astype(np.int16)
                adjusted_data = adjusted_samples.tobytes()
                
                is_speaking = vad.is_speech(adjusted_data, RATE)
                
                if is_speaking:
                    name =  await sprinty_client.client_object.display_name()
                    xyz = await sprinty_client.body.position()
                    client_zone = await sprinty_client.client_object.client_zone()
                    if client_zone != None:
                        zone_id = await client_zone.zone_id()
                        
                        event = {
                            "name": name,
                            "x": xyz.x,
                            "y": xyz.y,
                            "z": xyz.z,
                            "zone_id": zone_id,
                            "data": base64.b64encode(adjusted_data).decode("utf-8")
                        }
                        await websocket.send(json.dumps(event))
                    
                await asyncio.sleep(0.001)

        async def receive_data():
            prefill = 20  # Prefill buffer before playback
            while True:
                data = await websocket.recv()
                event = json.loads(data)
                voice_data = base64.b64decode(event["data"])
                audio_samples = np.frombuffer(voice_data, dtype=np.int16)
                adjusted_samples = np.clip(audio_samples * (VOLUME / 100), -32768, 32767).astype(np.int16)
                adjusted_data = adjusted_samples.tobytes()
                talking_client = event["name"]
                
                print(f"{talking_client} >>>")
                
                if jitter_buffer.qsize() < JITTER_BUFFER_SIZE:
                    jitter_buffer.put(adjusted_data)

                # Start playback only after prefill
                if jitter_buffer.qsize() > prefill:
                    stream.write(jitter_buffer.get())
                        
                await asyncio.sleep(0.001)

        # Run send and receive simultaneously
        await asyncio.gather(send_data(), receive_data())

async def setup_wizwalker():
    await sprinty_client.hook_handler.activate_client_hook()
    await sprinty_client.hook_handler.activate_player_hook()

async def close_wizwalker():
    await sprinty_client.hook_handler.deactivate_client_hook()
    await sprinty_client.hook_handler.deactivate_player_hook()
    await sprinty_client.hook_handler.close()

async def main():
    await setup_wizwalker()
    await send_and_receive_data()
    await close_wizwalker()

if __name__ == "__main__":
    asyncio.run(main())