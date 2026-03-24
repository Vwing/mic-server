from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

receiver_offer_handler = None

class SDPMessage(BaseModel):
    sdp: str
    type: str

@app.post("/register-receiver")
async def register_receiver():
    global receiver_offer_handler
    return {"ok": True}

@app.post("/offer")
async def offer(msg: SDPMessage):
    global receiver_offer_handler
    if receiver_offer_handler is None:
        return {"error": "receiver not connected"}
    answer = await receiver_offer_handler(msg.dict())
    return answer