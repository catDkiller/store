import streamlit as st
import pandas as pd
import numpy as np
from pymongo import MongoClient
import plotly.express as px
import hashlib

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(page_title="🛍️ Retail Sales Dashboard", layout="wide")

# ==============================
# MONGO CONNECTION
# ==============================
MONGO_URI = "mongodb+srv://Garvit:bababro89@store.bihf6uw.mongodb.net/?appName=store"
DB_NAME = "retail_app"
COLL_USERS = "users"
COLL_PRODUCTS = "products"

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    users_col = db[COLL_USERS]
    products_col = db[COLL_PRODUCTS]
except Exception as e:
    st.error(f"❌ MongoDB connection failed: {e}")
    st.stop()

# ==============================
# STYLING
# ==============================
st.markdown("""
<style>
.stApp {background-color: #000; color: #FFF;}
[data-testid="stSidebar"] {background-color: #1a1a1a;}
.stButton>button {background-color: #4F46E5; color: white; border-radius: 10px;}
.stButton>button:hover {background-color: #6366F1;}
</style>
""", unsafe_allow_html=True)

# ==============================
# HELPER FUNCTIONS
# ==============================
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    user = users_col.find_one({"username": username})
    if user and user["password"] == hash_pw(password):
        return user
    return None

def create_user(username, password, role="user"):
    if users_col.find_one({"username": username}):
        return False
    users_col.insert_one({"username": username, "password": hash_pw(password), "role": role})
    return True

# ==============================
# AUTHENTICATION
# ==============================
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

    with tab1:
        st.subheader("Login to Retail Dashboard")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = verify_user(username, password)
            if user:
                st.session_state.user = {"username": user["username"], "role": user["role"]}
                st.success(f"✅ Welcome {user['username']} ({user['role']})")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    with tab2:
        st.subheader("Create a New Account")
        new_user = st.text_input("New Username")
        new_pw = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            if create_user(new_user, new_pw):
                st.success("✅ Account created!
