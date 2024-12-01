import asyncio
import multiprocessing
import multiprocessing.connection
import pyaudio
import queue
import base64
import webrtcvad
import json
import numpy as np
import itertools

from websockets.asyncio.client import connect

from wizwalker.extensions.wizsprinter import WizSprinter
from websockets.exceptions import ConnectionClosed

sprinter = WizSprinter()
sprinty_client = (sprinter.get_new_clients())[0]

uri = "ws://69.48.206.144:8765"
#uri = "ws://localhost:8765"

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

async def keepalive(websocket, ping_interval=30):
    for ping in itertools.count():
        await asyncio.sleep(ping_interval)
        try:
            await websocket.send(json.dumps({"ping": ping}))
        except ConnectionClosed:
            break

def playback(pipe: multiprocessing.connection.Connection):
    stream = audio.open(format=FORMAT, channels=CHANNELS,
        rate=RATE, input=False, output=True,
        frames_per_buffer=CHUNK
    )
    jitter_buffer = []
    prefill = 50

    while not pipe.closed:
        segments = []
        i = 0
        while pipe.poll():
            data = pipe.recv_bytes()
            event = json.loads(data)
            
            voice_data = base64.b64decode(event["data"])
            audio_samples = np.frombuffer(voice_data, dtype=np.int16)
            adjusted_samples = np.clip(audio_samples * (VOLUME / 100), -32768, 32767).astype(np.float32)
            
            if len(adjusted_samples) > 0:
                # TODO: Resample if sizes don't match
                segments.append(adjusted_samples)
                
        if len(segments) > 0:
            data = segments[0] / len(segments)
            for i in range(1, len(segments)):
                data = data + segments[i] / len(segments)
            #data /= len(segments)
            adjusted_samples = data.astype(np.int16)
            jitter_buffer.append(adjusted_samples.tobytes())
            if len(jitter_buffer) > prefill:
                stream.write(jitter_buffer.pop(0))


def record(pipe: multiprocessing.connection.Connection):
    stream = audio.open(format=FORMAT, channels=CHANNELS,
        rate=RATE, input=True, output=False,
        frames_per_buffer=CHUNK
    )
    while not pipe.closed:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_samples = np.frombuffer(data, dtype=np.int16)
        adjusted_samples = np.clip(audio_samples * (MICROPHONE / 100), -32768, 32767).astype(np.int16)
        adjusted_data = adjusted_samples.tobytes()

        is_speaking = vad.is_speech(adjusted_data, RATE)
        
        if is_speaking:
            pipe.send_bytes(adjusted_data)


# Function to send and receive audio
async def send_and_receive_data():
    async with connect(uri) as websocket:
        keepalive_task = asyncio.create_task(keepalive(websocket))
        try:
            async def send_data():
                pipe_in, pipe_out = multiprocessing.Pipe()
                proc = multiprocessing.Process(target=record, args=(pipe_in,), daemon=True)
                proc.start()
                while True:
                    if not pipe_out.poll():
                        await asyncio.sleep(0.01)
                        continue
                    
                    name =  await sprinty_client.client_object.display_key()
                    xyz = await sprinty_client.body.position()
                    client_zone = await sprinty_client.client_object.client_zone()
                    
                    if client_zone == None:
                        continue
                    
                    zone_id = await client_zone.zone_id()
                    
                    data = pipe_out.recv_bytes()
                    event = {
                        "name": name,
                        "x": xyz.x,
                        "y": xyz.y,
                        "z": xyz.z,
                        "zone_id": zone_id,
                        "data": base64.b64encode(data).decode("utf-8")
                    }
                    await websocket.send(json.dumps(event))

            async def receive_data():
                pipe_in, pipe_out = multiprocessing.Pipe()
                proc = multiprocessing.Process(target=playback, args=(pipe_in,), daemon=True)
                proc.start()
                while True:
                    data = bytes(await websocket.recv(), "utf-8")
                    pipe_out.send_bytes(data)

            # force connect
            event = {
                "name": "gamer",
                "x": 0,
                "y": 0,
                "z": 0,
                "zone_id": 0,
                "data": base64.b64encode(b"").decode("utf-8")
            }
            await websocket.send(json.dumps(event))

            # Run send and receive simultaneously
            await asyncio.gather(
                send_data(),
                receive_data(),
            )
        finally:
            keepalive_task.cancel()

async def setup_wizwalker():
    await sprinty_client.hook_handler.activate_client_hook()
    await sprinty_client.hook_handler.activate_player_hook()

async def close_wizwalker():
    await sprinty_client.hook_handler.deactivate_client_hook()
    await sprinty_client.hook_handler.deactivate_player_hook()
    await sprinty_client.hook_handler.close()

async def main():
    try:
        await setup_wizwalker()
        await send_and_receive_data()
    except KeyboardInterrupt:
        pass
    finally:
        await close_wizwalker()

if __name__ == "__main__":
    asyncio.run(main())