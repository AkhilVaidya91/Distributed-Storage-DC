import socket
import json
from pymongo import MongoClient
import gridfs
import hashlib
import datetime
from dotenv import dotenv_values
from pymongo.errors import PyMongoError
import base64

# MongoDB Connection
CONN_STRING = "CONN_STRING"
HOST = 'localhost'
PORT = 65432

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
    """Start the socket server"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        print(f"Connected by {addr}")
        
        try:
            while True:
                data = conn.recv(1024*1024)  # Increased buffer size for file transfers
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
            print(f"Error handling client: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    start_server()
