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
# MONGO CONNECTION (from secrets.toml)
# ==============================
mongo_uri = "mongodb+srv://Garvit:bababro89@store.bihf6uw.mongodb.net/?appName=store"
db_name = "retail_app"
coll_users = "users"
coll_products = "products"

try:
    client = MongoClient(mongo_uri)
    db = client[db_name]
    users_col = db[coll_users]
    products_col = db[coll_products]
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
                st.success("✅ Account created! Please log in.")
            else:
                st.error("⚠️ Username already exists.")
    st.stop()

# ==============================
# LOGOUT + HEADER
# ==============================
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🛍️ Retail Sales Dashboard")
with col2:
    if st.button("🚪 Logout"):
        st.session_state.user = None
        st.rerun()

role = st.session_state.user["role"]

# ==============================
# SAMPLE DATA (if empty)
# ==============================
if products_col.count_documents({}) == 0:
    np.random.seed(42)
    categories = ["Clothing", "Shoes", "Accessories", "Electronics"]
    products = []
    for i in range(20):
        products.append({
            "Product_Name": f"Product_{i+1}",
            "Category": np.random.choice(categories),
            "Price": np.random.randint(300, 4000),
            "Rating": np.random.uniform(2.5, 5.0),
            "Sales_Volume": np.random.randint(50, 500),
            "Stock": np.random.randint(10, 100),
            "Revenue": np.random.randint(20000, 200000),
            "Recommendation_Score": np.random.uniform(50, 100)
        })
    products_col.insert_many(products)
    st.info("🧾 20 sample product records added to MongoDB.")

# ==============================
# LOAD DATA
# ==============================
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

# ==============================
# USER DASHBOARD
# ==============================
st.sidebar.header("🔍 Filters")
cat = st.sidebar.selectbox("Category", ["All"] + sorted(df["Category"].unique().tolist()))
price = st.sidebar.slider("Price (₹)", int(df["Price"].min()), int(df["Price"].max()), (1000, 3000))
rating = st.sidebar.slider("Min Rating", 0.0, 5.0, 3.0, 0.1)

filtered = df[
    (df["Price"].between(price[0], price[1])) &
    (df["Rating"] >= rating)
]
if cat != "All":
    filtered = filtered[filtered["Category"] == cat]

st.subheader("📋 Product Catalog")
st.dataframe(filtered)

st.download_button(
    "📥 Download CSV",
    data=filtered.to_csv(index=False).encode('utf-8'),
    file_name="retail_data.csv",
    mime="text/csv"
)

st.divider()
st.subheader("📊 Visualization")

col1, col2 = st.columns(2)
with col1:
    fig = px.bar(df, x="Product_Name", y="Revenue", color="Category", title="Revenue per Product")
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig2 = px.scatter(df, x="Rating", y="Sales_Volume", size="Price", color="Category", title="Rating vs Sales Volume")
    st.plotly_chart(fig2, use_container_width=True)

