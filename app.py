import streamlit as st
import requests
import sqlite3
import json
from datetime import datetime

# Load OpenRouter API key
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# Initialize DB
conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT CHECK(role IN ('user', 'assistant')),
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
""")
conn.commit()

# Improved DeepSeek API Call with error handling
def ask_deepseek(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ecoding.streamlit.app",  # Required by OpenRouter
        "X-Title": "DeepSeek Chat App"  # Recommended
    }
    data = {
        "model": "deepseek/deepseek-coder",
        "messages": messages
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",  # Actual API endpoint
            headers=headers,
            json=data,
            timeout=30  # 30-second timeout
        )
        
        # Handle rate limits/errors
        if response.status_code == 429:
            st.error("API rate limit reached. Please try again later.")
            return "I'm currently rate-limited. Try again in a moment."
        elif response.status_code == 402:
            st.error("API quota exceeded. Upgrade your OpenRouter plan.")
            return "Daily limit reached. See OpenRouter.ai to upgrade."
        response.raise_for_status()  # Raises other HTTP errors
        
        return response.json()["choices"][0]["message"]["content"]
        
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}")
        return "Sorry, I couldn't get a response. Please try again."

# Streamlit App
st.set_page_config(page_title="DeepSeek Chat", layout="wide")

# Sidebar for Login
with st.sidebar:
    st.title("🔐 Login")
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    
    if st.session_state.user_id is None:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            cursor.execute("SELECT id FROM users WHERE username = ? AND password = ?", 
                          (username, password))
            user = cursor.fetchone()
            if user:
                st.session_state.user_id = user[0]
                st.rerun()
            else:
                st.error("Invalid credentials.")
    else:
        st.success(f"Logged in as user {st.session_state.user_id}")
        if st.button("Logout"):
            st.session_state.user_id = None
            st.rerun()

# Main Chat UI
if st.session_state.user_id:
    st.title("💬 DeepSeek Coder Chat")
    
    # Load chat history
    cursor.execute("""
        SELECT role, content FROM chats 
        WHERE user_id = ? 
        ORDER BY timestamp
    """, (st.session_state.user_id,))
    chats = cursor.fetchall()
    
    # Display messages
    for role, content in chats:
        with st.chat_message(role):
            st.markdown(content)
    
    # User input
    if prompt := st.chat_input("Ask DeepSeek Coder..."):
        # Save user message
        cursor.execute("""
            INSERT INTO chats (user_id, role, content) 
            VALUES (?, ?, ?)
        """, (st.session_state.user_id, "user", prompt))
        conn.commit()
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Prepare messages for API
        messages = [{"role": role, "content": content} 
                   for role, content in chats] + [{"role": "user", "content": prompt}]
        
        # Get AI response
        with st.spinner("Thinking..."):
            response = ask_deepseek(messages)
        
        # Save and display AI response
        cursor.execute("""
            INSERT INTO chats (user_id, role, content) 
            VALUES (?, ?, ?)
        """, (st.session_state.user_id, "assistant", response))
        conn.commit()
        
        with st.chat_message("assistant"):
            st.markdown(response)
else:
    st.warning("Please log in to chat.")

conn.close()