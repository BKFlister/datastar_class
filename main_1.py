import asyncio
import json
import time
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

#region Datastar
class MergeType(str, Enum):
    MORPH = "morph_element"
    INNER = "inner_element"
    OUTER = "outer_element"
    PREPEND = "prepend_element"
    APPEND = "append_element"
    BEFORE = "before_element"
    AFTER = "after_element"
    DELETE = "delete_element"
    UPSERT_ATTRIBUTES = "upsert_attributes"

class DatastarEvent:
    def __init__(
        self,
        fragment: str,
        merge: MergeType | None = None,
        query_selector: str | None = None,
        settle_duration: int | None = None,
        use_view_transitions: bool | None = None
    ):
        data_lines: list[str] = []

        if query_selector:
            data_lines.append(f"selector {query_selector}")

        if merge:
            data_lines.append(f"merge {merge.value}")

        if settle_duration:
            data_lines.append(f"settle {settle_duration}")

        if use_view_transitions is not None:
            data_lines.append(f"vt {str(use_view_transitions).lower()}")

        data_lines.append(f"fragment {fragment}")

        self.data = "\ndata: ".join(data_lines)
        self.event = "datastar-fragment"

    def format_sse(self):
        """Format the event data for Server-Sent Events (SSE)."""
        return f"event: {self.event}\ndata: {self.data}\n\n"

    async def event_generator(self):
        """Generate the SSE event."""
        yield self.format_sse()

class DatastarSignal:
    def __init__(self, store: dict):
        self.store = store
        self.event = "datastar-signal"

    def format_sse(self):
        """Format the event data for Server-Sent Events (SSE)."""
        return f"event: {self.event}\ndata: {json.dumps(self.store)}\n\n"

    async def event_generator(self):
        """Generate the SSE event."""
        yield self.format_sse()

class DataStarStreamer:
    def __init__(self, condition_callable, interval=1):
        self.condition_callable = condition_callable
        self.interval = interval

    async def stream(self, fragment_generator):
        while True:
            if self.condition_callable():
                fragment = await fragment_generator()
                if fragment:
                    event = DatastarEvent(**fragment)
                    yield await event.event_generator().__anext__()
            await asyncio.sleep(self.interval)
#endregion Datastar

# Global store and other variables
store = {"input": "datastar", "output": "", "_show": False, "message": "", "send": "", "update_store": ""}
single_target ='single_target'
target_1 ='target_1'
target_2 ='target_2'
target_3 ='target_3'
send = False
i = 0

app = FastAPI()

html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Fastapi SSE with Datastar</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script type="module" defer src="https://cdn.jsdelivr.net/npm/@sudodevnull/datastar@0.18.13/dist/datastar.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">
</head>
<body>
    <h2>Python/FastAPI + Datastar Example</h2>
    <main class="container" id="main" data-store='{json.dumps(store)}'>

        <hr />

        <input type="text" placeholder="Send to server..." data-model="input" />
        <button data-on-click="$$get('/get')">Send State Roundtrip</button>
        <div id="output" data-text="$output"></div>
        <hr />

        <button data-on-click="$$get('/target')">Target single HTML Element</button>
        <div id="{single_target}"></div>
        <hr />

        <button data-on-click="$$get('/multi-target')">Target multiple HTML Element</button>
        <div id="{target_1}"></div>
        <div id="{target_2}"></div>
        <div id="{target_3}"></div>
        <hr />

        <button data-on-click="$$get('update-store')">Update `data-store` only</button>
        <div id="update_store" data-text="'Data-store variable: update_store=' + $update_store"></div>
        <hr />

        <button data-on-click="$_show=!$_show">Toggle Show Feed</button>
        <div data-show="$_show">
        <button data-on-click="$$get('/toggle')">Toggle Feed from server</button>
        <span>Feed from server: <span data-text="$send ? 'Active' : 'Inactive'"></span></span>
        <div id="feeds" style="border: 1px solid red; max-height: 300px; overflow:auto;" data-on-load="$$get('/feed')">
            <div id="feed"></div>
        </div>
        </div>
        <hr />

    </main>
</body>
</html>
"""

def datastream(stream) -> StreamingResponse:
    """Create a StreamingResponse for Server-Sent Events (SSE)."""
    return StreamingResponse(
        stream,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        media_type="text/event-stream",
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the root HTML page."""
    return HTMLResponse(html)

@app.get('/get')
async def get_data(request: Request):
    store = json.loads(dict(request.query_params)['datastar'])
    store['output'] = f"Your input: {store['input']}, is {len(store['input'])} long."
    fragment = f'<main id="main" data-store=\'{json.dumps(store)}\'></main>'
    sse = DatastarEvent(
        fragment=fragment,
        merge=MergeType.UPSERT_ATTRIBUTES,
    )
    return datastream(sse.event_generator())

@app.get('/target')
async def target_element():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    fragment = f"<div id='{single_target}'><b>{current_time}</b></div>"
    sse = DatastarEvent(fragment=fragment)
    return datastream(sse.event_generator())


@app.get('/multi-target')
async def multi_target():
    async def generate_events():
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        fragments = [
            f'<div id="{target_1}"><b>{current_time} - Target 1</b></div>',
            f'<div id="{target_2}"><b>{current_time} - Target 2</b></div>',
            f'<div id="{target_3}"><b>{current_time} - Target 3</b></div>'
        ]
        for fragment in fragments:
            sse = DatastarEvent(fragment=fragment)
            async for event in sse.event_generator():
                yield event
    return datastream(generate_events())

@app.get('/update-store')
async def update_store():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    store = {'update_store': f'Update `data-store` only: {current_time}'}
    signal = DatastarSignal(store)
    return datastream(signal.event_generator())


@app.get('/toggle')
async def toggle_feed():
    global send
    send = not send
    signal = DatastarSignal({'send': send})
    return datastream(signal.event_generator())

@app.get('/feed')
async def feed():
    async def fragment_generator():
        global i
        i += 1
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        fragment = {
            "fragment": f'<div id="feed">{i} - {current_time}</div>',
            "merge": MergeType.PREPEND,
            "query_selector": "#feeds",
            "use_view_transitions": False,
        }
        return fragment

    streamer = DataStarStreamer(condition_callable=lambda: send, interval=1)
    return datastream(streamer.stream(fragment_generator))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run( app, host="127.0.0.1", port=8000)
