import streamlit as st
import pandas as pd
import numpy as np
from pymongo import MongoClient
import plotly.express as px

# ==============================
# MONGO CONNECTION
# ==============================
MONGO_URI = "mongodb+srv://Garvit:bababro89@store.bihf6uw.mongodb.net/?appName=store"
DB_NAME = "retail_app"
COLLECTION_NAME = "sales"

# Connect to MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
except Exception as e:
    st.error(f"❌ MongoDB connection failed: {e}")
    st.stop()

# ==============================
# DATA GENERATION (if empty)
# ==============================
if collection.count_documents({}) == 0:
    np.random.seed(42)
    customers = [f"CUST_{i}" for i in range(1, 21)]
    items = ["Jeans", "Shoes", "T-Shirt", "Jacket", "Hat", "Watch"]
    data = []
    for i in range(20):
        data.append({
            "CustomerID": customers[i],
            "Name": f"Customer_{i+1}",
            "Item": np.random.choice(items),
            "Quantity": np.random.randint(1, 5),
            "Spent": np.random.randint(500, 5000),
            "Days": np.random.choice(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            "StoreLocation": np.random.choice(["Delhi", "Mumbai", "Bangalore", "Pune"])
        })
    collection.insert_many(data)

# ==============================
# FETCH DATA
# ==============================
data = list(collection.find({}, {"_id": 0}))
df = pd.DataFrame(data)
df["Total"] = df["Spent"] * df["Quantity"]

# ==============================
# STREAMLIT UI CONFIG
# ==============================
st.set_page_config(page_title="Retail Dashboard", layout="wide")

# Pastel gradient theme and rounded cards
st.markdown("""
    <style>
        body {
            background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
            font-family: 'Poppins', sans-serif;
            color: #333;
        }
        .stApp {
            background-color: transparent;
        }
        .main-title {
            text-align: center;
            font-size: 2.3rem;
            color: #4b5563;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }
        .sub-title {
            text-align: center;
            font-size: 1rem;
            color: #6b7280;
            margin-bottom: 2rem;
        }
        .card {
            background: #ffffffd9;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0px 3px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-4px);
        }
        .stButton>button {
            border-radius: 8px;
            background-color: #a5b4fc;
            color: white;
            border: none;
            font-weight: 500;
        }
        .stButton>button:hover {
            background-color: #818cf8;
        }
    </style>
""", unsafe_allow_html=True)

# ==============================
# SIDEBAR NAVIGATION
# ==============================
st.sidebar.title("🔍 Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Data", "Analysis"])

# ==============================
# HEADER
# ==============================
st.markdown('<h1 class="main-title">🏪 Retail Sales Dashboard</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Clean • Visual • Interactive</p>', unsafe_allow_html=True)

# ==============================
# PAGE 1: DASHBOARD
# ==============================
if page == "Dashboard":
    total_sales = df["Total"].sum()
    avg_spent = df["Spent"].mean()
    top_item = df.groupby("Item")["Total"].sum().idxmax()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='card'><h3>💰 Total Revenue</h3><h2>₹{total_sales:,.0f}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card'><h3>🧍 Avg Spend / Customer</h3><h2>₹{avg_spent:,.0f}</h2></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='card'><h3>🔥 Top Selling Item</h3><h2>{top_item}</h2></div>", unsafe_allow_html=True)

# ==============================
# PAGE 2: DATA (Admin editable)
# ==============================
elif page == "Data":
    st.subheader("📋 Manage Product Data")
    st.caption("Admin can edit rows but not columns")

    edited_df = st.data_editor(df, num_rows="dynamic", disabled=["CustomerID", "Name", "Item", "Days", "StoreLocation"])

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💾 Save Changes"):
            collection.delete_many({})
            collection.insert_many(edited_df.to_dict(orient="records"))
            st.success("✅ Data updated successfully!")
    with col2:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export as CSV", csv, "retail_data.csv", "text/csv")

# ==============================
# PAGE 3: ANALYSIS
# ==============================
elif page == "Analysis":
    st.subheader("📊 Data Analysis & Visualization")

    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.bar(df.groupby("Item", as_index=False).sum(), x="Item", y="Total", title="Total Sales by Product", color="Item")
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = px.pie(df, names="StoreLocation", values="Total", title="Revenue by Store Location")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    fig3 = px.line(df.groupby("Days", as_index=False).sum(), x="Days", y="Total", title="Sales Trend by Day", markers=True)
    st.plotly_chart(fig3, use_container_width=True)
