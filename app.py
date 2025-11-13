import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
from pymongo import MongoClient
import plotly.express as px

# ---------------------------
# Config / Page setup
# ---------------------------
st.set_page_config(page_title="Retail Sales Dashboard", page_icon="🛒", layout="wide")

# ---------------------------
# Mongo connection
# ---------------------------
@st.cache_resource
def init_connection():
    try:
        conn_str = st.secrets["mongo"]["connection_string"]
        client = MongoClient(conn_str)
        return client
    except Exception as e:
        st.error("MongoDB connection failed. Check secrets.toml.")
        return None

def get_db_collections():
    client = init_connection()
    if client:
        db_name = st.secrets["mongo"]["database"]
        db = client[db_name]
        return (
            db[st.secrets["mongo"]["collection"]],
            db[st.secrets["mongo"]["users_collection"]],
            db["purchases"],
        )
    return None, None, None

# ---------------------------
# Helpers
# ---------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_data
def create_sample_data():
    np.random.seed(42)
    categories = ["Electronics", "Clothing", "Books", "Home", "Toys"]
    data = {
        "Product_ID": [f"P{i}" for i in range(1, 21)],
        "Product_Name": [f"{np.random.choice(categories)} Item {i}" for i in range(1, 21)],
        "Category": np.random.choice(categories, 20),
        "Price": np.round(np.random.uniform(10, 500, 20), 2),
        "Rating": np.round(np.random.uniform(3.0, 5.0, 20), 1),
        "Stock": np.random.randint(0, 50, 20),
        "Discount": np.random.choice([0, 5, 10, 15, 20], 20),
        "Sales_Volume": np.random.randint(10, 1000, 20),
    }
    df = pd.DataFrame(data)
    df["Revenue"] = (df["Price"] * df["Sales_Volume"] * (1 - df["Discount"] / 100)).round(2)
    return df

# ---------------------------
# DB functions
# ---------------------------
def register_user(username, password, full_name, role="user"):
    _, users_coll, _ = get_db_collections()
    if users_coll.find_one({"username": username}):
        return False, "Username already exists"
    users_coll.insert_one({
        "username": username,
        "password": hash_password(password),
        "role": role,
        "full_name": full_name,
        "created_at": datetime.now(),
    })
    return True, "Registered successfully"

def authenticate_user(username, password):
    _, users_coll, _ = get_db_collections()
    user = users_coll.find_one({"username": username, "password": hash_password(password)})
    return user

def load_products():
    coll, _, _ = get_db_collections()
    return pd.DataFrame(list(coll.find({}, {"_id": 0}))) if coll.count_documents({}) > 0 else pd.DataFrame()

def save_products(df):
    coll, _, _ = get_db_collections()
    coll.delete_many({})
    coll.insert_many(df.to_dict("records"))

def record_purchase(username, product):
    _, _, purchases = get_db_collections()
    purchase = {
        "username": username,
        "Product_ID": product["Product_ID"],
        "Product_Name": product["Product_Name"],
        "Price": product["Price"],
        "Quantity": 1,
        "Purchase_Date": datetime.now(),
    }
    purchases.insert_one(purchase)

def get_all_purchases():
    _, _, purchases = get_db_collections()
    return pd.DataFrame(list(purchases.find({}, {"_id": 0})))

# ---------------------------
# Login & Registration
# ---------------------------
def login_register():
    st.title("🛒 Retail App Login")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            if submit:
                user = authenticate_user(u, p)
                if user:
                    st.session_state.user = user
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    
    with tab2:
        with st.form("register"):
            name = st.text_input("Full Name")
            u = st.text_input("New Username")
            p = st.text_input("Password", type="password")
            c = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Register"):
                if p != c:
                    st.error("Passwords do not match.")
                elif len(p) < 6:
                    st.warning("Password must be 6+ characters.")
                else:
                    ok, msg = register_user(u, p, name)
                    st.success(msg) if ok else st.error(msg)

# ---------------------------
# Dashboard (with visualizations)
# ---------------------------
def dashboard(df):
    st.header("📊 Sales Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Products", len(df))
    col2.metric("Total Revenue", f"${df['Revenue'].sum():,.2f}")
    col3.metric("Avg Rating", f"{df['Rating'].mean():.2f}⭐")
    col4.metric("Total Sales", f"{df['Sales_Volume'].sum():,}")
    
    st.subheader("Revenue by Category")
    fig = px.bar(df.groupby("Category")["Revenue"].sum().reset_index(), x="Category", y="Revenue",
                 color="Category", title="Revenue Distribution by Category")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# User View
# ---------------------------
def user_view(df):
    st.header("🛍️ Browse Products")
    with st.expander("Filters", expanded=True):
        col1, col2 = st.columns(2)
        cat = col1.selectbox("Category", ["All"] + sorted(df["Category"].unique().tolist()))
        min_rating = col2.slider("Minimum Rating", 0.0, 5.0, 3.0, 0.1)
        if cat != "All":
            df = df[df["Category"] == cat]
        df = df[df["Rating"] >= min_rating]

    st.write(f"Showing {len(df)} products")
    st.dataframe(df, use_container_width=True)

    for _, row in df.iterrows():
        if row["Stock"] > 0:
            if st.button(f"Buy {row['Product_Name']} - ${row['Price']}", key=row["Product_ID"]):
                record_purchase(st.session_state.user["username"], row)
                st.success(f"Purchased {row['Product_Name']} successfully!")

# ---------------------------
# Admin Panel
# ---------------------------
def admin_panel(df):
    st.header("👨‍💼 Admin Panel")
    subtab1, subtab2 = st.tabs(["Products", "User Purchases"])
    
    with subtab1:
        st.dataframe(df, use_container_width=True)
        if st.button("Export Products to CSV"):
            df.to_csv("products.csv", index=False)
            st.success("Exported as products.csv")
    
    with subtab2:
        purchases = get_all_purchases()
        if not purchases.empty:
            st.dataframe(purchases, use_container_width=True)
        else:
            st.info("No purchases yet.")

# ---------------------------
# Main app
# ---------------------------
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None

    if not st.session_state.logged_in:
        login_register()
        return

    user = st.session_state.user
    st.sidebar.success(f"Welcome, {user['full_name']} ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    mongo_df = load_products()
    df = mongo_df if not mongo_df.empty else create_sample_data()
    if mongo_df.empty:
        save_products(df)

    choice = st.sidebar.radio("Navigate", ["Dashboard", "Shop"] if user["role"] == "user" else ["Dashboard", "Admin"])

    if choice == "Dashboard":
        dashboard(df)
    elif choice == "Shop" and user["role"] == "user":
        user_view(df)
    elif choice == "Admin" and user["role"] == "admin":
        admin_panel(df)

if __name__ == "__main__":
    main()
