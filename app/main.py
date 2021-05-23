from enum import Enum
from typing import Optional

from aioredis import Channel, Redis
from fastapi import FastAPI
from fastapi.params import Depends, Header
from fastapi_plugins import depends_redis, redis_plugin
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>SSE</title>
    </head>
    <body>
    
      <h1>Getting server updates</h1>
      <div id="result"></div>
        
      <script>
          if(typeof(EventSource) !== "undefined") {
              const evtSource = new EventSource("http://localhost:8000/sse/stream");              
              evtSource.addEventListener("message", function(event) {
              // Logic to handle status updates
              console.log(event.data);
            
              try{ 
                  console.log(JSON.parse(event.data)); 
              } catch(e) { 
                  document.getElementById("result").innerHTML += "ERROR: Caught: " + e.message + " --- ";
              }
                   
              document.getElementById("result").innerHTML += event.data + "<br>";            
            
          });              
          } else {
              document.getElementById("result").innerHTML = "Sorry, your browser does not support server-sent events.";
          }
      </script>
    </body>
</html>
"""

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


@app.on_event("startup")
async def on_startup() -> None:
    await redis_plugin.init_app(app)
    await redis_plugin.init()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get("/sse/demo", tags=["demo"])
async def demo():
    return HTMLResponse(html)


@app.get("/sse/publish", tags=["demo"])
async def publish(channel: str = "default", redis: Redis = Depends(depends_redis)):
    await redis.publish(channel=channel, message="Hello world!")
    return ""


@app.get("/sse/stream", tags=["demo"])
async def stream(channel: str = "default", redis: Redis = Depends(depends_redis),
                 accept: str = Header(None)):
    if "text/event-stream" not in accept:
        return HTMLResponse("<!DOCTYPE html><html><title></title><body>SSE only!</body></html>")

    return EventSourceResponse(subscribe(channel, redis))


async def subscribe(channel: str, redis: Redis):
    (channel_subscription,) = await redis.subscribe(channel=Channel(channel, False))
    while await channel_subscription.wait_message():
        yield {"event": "message", "data": await channel_subscription.get(encoding='utf-8')}


class ReceiveType(str, Enum):
    lightning = "lightning"
    onchain = "onchain"


class BaseReceive(BaseModel):
    type: ReceiveType = ReceiveType.lightning


class ReceiveIn(BaseReceive):
    amount: Optional[int] = Field(..., description="Amount in SATs (or in mSATs?!)", ge=0)
    comment: Optional[str]


class ReceiveOut(BaseReceive):
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
        return {"type": obj.type, "data": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"}
    else:
        return {"type": obj.type, "data": "lntb1u1pwz5w78pp5e8w8cr5c30xzws92v3"}


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
async def shutdown():
    return {"status": "success"}


@app.post("/syncstatus")
async def syncstatus():
    return {"status": "success"}


@app.get("/appstatus", tags=["apps"])
async def show_app_status():
    return {"status": "success"}


@app.get("/apps", summary="List info about Apps. (Supports SSE)", tags=["apps"])
async def apps():
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
