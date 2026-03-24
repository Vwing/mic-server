# Remote Microphone (WebRTC + FastAPI)

Stream a microphone from one machine to another over the network and use it as a mic input on Windows.

## How it works

Sender captures mic → WebRTC → Receiver → VB-CABLE → apps see it as a microphone

FastAPI is only used for signaling. Audio is handled by WebRTC.

---

## Requirements

### Python deps

Install:

```
pip install -r requirements.txt
```

### System deps

* Install **ffmpeg**
* On Windows (receiver): install **VB-CABLE**

---

## Setup

### 1. Start receiver (Windows)

Edit nothing unless your VB-CABLE device name is different.

Run:

```
python receiver.py
```

Server starts on port 8000.

---

### 2. Start sender (any machine)

Edit `SERVER_URL` in `sender.py`:

```
SERVER_URL = "http://RECEIVER_IP:8000"
```

Then run:

```
python sender.py
```

---

## Use as microphone

On the Windows receiver machine:

* Open Discord / Zoom / Teams / etc.
* Select **VB-CABLE output/recording device** as your microphone

---

## Notes

* Works best on a local network
* Latency is low (~tens of ms)
* Audio is mono 48kHz
* No authentication (LAN use only)

---

## Troubleshooting

### No audio

* Check VB-CABLE is installed
* Verify correct device name in `receiver.py`
* Make sure sender is connected (no errors in console)

### Wrong device

Print devices:

```python
import sounddevice as sd
print(sd.query_devices())
```

Update device name in receiver.

### Choppy audio

* Ensure stable LAN connection
* Avoid WiFi if possible
* Reduce CPU load

---

## Limitations

* Single sender only
* No reconnect logic
* No NAT traversal (LAN only)
* Relies on virtual audio cable (not a native driver)
