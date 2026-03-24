import asyncio
import fractions
import json
import os

import av
import numpy as np
import requests
import sounddevice as sd

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription

_config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(_config_path) as _f:
    _config = json.load(_f)
SERVER_URL = _config["server_url"]
SAMPLE_RATE = 48000
CHANNELS = 1
BLOCK_SAMPLES = 960  # 20 ms
AUDIO_DTYPE = np.int16


class MicrophoneAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, input_device=None):
        super().__init__()
        self._loop = asyncio.get_event_loop()
        self.input_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        self.pts = 0
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SAMPLES,
            callback=self._audio_callback,
            device=input_device,
        )
        self.stream.start()

    def _audio_callback(self, indata, frames, time, status):
        chunk = np.copy(indata[:, 0])
        try:
            self._loop.call_soon_threadsafe(self.input_queue.put_nowait, chunk)
        except asyncio.QueueFull:
            pass

    async def recv(self):
        chunk = await self.input_queue.get()

        frame = av.AudioFrame(
            format="s16",
            layout="mono",
            samples=len(chunk),
        )
        frame.sample_rate = SAMPLE_RATE
        frame.time_base = fractions.Fraction(1, SAMPLE_RATE)
        frame.pts = self.pts
        self.pts += len(chunk)

        arr = chunk.reshape(1, -1)
        frame.planes[0].update(arr.tobytes())
        return frame


async def main():
    pc = RTCPeerConnection()

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state:", pc.connectionState)
        if pc.connectionState in {"failed", "closed", "disconnected"}:
            await pc.close()

    mic_track = MicrophoneAudioTrack()
    pc.addTrack(mic_track)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    response = requests.post(
        f"{SERVER_URL}/offer",
        json={
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        },
        timeout=30,
    )
    response.raise_for_status()
    answer = response.json()

    if "error" in answer:
        raise RuntimeError(answer["error"])

    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
    )

    print("Streaming microphone. Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await pc.close()


if __name__ == "__main__":
    asyncio.run(main())