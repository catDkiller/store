import streamlit as st
import pandas as pd
import numpy as np
from pymongo import MongoClient
import plotly.express as px
import random

st.set_page_config(page_title="🛍️ Retail Sales Dashboard", layout="wide")

# Black background styling
st.markdown("""
<style>
.stApp {
    background-color: #000000;
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# MongoDB Connection
# ==============================
MONGO_URI = "mongodb+srv://Garvit:bababro89@store.bihf6uw.mongodb.net/?appName=store"
DB_NAME = "retail_app"
COLLECTION_NAME = "products"

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
  #    st.success("✅ Connected to MongoDB")
except Exception as e:
  #    st.error(f"❌ MongoDB connection failed: {e}")
  #    st.stop()

# ==============================
# Sample Data (if empty)
# ==============================
if collection.count_documents({}) == 0:
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
            "Available Stock": np.random.randint(10, 100),
            "Revenue": np.random.randint(20000, 200000),
            "Recommendation Score": np.random.uniform(50, 100)
        })
    collection.insert_many(products)
    st.info("🧾 20 sample product records added to MongoDB.")

# ==============================
# Load Data
# ==============================
data = list(collection.find({}, {"_id": 0}))
df = pd.DataFrame(data)

# ==============================
# Streamlit Page Config
# ==============================


# Soft Modern Theme
st.markdown("""
    <style>
        body {background-color: #F8FAFC;}
        .stApp {background-color: #FAFAFA;}
        .stButton>button {background-color: #A5B4FC; color: white; border-radius: 10px;}
        .stButton>button:hover {background-color: #818CF8;}
        div[data-testid="stMetricValue"] {color: #4F46E5;}
    </style>
""", unsafe_allow_html=True)

# ==============================
# Sidebar Filters
# ==============================
st.sidebar.header("🔍 Filter Options")

selected_category = st.sidebar.selectbox(
    "Select Category", options=["All"] + sorted(df["Category"].unique().tolist())
)

min_price, max_price = int(df["Price"].min()), int(df["Price"].max())
price_range = st.sidebar.slider("Price Range (₹)", min_price, max_price, (min_price, max_price))

rating_filter = st.sidebar.slider("Minimum Rating", 0.0, 5.0, 3.0, 0.1)

# Apply filters
filtered_df = df[
    ((df["Price"] >= price_range[0]) & (df["Price"] <= price_range[1])) &
    (df["Rating"] >= rating_filter)
]

if selected_category != "All":
    filtered_df = filtered_df[filtered_df["Category"] == selected_category]

# ==============================
# Search Bar + Recommendations
# ==============================
st.title("🛒 Retail Product Browser")

search_query = st.text_input("Search for products...", placeholder="Type product name...").strip().lower()

if search_query:
    results = filtered_df[filtered_df["Product_Name"].str.lower().str.contains(search_query)]
    if results.empty:
        st.warning("No products found for your search.")
    else:
        st.subheader(f"Results for '{search_query}':")
        for _, row in results.iterrows():
            with st.container():
                st.markdown(f"### 🏷️ {row['Product Name']}")
                st.write(f"💰 Price: ₹{row['Price']:.2f}")
                st.write(f"⭐ Rating: {row['Rating']:.1f}")
                st.write(f"📦 Sold: {row['Sales Volume']} units")
                if st.button(f"View More Details - {row['Product Name']}"):
                    st.info(f"""
                    **Available Stock:** {row['Available Stock']}  
                    **Revenue:** ₹{row['Revenue']:,}  
                    **Recommendation Score:** {row['Recommendation Score']:.1f}%
                    """)
        st.divider()

    # Show random recommendations
    st.subheader("💡 Recommended for You")
    recommended = df.sample(3)
    for _, rec in recommended.iterrows():
        st.markdown(f"**🛍️ {rec['Product Name']}** — ₹{rec['Price']:.0f} | ⭐ {rec['Rating']:.1f}")
else:
    st.subheader("Browse All Products")
    st.dataframe(filtered_df.drop(columns=["Category"]))

# ==============================
# Visualization
# ==============================
st.divider()
st.subheader("📊 Sales Analysis")

col1, col2 = st.columns(2)
with col1:
    fig = px.bar(df, x="Product_Name", y="Revenue", title="Revenue per Product", color="Category")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig2 = px.scatter(df, x="Rating", y="Sales_Volume",
                      size="Price", color="Category", title="Rating vs Sales Volume")
    st.plotly_chart(fig2, use_container_width=True)

# ==============================
# Export CSV
# ==============================
st.download_button(
    label="📥 Export Data as CSV",
    data=filtered_df.to_csv(index=False).encode('utf-8'),
    file_name="retail_products.csv",
    mime="text/csv"
)







