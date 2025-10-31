import asyncio
import websockets
import json
import os
from datetime import datetime

# Configuration
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 800
PORT = '8080'
HOST = ''

class CollaborativeCanvas:
    def __init__(self):
        self.connections = {}
        self.cursors = {}
        # Stocke tous les traits dessinés (pour les nouveaux joueurs)
        self.strokes = []
        
    def add_player(self, player_id, websocket):
        """Ajoute un nouveau joueur"""
        self.connections[player_id] = {
            'ws': websocket,
            'name': f'Player {len(self.connections) + 1}',
            'color': '#000000'
        }
        print(f"Joueur connecté: {player_id} - Total: {len(self.connections)}")
    
    def remove_player(self, player_id):
        """Retire un joueur"""
        if player_id in self.connections:
            del self.connections[player_id]
        if player_id in self.cursors:
            del self.cursors[player_id]
        print(f"Joueur déconnecté: {player_id} - Total: {len(self.connections)}")
    
    def add_stroke(self, stroke_data):
        """Ajoute un trait au canvas"""
        self.strokes.append(stroke_data)
        # Limite l'historique à 10000 traits pour éviter une croissance infinie
        if len(self.strokes) > 10000:
            self.strokes.pop(0)
    
    def update_cursor(self, player_id, x, y):
        """Met à jour la position du curseur d'un joueur"""
        self.cursors[player_id] = {'x': x, 'y': y}
    
    async def broadcast(self, message, exclude_id=None):
        """Envoie un message à tous les clients sauf exclude_id"""
        if not self.connections:
            return
        
        tasks = []
        for player_id, player in self.connections.items():
            if player_id != exclude_id:
                tasks.append(player['ws'].send(message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_player(self, player_id, message):
        """Envoie un message à un joueur spécifique"""
        if player_id in self.connections:
            try:
                await self.connections[player_id]['ws'].send(message)
            except:
                pass

# Instance du canvas
canvas = CollaborativeCanvas()

async def handler(websocket):
    """Gère les connexions WebSocket"""
    player_id = str(id(websocket))
    
    try:
        # Enregistre le joueur
        canvas.add_player(player_id, websocket)
        
        # Envoie l'ID au joueur
        await websocket.send(json.dumps({
            'type': 'connected',
            'playerId': player_id,
            'canvasWidth': CANVAS_WIDTH,
            'canvasHeight': CANVAS_HEIGHT
        }))
        
        # Envoie l'historique des traits au nouveau joueur
        await websocket.send(json.dumps({
            'type': 'history',
            'strokes': canvas.strokes
        }))
        
        # Notifie les autres joueurs
        await canvas.broadcast(json.dumps({
            'type': 'player_joined',
            'playerId': player_id,
            'playerCount': len(canvas.connections)
        }), exclude_id=player_id)
        
        # Boucle de réception des messages
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data['type'] == 'draw':
                    # Un joueur dessine
                    stroke_data = {
                        'playerId': player_id,
                        'points': data['points'],
                        'color': data['color'],
                        'size': data['size']
                    }
                    canvas.add_stroke(stroke_data)
                    
                    # Broadcast aux autres joueurs
                    await canvas.broadcast(json.dumps({
                        'type': 'draw',
                        'stroke': stroke_data
                    }), exclude_id=player_id)
                
                elif data['type'] == 'cursor':
                    # Mise à jour de la position du curseur
                    canvas.update_cursor(player_id, data['x'], data['y'])
                    
                    # Broadcast aux autres joueurs
                    await canvas.broadcast(json.dumps({
                        'type': 'cursor',
                        'playerId': player_id,
                        'x': data['x'],
                        'y': data['y']
                    }), exclude_id=player_id)
                
                elif data['type'] == 'clear':
                    # Efface le canvas (nécessite confirmation)
                    canvas.strokes = []
                    
                    # Broadcast à tous
                    await canvas.broadcast(json.dumps({
                        'type': 'clear'
                    }))
            
            except json.JSONDecodeError:
                print(f"Message JSON invalide reçu de {player_id}")
            except Exception as e:
                print(f"Erreur lors du traitement du message: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"Erreur dans le handler: {e}")
    finally:
        # Déconnexion du joueur
        canvas.remove_player(player_id)
        
        # Notifie les autres joueurs
        await canvas.broadcast(json.dumps({
            'type': 'player_left',
            'playerId': player_id,
            'playerCount': len(canvas.connections)
        }))

async def main():
    """Démarre le serveur"""
    print("=" * 50)
    print("Serveur Toile Collaborative démarré")
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print(f"Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT}")
    print("=" * 50)
    
    # Démarre le serveur WebSocket
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServeur arrêté")
