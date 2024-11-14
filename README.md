# Distributed File Storage System

This repository contains the code for a simple Distributed File Storage System with a user-friendly Streamlit frontend. This system enables users to upload, download, and delete files, and provides a dashboard to view all their stored files. Socket communication is used to facilitate interaction between the Streamlit frontend and the server backend, which handles file storage and management.

## Features

- **User Dashboard**: A user-friendly Streamlit dashboard for easy file management.
- **File Upload, Download, Delete**: Users can upload, download, and delete their files with simple interface options.
- **File Storage in MongoDB**: Files are stored in a MongoDB database along with metadata, ensuring structured and accessible storage.

## System Architecture

The system has two main components:

1. **Frontend (Streamlit Client - `app.py`)**
   - Built with Streamlit to provide a simple, intuitive interface.
   - Displays a dashboard where users can view all their uploaded files.
   - Sends requests to the server to perform file operations (upload, download, delete) via socket communication.

2. **Backend (Server - `server.py`)**
   - Handles file operations and metadata management.
   - Stores files in MongoDB and organizes metadata under user collections.
   - Manages socket communication with the client to receive and process requests.

### Installation

1. Clone this repository:

2. Install required packages:

    ```bash
    pip install -r requirements.txt
    ```

3. Configure MongoDB connection settings in `server.py`.

### Running the Application

1. **Start the Server**:

    ```bash
    python server.py
    ```

2. **Run the Streamlit Client**:

    ```bash
    streamlit run app.py
    ```

3. Access the Streamlit app in your browser

## Usage

- **Uploading Files**: Select a file from your system and click "Upload". The file will be sent to the server, stored in MongoDB, and metadata will be updated.
- **Downloading Files**: Choose a file from the dashboard and click "Download" to retrieve it.
- **Deleting Files**: Select a file to delete, and the server will remove it from the storage.