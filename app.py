import streamlit as st
import socket
import json
import base64
import time
from streamlit_option_menu import option_menu

# Socket Configuration
HOST = 'localhost'
PORT = 65432

# Page configuration
st.set_page_config(
    page_title="Distributed File Storage System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 2rem;
        background-color: #f0f2f6;
        border-radius: 0.5rem;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e0e2e6;
    }
    .css-1y4p8pa {
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .stButton button {
        width: 100%;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
    }
    .upload-section {
        padding: 2rem;
        border: 2px dashed #ccc;
        border-radius: 1rem;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ''

def send_request(request_type, action, data):
    """Send request to server and receive response"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            request = {
                "type": request_type,
                "action": action,
                "data": data
            }
            s.sendall(json.dumps(request).encode())
            response = s.recv(1024*1024)  # Increased buffer size for file transfers
            return json.loads(response.decode())
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return {"status": "error", "message": "Server connection failed"}

def handle_login():
    """Handle user login"""
    with st.form("login_form"):
        st.markdown("### Welcome Back! 👋")
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            response = send_request("auth", "login", {
                "email": email,
                "password": password
            })
            
            if response["status"] == "success":
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.success("Login successful!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Invalid email or password")

def handle_signup():
    """Handle user signup"""
    with st.form("signup_form"):
        st.markdown("### Create New Account 📝")
        name = st.text_input("Full Name", placeholder="Enter your full name")
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Create a strong password")
        demographics = st.text_input("Demographics", placeholder="Enter your demographics")
        submit = st.form_submit_button("Sign Up", use_container_width=True)
        
        if submit:
            response = send_request("auth", "signup", {
                "name": name,
                "email": email,
                "password": password,
                "demographics": demographics
            })
            
            if response["status"] == "success":
                st.success("Account created successfully! Please login.")
            else:
                st.error(response["message"])

def upload_files():
    """Handle file uploads"""
    st.markdown("### Upload Files 📤")
    with st.container():
        st.markdown("""
        <div class="upload-section">
            <h4>Drop your files here</h4>
            <p>Supported formats: All file types</p>
        </div>
        """, unsafe_allow_html=True)
        
        file_name_input = st.text_input("Custom File Name (optional)", placeholder="Enter a custom name for your file")
        uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)
        
        if uploaded_files:
            if st.button("Upload Files", use_container_width=True):
                for uploaded_file in uploaded_files:
                    file_data = base64.b64encode(uploaded_file.read()).decode('utf-8')
                    response = send_request("file", "upload", {
                        "file_data": file_data,
                        "filename": uploaded_file.name,
                        "filetype": uploaded_file.type,
                        "user_email": st.session_state.user_email,
                        "file_name_input": file_name_input
                    })
                    
                    if response["status"] == "success":
                        st.success(f"Uploaded {uploaded_file.name} successfully!")
                    else:
                        st.error(f"Failed to upload {uploaded_file.name}")

def view_files():
    """Display user's files"""
    st.markdown("### Your Files 📁")
    
    response = send_request("file", "list", {"user_email": st.session_state.user_email})
    
    if response["status"] == "success":
        files = response["files"]
        if not files:
            st.info("No files uploaded yet")
            return
            
        for file in files:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                col1.markdown(f"**{file['filename']}**")
                col1.caption(f"Uploaded: {file['upload_time']}")
                
                # Download button
                if col2.button("📥 Download", key=f"down_{file['_id']}"):
                    download_response = send_request("file", "download", {
                        "filename": file['filename'],
                        "user_email": st.session_state.user_email
                    })
                    if download_response["status"] == "success":
                        file_data = base64.b64decode(download_response["file_data"])
                        col2.download_button(
                            label="Save File",
                            data=file_data,
                            file_name=download_response["filename"],
                            key=f"save_{file['_id']}"
                        )
                
                # Delete button
                if col3.button("🗑️ Delete", key=f"del_{file['_id']}"):
                    delete_response = send_request("file", "delete", {
                        "file_id": file['_id'],
                        "metadata_id": file['_id']
                    })
                    if delete_response["status"] == "success":
                        st.success("File deleted successfully")
                        time.sleep(1)
                        st.rerun()

def user_info():
    """Display user information"""
    response = send_request("auth", "get_user", {"email": st.session_state.user_email})
    
    if response["status"] == "success":
        user = response["user"]
        st.markdown("### Profile Information 👤")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("##### Personal Details")
            st.write(f"**Name:** {user['name']}")
            st.write(f"**Email:** {user['email']}")
            st.write(f"**Demographics:** {user['demographics']}")
        
        with col2:
            st.markdown("##### Storage Statistics")
            files_response = send_request("file", "list", {"user_email": st.session_state.user_email})
            if files_response["status"] == "success":
                files = files_response["files"]
                st.write(f"**Total Files:** {len(files)}")
                total_size = sum(file['filesize'] for file in files)
                st.write(f"**Total Storage Used:** {total_size/1024/1024:.2f} MB")

def main():
    """Main application"""
    st.title("🗄️ Distributed File Storage System")
    
    if not st.session_state.logged_in:
        col1, col2 = st.columns(2)
        
        with col1:
            handle_login()
        
        with col2:
            handle_signup()
            
        st.markdown("""
        ---
        ### Features ✨
        - **Secure Storage:** Your files are protected with enterprise-grade security
        - **Easy Access:** Upload and download files from anywhere
        - **File Management:** Organize and manage your files efficiently
        - **Multiple File Types:** Support for all file formats
        """)
    else:
        # Sidebar navigation
        with st.sidebar:
            st.markdown("### Welcome Back! 👋")
            selected = option_menu(
                menu_title=None,
                options=["Upload", "Files", "Profile", "Logout"],
                icons=["cloud-upload", "folder", "person", "box-arrow-right"],
                menu_icon="cast",
                default_index=0,
            )
            
            if selected == "Logout":
                st.session_state.logged_in = False
                st.session_state.user_email = ''
                st.success("Logged out successfully!")
                st.rerun()
        
        # Main content based on selection
        if selected == "Upload":
            upload_files()
        elif selected == "Files":
            view_files()
        elif selected == "Profile":
            user_info()

if __name__ == "__main__":
    main()
