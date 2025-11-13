# app.py
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
import plotly.express as px
from pymongo import MongoClient

# ---------------------------
# Config / Page setup
# ---------------------------
st.set_page_config(page_title="Retail Sales Dashboard", page_icon="🛒", layout="wide")

st.markdown(
    """
    <style>
    body {background-color:#f9fafb;}
    .stButton>button {border-radius:10px;background-color:#6c63ff;color:white;border:none;}
    .stButton>button:hover {background-color:#5548d9;}
    .block-container {padding-top:2rem;}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# Helpers: Mongo connection
# ---------------------------
@st.cache_resource
def init_connection():
    try:
        conn_str = st.secrets["mongo"]["connection_string"]
        client = MongoClient(conn_str)
        return client
    except Exception as e:
        st.error("❌ MongoDB connection failed. Check secrets.toml.")
        return None

def get_db_collections():
    client = init_connection()
    if client:
        db_name = st.secrets["mongo"]["database"]
        coll_name = st.secrets["mongo"]["collection"]
        users_coll = st.secrets["mongo"].get("users_collection", "users")
        db = client[db_name]
        return db[coll_name], db[users_coll]
    return None, None

# ---------------------------
# Simple password hashing
# ---------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------------------
# User functions (Mongo)
# ---------------------------
def register_user(username, password, full_name, role="user"):
    _, users_coll = get_db_collections()
    if users_coll is not None:
        if users_coll.find_one({"username": username}):
            return False, "Username already exists"
        users_coll.insert_one({
            "username": username,
            "password": hash_password(password),
            "role": role,
            "full_name": full_name,
            "created_at": datetime.now()
        })
        return True, "Registered"
    return False, "DB connection problem"

def authenticate_user(username, password):
    _, users_coll = get_db_collections()
    if users_coll is not None:
        user = users_coll.find_one({"username": username, "password": hash_password(password)})
        if user:
            return {"username": user["username"], "role": user["role"], "full_name": user.get("full_name", user["username"])}
    return None

# ---------------------------
# Local DataFrame creation (clean sample data)
# ---------------------------
@st.cache_data
def create_local_df():
    np.random.seed(42)
    categories = ['Electronics', 'Clothing', 'Food', 'Home', 'Sports', 'Books', 'Toys']
    names = [
        'Wireless Earbuds', 'Running Shoes', 'Smartphone', 'Laptop', 'T-Shirt', 'Novel', 'Yoga Mat',
        'Gaming Mouse', 'Smartwatch', 'Cookware Set', 'Bluetooth Speaker', 'Football', 'Desk Lamp',
        'Sunglasses', 'Backpack', 'Sneakers', 'Action Figure', 'Water Bottle', 'Headphones', 'Charger'
    ]
    df = pd.DataFrame({
        'Product_ID': [f"P{i:03d}" for i in range(1, 21)],
        'Product_Name': names,
        'Category': np.random.choice(categories, 20),
        'Price': np.round(np.random.uniform(15, 800, 20), 2),
        'Rating': np.round(np.random.uniform(3.0, 5.0, 20), 1),
        'Sales_Volume': np.random.randint(50, 1200, 20),
        'Stock': np.random.randint(10, 300, 20),
        'Discount': np.random.choice([0, 5, 10, 15, 20], 20)
    })
    # Clean & Transform
    df['Revenue'] = np.round(df['Price'] * df['Sales_Volume'] * (1 - df['Discount'] / 100), 2)
    df['Recommendation_Score'] = np.round(
        (df['Rating'] * 0.4)
        + (df['Sales_Volume'] / df['Sales_Volume'].max() * 5 * 0.3)
        + (df['Discount'] / 25 * 5 * 0.3),
        2
    )
    return df

# ---------------------------
# Mongo sync
# ---------------------------
def load_products_from_mongo():
    coll, _ = get_db_collections()
    if coll is not None:
        docs = list(coll.find({}, {"_id": 0}))
        if len(docs) > 0:
            return pd.DataFrame(docs)
    return pd.DataFrame()

def push_local_to_mongo(df):
    coll, _ = get_db_collections()
    if coll is not None:
        coll.delete_many({})
        if not df.empty:
            coll.insert_many(df.to_dict("records"))
        return True
    return False

# ---------------------------
# Dashboard Visualization
# ---------------------------
def show_dashboard(df):
    st.header("📊 Sales Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Products", len(df))
    col2.metric("Total Revenue", f"${df['Revenue'].sum():,.2f}")
    col3.metric("Avg Rating", f"{df['Rating'].mean():.2f}⭐")
    col4.metric("Total Sales", f"{df['Sales_Volume'].sum():,}")

    st.subheader("Revenue by Category")
    cat_rev = df.groupby('Category')['Revenue'].sum().sort_values(ascending=False).reset_index()
    fig = px.bar(cat_rev, x='Category', y='Revenue', color='Category',
                 color_discrete_sequence=px.colors.qualitative.Pastel,
                 title="Revenue by Category")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Discount vs Revenue")
    fig2 = px.scatter(df, x='Discount', y='Revenue', size='Sales_Volume',
                      color='Rating', color_continuous_scale='Viridis',
                      hover_data=['Product_Name'])
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Top 5 Products by Revenue")
    st.dataframe(df.nlargest(5, 'Revenue')[['Product_Name', 'Category', 'Price', 'Sales_Volume', 'Revenue']], use_container_width=True)

# ---------------------------
# Product view with export
# ---------------------------
def show_products(df):
    st.header("🛍️ Browse Products")
    with st.expander("Filters", expanded=True):
        c1, c2, c3 = st.columns(3)
        cat = c1.selectbox("Category", ['All'] + sorted(df['Category'].unique().tolist()))
        min_price, max_price = c2.slider("Price range", float(df['Price'].min()), float(df['Price'].max()),
                                         (float(df['Price'].min()), float(df['Price'].max())))
        min_rating = c3.slider("Minimum Rating", 0.0, 5.0, 3.5, 0.1)

    filtered = df.copy()
    if cat != "All":
        filtered = filtered[filtered["Category"] == cat]
    filtered = filtered[(filtered["Price"] >= min_price) & (filtered["Price"] <= max_price)]
    filtered = filtered[filtered["Rating"] >= min_rating]

    st.dataframe(filtered.reset_index(drop=True), use_container_width=True)
    st.download_button("⬇️ Export as CSV", data=filtered.to_csv(index=False), file_name="products_filtered.csv")

# ---------------------------
# Login Page
# ---------------------------
def show_login_page():
    st.title("🛒 Retail Sales App")
    st.markdown("### Sign in to access — Admins manage, Users explore.")

    login_tab, reg_tab = st.tabs(["Login", "Register"])
    with login_tab:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            sub = st.form_submit_button("Login")
            if sub:
                user = authenticate_user(u, p)
                if user:
                    st.session_state.user = user
                    st.session_state.logged_in = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with reg_tab:
        with st.form("register_form"):
            name = st.text_input("Full name")
            user = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["user", "admin"])
            btn = st.form_submit_button("Register")
            if btn:
                if not all([name, user, pwd]):
                    st.warning("Fill all fields")
                else:
                    ok, msg = register_user(user, pwd, name, role)
                    st.success(msg if ok else msg)

# ---------------------------
# Main App
# ---------------------------
def show_main_app():
    user = st.session_state.user
    st.sidebar.write(f"👤 {user['full_name']} ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    # Load or create data
    if "df" not in st.session_state:
        mongo_df = load_products_from_mongo()
        st.session_state.df = mongo_df if not mongo_df.empty else create_local_df()
        push_local_to_mongo(st.session_state.df)

    df = st.session_state.df

    if user["role"] == "admin":
        page = st.sidebar.radio("Go to", ["Dashboard", "Products", "Sync"])
    else:
        page = st.sidebar.radio("Go to", ["Dashboard", "Products"])

    if page == "Dashboard":
        show_dashboard(df)
    elif page == "Products":
        show_products(df)
    elif page == "Sync":
        if st.button("Push Local to MongoDB"):
            push_local_to_mongo(df)
            st.success("✅ Data pushed to Mongo successfully.")
        if st.button("Pull from MongoDB"):
            st.session_state.df = load_products_from_mongo()
            st.success("📥 Data pulled from Mongo.")

# ---------------------------
# Entry point
# ---------------------------
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
