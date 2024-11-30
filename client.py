import asyncio
import pyaudio
import queue
import base64
import webrtcvad
import json

from websockets.asyncio.client import connect

uri = "ws://localhost:8765"

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
                    event = {
                        "name": "Corey Pants",
                        "volume_setting": 100,
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "zone": "WC/Ravenwood",
                        "realm": "Ambrose",
                        "area": 1,
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
                
                print(f"{talking_client} >>> home")
                
                if jitter_buffer.qsize() < JITTER_BUFFER_SIZE:
                    jitter_buffer.put(voice_data)

                # Start playback only after prefill
                if jitter_buffer.qsize() > prefill:
                    stream.write(jitter_buffer.get())
                        
                await asyncio.sleep(0.001)

        # Run send and receive simultaneously
        await asyncio.gather(send_data(), receive_data())

async def main():
    await send_and_receive_data()

if __name__ == "__main__":
    asyncio.run(main())