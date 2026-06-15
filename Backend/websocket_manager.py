"""
WebSocket Manager for real-time attendance updates and live dashboard synchronization.
Handles bi-directional communication between frontend and backend.
"""
from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio
from datetime import datetime


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Dictionary to store active connections
        # Structure: {user_id: [WebSocket, WebSocket, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "type": "client"
        }
        
        print(f"[WS] Connected for user_id={user_id}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket"""
        if websocket in self.connection_metadata:
            user_id = self.connection_metadata[websocket]["user_id"]
            
            if user_id in self.active_connections:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            del self.connection_metadata[websocket]
            print(f"[WS] Disconnected for user_id={user_id}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to user_id={user_id}: {e}")
                    disconnected.append(connection)
        
        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast_to_user(self, user_id: int, message: dict):
        """Broadcast a message to all connections of a specific user"""
        if user_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to user_id={user_id}: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast_to_role(self, role: str, message: dict):
        """Broadcast a message to all users with a specific role"""
        # This would typically require a role lookup from the database
        # For now, we broadcast to all connected users
        await self.broadcast(message)
    
    async def send_attendance_update(self, user_id: int, attendance_data: dict):
        """Send real-time attendance update to user's connections"""
        message = {
            "type": "attendance_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": attendance_data
        }
        await self.broadcast_to_user(user_id, message)
        
        # Also broadcast to all admins (in real scenario, check role)
        admin_message = {
            "type": "employee_status_update",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data": attendance_data
        }
        await self.broadcast(admin_message)
    
    async def send_prediction_update(self, user_id: int, prediction_data: dict):
        """Send ML prediction updates"""
        message = {
            "type": "prediction_update",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data": prediction_data
        }
        await self.broadcast(message)
    
    async def send_alert(self, user_id: int, alert_data: dict):
        """Send real-time alerts"""
        message = {
            "type": "alert",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data": alert_data
        }
        await self.broadcast(message)
    
    async def send_chat_message(self, user_id: int, message_data: dict):
        """Send chat message updates"""
        message = {
            "type": "chat_message",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data": message_data
        }
        await self.broadcast_to_user(user_id, message)
    
    def get_active_users_count(self) -> int:
        """Get count of active connections"""
        return len(self.active_connections)
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        return {
            "active_users": self.get_active_users_count(),
            "total_connections": total_connections,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global connection manager instance
manager = ConnectionManager()
