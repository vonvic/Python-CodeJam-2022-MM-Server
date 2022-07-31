from dataclasses import dataclass, field
from typing import List

from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="static")
# app.mount("/static", StaticFiles(directory="static"), name="static")

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://localhost:8000/ws/${client_id}`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                console.log(messages)
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    """Connects, disconnects, can send individual messages to a socket, or broaddcasts messages."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.rooms: List[Room] = []

    async def connect(self, websocket: WebSocket):
        """Adds `websocket` to all active connections."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes `websocket` from all active connections."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Sends `message` to `websocket`."""
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        """Broadcasts message to all active connections."""
        for connection in self.active_connections:
            await connection.send_text(message)

    async def locate_room(self, room_id: str):
        """Returns the room with id `room_id`."""
        for i in self.rooms:
            if room_id == i.room_id:
                return i

        return None


@dataclass
class Room:
    """Room to connect, disconnect, and broadcast messages to users."""

    name: str
    room_id: str
    people: List[WebSocket] = field(default_factory=list)
    owner: WebSocket = None

    async def connect(self, websocket: WebSocket):
        """Adds `websocket` to list of people."""
        await websocket.accept()
        self.people.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes `websocket` from list of people."""
        self.people.remove(websocket)

    async def broadcast(self, message: str):
        """Sends a message to all users."""
        for connection in self.people:
            await connection.send_text(message)


manager = ConnectionManager()


@app.get("/")
async def get(request: Request):
    """Todo (Firestar)"""
    data = {"num": "not connected"}
    return templates.TemplateResponse("index.html", {"request": request, "data": data})


@app.websocket("/ws/{room_id}/{client_id}/{joining}")
async def make_room(websocket: WebSocket, room_id: str, client_id: int, joining: bool):
    """Creates a room."""
    find = await manager.locate_room(room_id=room_id)
    if not find:
        if joining:
            await manager.connect(websocket)
            await manager.send_personal_message("not found", websocket)
            return

        else:
            for i in manager.rooms:
                if websocket in i.people:
                    print("removing", i.name)
                    if len(i.people) > 1:
                        i.disconnect(websocket)

                    else:
                        manager.rooms.remove(i)

            room = Room(name=str(client_id) + "'s room", room_id=room_id)
            room.owner = websocket
            manager.rooms.append(room)
            await room.connect(websocket)
            await room.broadcast(f"{client_id} has joined #{room_id}")
            find = room

    elif websocket not in find.people:
        for i in manager.rooms:
            if websocket in i.people:
                print("removing", i.name)
                if len(i.people) > 1:
                    i.disconnect(websocket)

                else:
                    manager.rooms.remove(i)
        if joining:
            await manager.connect(websocket)
            await manager.send_personal_message("found", websocket)
            manager.disconnect(websocket)

        else:
            await find.connect(websocket)
            await find.broadcast(f"{client_id} has joined #{find.room_id}")

    try:
        while True:
            data = await websocket.receive_text()
            await find.broadcast(f"{client_id}: {data}")

    except Exception:
        find.disconnect(websocket)
        await find.broadcast(f"{client_id} has left the room")

        if len(find.people) == 0:
            manager.rooms.remove(find)
