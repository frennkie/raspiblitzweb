import asyncio
from enum import Enum
from typing import Optional

from aioredis import Channel, Redis
from fastapi import FastAPI, Request
from fastapi.params import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from fastapi_plugins import depends_redis, redis_plugin
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse


tags_metadata = [
    {
        "name": "apps",
        "description": "Manage Apps.",
    },
    {
        "name": "demo",
        "description": "SSE Demo.",
    },
    {
        "name": "system",
        "description": "System operations (e.g. reboot).",
    },
]

app = FastAPI(
    title="Blitzd",
    description="The Raspiblitz API. More to come...",
    openapi_tags=tags_metadata,
    version="0.1"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def on_startup() -> None:
    await redis_plugin.init_app(app)
    await redis_plugin.init()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get("/sse/demo", tags=["demo"])
async def demo(request: Request):
    return templates.TemplateResponse("demo.html", {"request": request})


@app.get("/sse/publish", tags=["demo"])
async def publish(channel: str = "default", redis: Redis = Depends(depends_redis)):
    await redis.publish(channel=channel, message="Hello world!")
    return ""


@app.get("/sse/stream", tags=["demo"])
async def stream(channel: str = "default", redis: Redis = Depends(depends_redis),
                 request: Request = None,
                 accept: str = Header(None)):
    if "text/event-stream" not in accept:
        return templates.TemplateResponse("sse_only.html", {"request": request})

    print(f"running stream(): {request}")
    return EventSourceResponse(subscribe(channel, redis))


async def subscribe(channel: str, redis: Redis):
    (channel_subscription,) = await redis.subscribe(channel=Channel(channel, False))
    print("subscribe called")

    while await channel_subscription.wait_message():

        data = await channel_subscription.get(encoding='utf-8')
        print(f"data: {data}")

        yield {"event": "message", "data": data}

MESSAGE_STREAM_DELAY = 1  # second
MESSAGE_STREAM_RETRY_TIMEOUT = 15000  # millisecond

COUNT = 0


def increment():
    global COUNT
    COUNT = COUNT+1


messages = [
    ("message", "foo"),
    ("message", "bar"),
    ("message", "foobar"),
    ("new_message", "honk"),
    ("new_message", "honk hase"),
]


@app.get("/events")
async def stream(request: Request, accept: str = Header(None)):
    if "text/event-stream" not in accept:
        return templates.TemplateResponse("sse_only.html", {"request": request})

    # return EventSourceResponse()
    def new_messages():
        print(f"checking for messages: {len(messages)}")
        return len(messages)

    async def event_generator():
        while True:
            # If client was closed the connection
            if await request.is_disconnected():
                break

            # Checks for new messages and return them to client if any
            if new_messages():
                # msg = messages[(randint(0, len(messages) - 1))]
                msg = messages.pop()
                increment()
                yield {
                        "event": msg[0],
                        "id": COUNT,
                        "retry": MESSAGE_STREAM_RETRY_TIMEOUT,
                        "data": msg[1]
                }

            await asyncio.sleep(MESSAGE_STREAM_DELAY)

    return EventSourceResponse(event_generator())


class ReceiveType(str, Enum):
    lightning = "lightning"
    onchain = "onchain"


class ReceiveIn(BaseModel):
    type: ReceiveType = ReceiveType.lightning  # can be factored out into a BaseReceive
    amount: Optional[int] = Field(..., description="Amount in SATs (or in mSATs?!)", ge=0)
    comment: Optional[str]


class ReceiveOut(BaseModel):
    type: ReceiveType = ReceiveType.lightning
    data: str = Field(..., description="Address or Invoice")


@app.post("/receive", response_model=ReceiveOut,
          summary="Create invoice or address for receiving")
async def receive_funds(obj: ReceiveIn):
    """
    Create a lightning invoice or address (onchain) in order to received funds:

    - **type**: either lightning or onchain
    - **amount**: a long description
    - **comment**: optional
    """

    if obj.type == ReceiveType.onchain:
        return ReceiveOut(type=obj.type, data="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    else:
        return {"type": obj.type, "data": "lntb1u1pwz5w78pp5e8w8cr5c30xzws92v3"}  # same as using the ReceiveOut model


@app.post("/send")
async def send():
    return {"status": "success"}


@app.post("/changepw", tags=["system"])
async def change_password():
    return {"status": "success"}


@app.post("/reboot", tags=["system"])
async def reboot():
    return {"status": "success"}


@app.post("/shutdown", tags=["system"])
async def shutdown(token: str = Depends(oauth2_scheme)):
    print(f"Token: {token}")
    return {"status": "success"}


@app.post("/syncstatus")
async def syncstatus():
    return {"status": "success"}


@app.get("/appstatus", tags=["apps"])
async def show_app_status():
    return {"status": "success"}


@app.get("/apps", summary="List info about Apps. (Supports SSE)", tags=["apps"])
async def apps():
    print("appending message")
    messages.append(("message", "yeah"))
    return


@app.get("/transactions")
async def transactions():
    print("TODO: list txs")
    return {"status": "success"}


@app.get("/tx/{tx_id}")
async def transactions(tx_id: str):
    print(f"call to /tx/{tx_id}")

    if tx_id == "blablabla":

        return {
            "type": 'onchain',  # or lightning
            "hash": '4073686402f35297e6f153bceda0fad51645b35243f21324760c1774f384fdf9',
            "confirmations": 2,
            "date": 1618501200,  # epoch timestamp
            "block": 683738,  # can be null if not confirmed
            "feeRate": 61.9,  # sat/vByte
            "fee": 0.00158274,
            "description": 'hi!'  # if available
        }

    else:
        return {
            "type": 'lightning',
            "hash": '1d4443dcad965200d01c0ee34332grfwqwe76j',
            "request":
                'LNBC50509VKAVKAVKAVAKVAKVKAVKAVKBLABLABLABLSBLABLSABSLABSALAALBASLSBALBSGSDQ6XGSV'
                '89EQGF6KUERVV5S8QCTRDVCQZPGXQRRSSSP538GMWU7BYNZ5FKJG4PDUN2GGMDCJJV9MHJARKDR3CJS9Q'
                'Y9QSQ6UVDP99NYTD',
            "status": 'SUCCEEDED',
            "date": '1618501200',  # epoch timestamp
            "fee": 2,  # (mSats)
            "value": 100000,  # (mSats) = > 100 sat
            "description": 'hi!',  # if available
        }
