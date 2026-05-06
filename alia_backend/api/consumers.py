import json
from channels.generic.websocket import AsyncWebsocketConsumer


class SimConsumer(AsyncWebsocketConsumer):
    """
    WebSocket ws://localhost:8000/ws/sim/<user_id>/
    Relaie les états avatar (speaking/listening/idle) en temps réel.
    """

    async def connect(self):
        self.user_id  = self.scope['url_route']['kwargs']['user_id']
        self.group    = f'sim_{self.user_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Messages entrants du client (non utilisés pour l'instant)."""
        pass

    async def avatar_state(self, event):
        """Reçu depuis agent.py via channel_layer.group_send."""
        await self.send(text_data=json.dumps(event['data']))
