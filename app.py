import streamlit as st
from pymongo import MongoClient
import gridfs
import hashlib
import datetime
from dotenv import dotenv_values
from pymongo.errors import PyMongoError
import time

# Load environment variables
config = dotenv_values(".env")
CONN_STRING = config["CONN_STRING"]

# Page configuration
st.set_page_config(page_title="Distributed File Storage System", layout="wide")

# MongoDB connection
try:
    client = MongoClient(CONN_STRING)
    db = client["file_storage_app"]
    users_collection = db["users"]
    metadata_collection = db["metadata"]
    fs = gridfs.GridFS(db)
except PyMongoError as e:
    st.error("Failed to connect to the database. Please check your connection settings.")
    st.stop()

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ''


# Utility Functions
def hash_password(password):
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(name, email, password, demographics):
    """Creates a new user in the database."""
    try:
        users_collection.insert_one({
            "name": name,
            "email": email,
            "password": hash_password(password),
            "demographics": demographics
        })
    except PyMongoError as e:
        st.error("An error occurred while creating your account. Please try again.")


def fetch_user(email, password=None):
    """Fetches a user by email and optional password."""
    query = {"email": email}
    if password:
        query["password"] = hash_password(password)
    try:
        return users_collection.find_one(query)
    except PyMongoError as e:
        st.error("An error occurred while fetching user data.")
        return None


def handle_file_operations(action, data=None):
    """
    Handles CRUD operations for files and metadata.
    :param action: str - 'create', 'read', or 'delete'.
    :param data: dict - Data for the respective action.
    :return: Result of the operation.
    """
    try:
        if action == "create":
            # Insert file into GridFS and metadata
            file_id = fs.put(data['file_data'], filename=data['filename'], user_email=data['user_email'])
            metadata_collection.insert_one({
                "filename": data['filename'],
                "filetype": data['filetype'],
                "filesize": data['filesize'],
                "upload_time": data['upload_time'],
                "user_email": data['user_email'],
                "file_name_input": data['file_name_input']
            })
            return file_id
        elif action == "read":
            # Retrieve files and metadata
            return metadata_collection.find({"user_email": data['user_email']})
        elif action == "delete":
            # Delete file from GridFS and metadata
            fs.delete(data['file_id'])
            metadata_collection.delete_one({"_id": data['metadata_id']})
            return True
    except PyMongoError as e:
        st.error("An error occurred during file operations.")
        return None


# Sidebar Authentication Functions
def handle_login():
    """Handles user login."""
    st.sidebar.markdown("### Login")
    email = st.sidebar.text_input("Email", key="login_email")
    password = st.sidebar.text_input("Password", type="password", key="login_password")
    if st.sidebar.button("Login"):
        user = fetch_user(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.sidebar.success("Login successful")
            st.rerun()
        else:
            st.sidebar.warning("Incorrect email or password")


def handle_signup():
    """Handles user signup."""
    st.sidebar.markdown("### Signup")
    name = st.sidebar.text_input("Name")
    signup_email = st.sidebar.text_input("Email")
    signup_password = st.sidebar.text_input("Password", type="password")
    demographics = st.sidebar.text_input("Demographics")
    if st.sidebar.button("Signup"):
        if fetch_user(signup_email):
            st.warning("Email already exists")
        else:
            create_user(name, signup_email, signup_password, demographics)
            st.success("Signup successful, please log in using the sidebar.")


# Main Application Interface
def upload_files():
    """Handles file uploads."""
    st.header("Upload Files")
    st.info("Upload files to your personal storage. You can upload multiple files at once.")
    file_name_input = st.text_input("Enter File Name")
    uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True)

    if uploaded_files:
        if st.button("Upload"):
            for uploaded_file in uploaded_files:
                file_data = uploaded_file.read()
                file_info = {
                    "file_data": file_data,
                    "filename": uploaded_file.name,
                    "filetype": uploaded_file.type,
                    "filesize": len(file_data),
                    "upload_time": datetime.datetime.now(),
                    "user_email": st.session_state.user_email,
                    "file_name_input": file_name_input
                }
                handle_file_operations("create", file_info)
            st.success("Files uploaded successfully")


def view_files():
    """Displays user's files."""
    st.header("Your Files")
    st.info("View, download, or delete your uploaded files.")
    files = handle_file_operations("read", {"user_email": st.session_state.user_email})
    for file in files:
        col1, col2, col3 = st.columns([2, 1, 1])
        col1.write(file['filename'])
        grid_out = fs.find_one({"filename": file['filename'], "user_email": st.session_state.user_email})
        if grid_out:
            col2.download_button(
                label="Download",
                data=grid_out.read(),
                file_name=grid_out.filename,
                key=str(file['_id'])
            )
        if col3.button("Delete", key=str(file['_id']) + '_del'):
            handle_file_operations("delete", {"file_id": grid_out._id, "metadata_id": file['_id']})
            st.success(f"Deleted {file['filename']}")
            time.sleep(2)
            st.rerun()


def user_info():
    """Displays user information."""
    st.header("User Information")
    st.info("View your account details.")
    user = fetch_user(st.session_state.user_email)
    if user:
        st.write(f"**Name:** {user['name']}")
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Demographics:** {user['demographics']}")


# Main Application Execution
st.title("Distributed File Storage System")
if not st.session_state.logged_in:
    st.markdown("""
    Welcome to our Distributed File Storage System! This application provides a secure and reliable platform for storing and managing your personal or professional files.

    ## How It Works

    Our system utilizes the power of MongoDB's GridFS to store your files in a distributed and redundant manner. When you upload a file, it is securely stored across multiple nodes in the MongoDB cluster, ensuring data availability and protection against a single point of failure.

    ## Key Features

    - **File Upload**: Easily upload files of any type and size to your personal storage. You can upload multiple files at once.
    - **File Management**: View, download, and delete your uploaded files directly from the application interface.
    - **User Authentication**: Sign up for an account and log in to access your personal file storage. Your data is protected and accessible only to you.
    - **Metadata Tracking**: The system automatically tracks metadata such as filename, file type, file size, and upload timestamp for each of your files.
    - **Secure Storage**: Your files are stored in a distributed manner using MongoDB's GridFS, ensuring high availability and data integrity.

    ## Start Using the Platform

    To get started, simply sign up for an account or log in using the sidebar options. Once authenticated, you can begin uploading and managing your files.

    If you have any questions or need further assistance, please don't hesitate to reach out. We're here to help you make the most of our Distributed File Storage System.
    """)
    auth_option = st.sidebar.selectbox("Choose an option", ["Signup", "Login"])
    if auth_option == "Login":
        handle_login()
    elif auth_option == "Signup":
        handle_signup()
else:

    # st.sidebar.title("Distributed File Storage")
    st.sidebar.markdown("# __Distributed File Storage__")
    st.sidebar.success("Login Successful")
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = ''
        st.sidebar.success("Logged out")
        st.rerun()

    # Tabs for navigation
    tabs = st.tabs(["File Upload", "Files", "User Info"])
    with tabs[0]:
        upload_files()
    with tabs[1]:
        view_files()
    with tabs[2]:
        user_info()