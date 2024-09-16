import asyncio
import json
import time
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from datastar import DatastarEvent, DatastarStreamer, FragmentConfig, MergeType, create_sse_stream

store = {"input": "datastar", "output": "", "_show": False, "message": "", "send": "", "update_store": ""}

single_target = 'single_target'
target_1 = 'target_1'
target_2 = 'target_2'
target_3 = 'target_3'
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
    <script type="module" defer src="https://cdn.jsdelivr.net/npm/@sudodevnull/datastar"></script>
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

def datastream(stream: AsyncGenerator[str, None]) -> StreamingResponse:
    """Create a StreamingResponse for Server-Sent Events (SSE)."""
    return StreamingResponse(
        stream,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        media_type="text/event-stream",
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(html)

@app.get('/get')
async def get_data(request: Request):
    store = json.loads(dict(request.query_params)['datastar'])
    store['output'] = f"Your input: {store['input']}, is {len(store['input'])} long."
    fragment = f'<main id="main" data-store=\'{json.dumps(store)}\'></main>'
    event = DatastarEvent.create_fragment(content=fragment, merge=MergeType.UPSERT_ATTRIBUTES)
    return datastream(event.stream())

@app.get('/target')
async def target_element():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    fragment = FragmentConfig(fragment=f'<div id="single_target"><b>{current_time}</b></div>')
    event = DatastarEvent(content=fragment)
    return datastream(event.stream())

@app.get('/multi-target')
async def multi_target():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    fragments = [
        FragmentConfig(fragment=f'<div id="target_1"><b>{current_time} - Target 1</b></div>', merge=MergeType.INNER),
        FragmentConfig(fragment=f'<div id="target_2"><b>{current_time} - Target 2</b></div>', merge=MergeType.PREPEND, selector='#target_2'),
        f'<div id="target_3"><b>{current_time} - Target 3</b></div>'
    ]
    event = DatastarEvent.create_fragment(content=fragments)
    return datastream(event.stream())

@app.get('/update-store')
async def update_store():
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    event = DatastarEvent.create_signal(data={'update_store': f'Update `data-store` only: {current_time}'})
    return datastream(event.stream())

@app.get('/toggle')
async def toggle_feed():
    global send
    send = not send
    event = DatastarEvent.create_signal(data={'send': send})
    return datastream(event.stream())

@app.get('/feed')
async def feed():
    global send, i

    async def data_generator() -> AsyncGenerator[FragmentConfig, None]:
        global i
        while True:
            if send:
                i += 1
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                yield FragmentConfig(
                    fragment=f'<div id="feed">{i} - {current_time}</div>',
                    merge=MergeType.PREPEND,
                    selector='#feeds',
                    use_view_transitions=False,
                )
            await asyncio.sleep(1)  # Control rate of fragment generation

    streamer = DatastarStreamer(condition_callable=lambda: send, interval=0.1)
    return datastream(streamer.stream(data_generator))

# Alternative implementation using create_sse_stream
@app.get('/feed_alt')
async def feed_alt():
    global send, i

    async def data_generator() -> AsyncGenerator[FragmentConfig, None]:
        global i
        while True:
            if send:
                i += 1
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                yield FragmentConfig(
                    fragment=f'<div id="feed">{i} - {current_time}</div>',
                    merge=MergeType.PREPEND,
                    selector='#feeds'
                )
            await asyncio.sleep(1)

    stream = create_sse_stream(
        data_generator=data_generator,
        merge=MergeType.PREPEND,
        selector='#feeds',
        use_view_transitions=False,
        interval=0.1
    )
    return datastream(stream)
