import streamlit as st
import requests
import sqlite3
import os

# Load OpenRouter API key
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# Initialize DB
conn = sqlite3.connect("chat.db")
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

# DeepSeek API Call
def ask_deepseek(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek/deepseek-coder",  # Use DeepSeek Coder
        "messages": messages
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=data
    )
    return response.json()["choices"][0]["message"]["content"]

# Streamlit App
st.set_page_config(page_title="DeepSeek Chat", layout="wide")

# Sidebar for Login/Signup
with st.sidebar:
    st.title("🔐 Auth")
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    
    # Login
    if st.session_state.user_id is None:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                cursor.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
                user = cursor.fetchone()
                if user:
                    st.session_state.user_id = user[0]
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        
        with tab2:
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            if st.button("Create Account"):
                try:
                    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (new_user, new_pass))
                    conn.commit()
                    st.success("Account created! Log in now.")
                except sqlite3.IntegrityError:
                    st.error("Username taken.")
    else:
        st.success(f"Logged in as user {st.session_state.user_id}")
        if st.button("Logout"):
            st.session_state.user_id = None
            st.rerun()

# Main Chat UI
if st.session_state.user_id:
    st.title("💬 DeepSeek Coder Chat")
    
    # Load chat history
    cursor.execute("SELECT role, content FROM chats WHERE user_id = ? ORDER BY timestamp", (st.session_state.user_id,))
    chats = cursor.fetchall()
    
    # Display messages
    for role, content in chats:
        with st.chat_message(role):
            st.markdown(content)
    
    # User input
    if prompt := st.chat_input("Ask DeepSeek Coder..."):
        # Save user message
        cursor.execute("INSERT INTO chats (user_id, role, content) VALUES (?, ?, ?)", 
                       (st.session_state.user_id, "user", prompt))
        conn.commit()
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Prepare messages for API (include history)
        messages = [{"role": role, "content": content} for role, content in chats] + [{"role": "user", "content": prompt}]
        
        # Get AI response
        with st.spinner("Thinking..."):
            response = ask_deepseek(messages)
        
        # Save and display AI response
        cursor.execute("INSERT INTO chats (user_id, role, content) VALUES (?, ?, ?)", 
                       (st.session_state.user_id, "assistant", response))
        conn.commit()
        
        with st.chat_message("assistant"):
            st.markdown(response)
else:
    st.warning("Please log in to chat.")

conn.close()