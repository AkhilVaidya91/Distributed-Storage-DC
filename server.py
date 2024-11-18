import socket
import json
from pymongo import MongoClient
import gridfs
import hashlib
import datetime
from dotenv import dotenv_values
from pymongo.errors import PyMongoError
import base64
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import heapq
from typing import Dict, List, Tuple
import time

# MongoDB Connection
CONN_STRING = "CONN_STRING"
HOST = 'localhost'
PORT = 65432

MAX_WORKERS = 4  # Number of worker threads
WORKER_QUEUE = queue.Queue()
active_connections: Dict[str, int] = {}  # Track active connections per worker
connection_locks = threading.Lock()

# Load environment variables
config = dotenv_values(".env")
if config:
    CONN_STRING = config.get("CONN_STRING")
    HOST = config.get("HOST")
    PORT = int(config.get("PORT"))

try:
    client = MongoClient(CONN_STRING)
    db = client["file_storage_app"]
    users_collection = db["users"]
    metadata_collection = db["metadata"]
    fs = gridfs.GridFS(db)
except PyMongoError as e:
    print(f"Database connection error: {e}")
    exit(1)


class LoadBalancer:
    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self.workers: List[Tuple[int, int]] = [(0, i) for i in range(num_workers)]  # (load, worker_id)
        self.lock = threading.Lock()

    def get_worker(self) -> int:
        with self.lock:
            load, worker_id = heapq.heappop(self.workers)
            heapq.heappush(self.workers, (load + 1, worker_id))
            return worker_id

    def release_worker(self, worker_id: int):
        with self.lock:
            for i, (load, wid) in enumerate(self.workers):
                if wid == worker_id:
                    self.workers[i] = (max(0, load - 1), wid)
                    heapq.heapify(self.workers)
                    break

class WorkerThread:
    def __init__(self, worker_id: int, load_balancer: LoadBalancer):
        self.worker_id = worker_id
        self.load_balancer = load_balancer

    def handle_client(self, conn, addr):
        try:
            while True:
                data = conn.recv(1024*1024)
                if not data:
                    break

                request = json.loads(data.decode())
                response = None

                if request['type'] == 'auth':
                    response = handle_auth(request['action'], request['data'])
                elif request['type'] == 'file':
                    response = handle_file_operations(request['action'], request['data'])

                conn.sendall(json.dumps(response).encode())

        except Exception as e:
            print(f"Worker {self.worker_id} error handling client {addr}: {e}")
        finally:
            with connection_locks:
                active_connections[str(self.worker_id)] -= 1
            self.load_balancer.release_worker(self.worker_id)
            conn.close()

def hash_password(password):
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def handle_auth(action, data):
    """Handle authentication operations"""
    try:
        print(f"Handling auth action: {action}")
        if action == "login":
            print(f"Attempting login for email: {data['email']}")
            user = users_collection.find_one({
                "email": data['email'],
                "password": hash_password(data['password'])
            })
            print(f"Found user: {user}")
            
            if user:
                # Convert ObjectId to string before sending
                user['_id'] = str(user['_id'])
                return {"status": "success", "user": user}
            return {"status": "error", "message": "Invalid credentials"}
        
        elif action == "signup":
            if users_collection.find_one({"email": data['email']}):
                return {"status": "error", "message": "Email already exists"}
            
            users_collection.insert_one({
                "name": data['name'],
                "email": data['email'],
                "password": hash_password(data['password']),
                "demographics": data['demographics']
            })
            return {"status": "success", "message": "User created successfully"}
        
        elif action == "get_user":
            user = users_collection.find_one({"email": data['email']})
            if user:
                # Convert ObjectId to string before sending
                user['_id'] = str(user['_id'])
                return {"status": "success", "user": user}
            return {"status": "error", "message": "User not found"}
            
    except PyMongoError as e:
        return {"status": "error", "message": str(e)}

def handle_file_operations(action, data):
    """Handle file operations"""
    try:
        if action == "upload":
            # Decode base64 file data
            file_data = base64.b64decode(data['file_data'])
            file_id = fs.put(
                file_data,
                filename=data['filename'],
                user_email=data['user_email']
            )
            
            metadata_collection.insert_one({
                "filename": data['filename'],
                "filetype": data['filetype'],
                "filesize": len(file_data),
                "upload_time": datetime.datetime.now(),
                "user_email": data['user_email'],
                "file_name_input": data['file_name_input']
            })
            return {"status": "success", "message": "File uploaded successfully"}

        elif action == "list":
            files = list(metadata_collection.find({"user_email": data['user_email']}))
            # Convert ObjectId to string for JSON serialization
            for file in files:
                file['_id'] = str(file['_id'])
                file['upload_time'] = str(file['upload_time'])
            return {"status": "success", "files": files}

        elif action == "download":
            grid_out = fs.find_one({"filename": data['filename'], "user_email": data['user_email']})
            if grid_out:
                file_data = base64.b64encode(grid_out.read()).decode('utf-8')
                return {"status": "success", "file_data": file_data, "filename": grid_out.filename}
            return {"status": "error", "message": "File not found"}

        elif action == "delete":
            fs.delete(data['file_id'])
            metadata_collection.delete_one({"_id": data['metadata_id']})
            return {"status": "success", "message": "File deleted successfully"}

    except PyMongoError as e:
        return {"status": "error", "message": str(e)}

def start_server():
    """Start the socket server with load balancing"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server listening on {HOST}:{PORT}")

    # Initialize load balancer and worker pools
    load_balancer = LoadBalancer(MAX_WORKERS)
    thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    # Initialize active connections counter for each worker
    for i in range(MAX_WORKERS):
        active_connections[str(i)] = 0

    while True:
        try:
            conn, addr = server.accept()
            print(f"New connection from {addr}")

            # Get the least loaded worker
            worker_id = load_balancer.get_worker()
            
            # Update active connections count
            with connection_locks:
                active_connections[str(worker_id)] += 1
            
            # Create worker and handle client
            worker = WorkerThread(worker_id, load_balancer)
            thread_pool.submit(worker.handle_client, conn, addr)

            # Log current load distribution
            print(f"Current connection distribution: {active_connections}")

        except Exception as e:
            print(f"Error accepting connection: {e}")
            continue

if __name__ == "__main__":
    start_server()
