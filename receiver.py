import asyncio
import fractions
import queue
from typing import Optional

import av
import numpy as np
import sounddevice as sd
import uvicorn

from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import FastAPI
from signaling_server import app as signaling_app

SAMPLE_RATE = 48000
CHANNELS = 1
BLOCK_SAMPLES = 960  # 20 ms at 48kHz
AUDIO_DTYPE = np.int16

audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
peer_connection: Optional[RTCPeerConnection] = None


def find_output_device(name_substring: str) -> int:
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_output_channels"] > 0 and name_substring.lower() in dev["name"].lower():
            return i
    raise RuntimeError(f"Could not find output device containing: {name_substring!r}")


def audio_callback(outdata, frames, time, status):
    try:
        chunk = audio_queue.get_nowait()
        if len(chunk) < frames:
            padded = np.zeros(frames, dtype=AUDIO_DTYPE)
            padded[: len(chunk)] = chunk
            chunk = padded
        elif len(chunk) > frames:
            chunk = chunk[:frames]
        outdata[:] = chunk.reshape(-1, 1)
    except queue.Empty:
        outdata.fill(0)


class AudioSink:
    def __init__(self, device_name_substring: str):
        self.device_id = find_output_device(device_name_substring)
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SAMPLES,
            callback=audio_callback,
            device=self.device_id,
        )

    def start(self):
        self.stream.start()


async def handle_offer(msg: dict) -> dict:
    global peer_connection

    if peer_connection:
        await peer_connection.close()

    pc = RTCPeerConnection()
    peer_connection = pc

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            asyncio.create_task(receive_audio(track))

    offer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


async def receive_audio(track):
    """
    Pull audio frames from WebRTC and convert them to mono 48k int16 PCM.
    """
    resampler = av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=SAMPLE_RATE,
    )

    pending = np.empty(0, dtype=AUDIO_DTYPE)

    while True:
        frame = await track.recv()

        resampled = resampler.resample(frame)
        if not isinstance(resampled, list):
            resampled = [resampled]

        for out_frame in resampled:
            pcm = out_frame.to_ndarray()

            # aiortc/av may return shape (channels, samples)
            if pcm.ndim == 2:
                pcm = pcm[0]

            pcm = np.asarray(pcm, dtype=AUDIO_DTYPE)
            pending = np.concatenate([pending, pcm])

            while len(pending) >= BLOCK_SAMPLES:
                block = pending[:BLOCK_SAMPLES]
                pending = pending[BLOCK_SAMPLES:]
                try:
                    audio_queue.put_nowait(block.copy())
                except queue.Full:
                    # Drop oldest behavior would be even better, but simple drop is okay for now
                    pass


def main():
    sink = AudioSink("CABLE Input")
    sink.start()

    signaling_app.state.receiver_offer_handler = handle_offer

    # Inject handler into imported module global used by the route
    import signaling_server
    signaling_server.receiver_offer_handler = handle_offer

    uvicorn.run(signaling_app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()