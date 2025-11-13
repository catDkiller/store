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
mongo_uri = st.secrets["mongo"]["uri"]  # <--- from secrets.toml
db_name = "retail_app"
coll_users = "users"
coll_products = "products"
coll_orders = "orders"

try:
    client = MongoClient(mongo_uri)
    db = client[db_name]
    users_col = db[coll_users]
    products_col = db[coll_products]
    orders_col = db[coll_orders]
except Exception as e:
    st.error(f"❌ MongoDB connection failed: {e}")
    st.stop()

# ==============================
# STYLE
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
# FUNCTIONS
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

def add_sample_products():
    np.random.seed(42)
    categories = ["Clothing", "Shoes", "Accessories", "Electronics"]
    products = []
    for i in range(20):
        products.append({
            "Product_ID": i + 1,
            "Product_Name": f"Product_{i+1}",
            "Category": np.random.choice(categories),
            "Price": np.random.randint(300, 4000),
            "Rating": np.random.uniform(2.5, 5.0),
            "Sales_Volume": np.random.randint(50, 500),
            "Stock": np.random.randint(10, 100),
            "Revenue": np.random.randint(20000, 200000)
        })
    products_col.insert_many(products)

# ==============================
# LOGIN / SIGNUP
# ==============================
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []

if not st.session_state.user:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = verify_user(username, password)
            if user:
                st.session_state.user = {"username": user["username"], "role": user["role"]}
                st.success(f"Welcome {user['username']} ({user['role']})")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.subheader("Create Account")
        new_user = st.text_input("New Username")
        new_pw = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            if create_user(new_user, new_pw):
                st.success("Account created! Please log in.")
            else:
                st.error("Username already exists.")
    st.stop()

# ==============================
# LOGOUT HEADER
# ==============================
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🛍️ Retail Sales Dashboard")
with col2:
    if st.button("🚪 Logout"):
        st.session_state.user = None
        st.session_state.cart = []
        st.rerun()

role = st.session_state.user["role"]

# ==============================
# LOAD DATA
# ==============================
if products_col.count_documents({}) == 0:
    add_sample_products()

data = list(products_col.find({}, {"_id": 0}))
df = pd.DataFrame(data)

# ==============================
# ADMIN PANEL
# ==============================
if role == "admin":
    st.subheader("⚙️ Admin Panel - Manage Products")
    edited = st.data_editor(df, num_rows="dynamic")
    if st.button("💾 Save Changes"):
        products_col.delete_many({})
        products_col.insert_many(edited.to_dict(orient="records"))
        st.success("✅ Database updated successfully.")
    st.divider()

    st.subheader("📦 Purchased Orders")
    orders = list(orders_col.find({}, {"_id": 0}))
    if len(orders) > 0:
        st.dataframe(pd.DataFrame(orders))
    else:
        st.info("No purchases yet.")
    st.stop()

# ==============================
# USER PANEL
# ==============================
st.sidebar.header("🔍 Filters")
cat = st.sidebar.selectbox("Category", ["All"] + sorted(df["Category"].unique().tolist()))
price = st.sidebar.slider("Price (₹)", int(df["Price"].min()), int(df["Price"].max()), (1000, 3000))
rating = st.sidebar.slider("Min Rating", 0.0, 5.0, 3.0, 0.1)

filtered = df[(df["Price"].between(price[0], price[1])) & (df["Rating"] >= rating)]
if cat != "All":
    filtered = filtered[filtered["Category"] == cat]

st.subheader("🛒 Product Catalog")

for _, row in filtered.iterrows():
    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    with col1:
        st.write(f"**{row['Product_Name']}** ({row['Category']})")
        st.write(f"💰 ₹{row['Price']} | ⭐ {round(row['Rating'],1)}")
    with col2:
        st.write(f"Stock: {row['Stock']}")
    with col3:
        qty = sum(1 for item in st.session_state.cart if item["Product_Name"] == row["Product_Name"])
        st.write(f"In Cart: {qty}")
    with col4:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕", key=f"add_{row['Product_Name']}"):
                st.session_state.cart.append(row.to_dict())
        with c2:
            if st.button("➖", key=f"remove_{row['Product_Name']}"):
                for i, item in enumerate(st.session_state.cart):
                    if item["Product_Name"] == row["Product_Name"]:
                        del st.session_state.cart[i]
                        break

st.divider()

# ==============================
# CART SECTION
# ==============================
st.subheader("🧺 Your Cart")
if len(st.session_state.cart) == 0:
    st.info("Cart is empty.")
else:
    cart_df = pd.DataFrame(st.session_state.cart)
    cart_df["Total"] = cart_df["Price"]
    st.dataframe(cart_df[["Product_Name", "Category", "Price", "Total"]])
    total = cart_df["Price"].sum()
    st.markdown(f"### 💳 Total Amount: ₹{total}")
    if st.button("🛍️ Final Purchase"):
        orders_col.insert_one({
            "username": st.session_state.user["username"],
            "cart_items": cart_df.to_dict(orient="records"),
            "total": float(total)
        })
        st.session_state.cart = []
        st.success("✅ Purchase successful! Your order is now with admin.")

st.divider()
st.subheader("📊 Visualization")

col1, col2 = st.columns(2)
with col1:
    fig = px.bar(df, x="Product_Name", y="Revenue", color="Category", title="Revenue per Product")
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig2 = px.scatter(df, x="Rating", y="Sales_Volume", size="Price", color="Category",
                      title="Rating vs Sales Volume")
    st.plotly_chart(fig2, use_container_width=True)
