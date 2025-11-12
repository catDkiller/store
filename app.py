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
        st.error("MongoDB connection failed. Check secrets.toml.")
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
# User functions (stored in Mongo)
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
# Local DataFrame creation (primary in-memory dataset)
# ---------------------------
@st.cache_data
def create_local_df():
    np.random.seed(42)
    categories = ['Electronics', 'Clothing', 'Food', 'Home & Garden', 'Sports', 'Books', 'Toys']
    products = ['Product_' + str(i) for i in range(1, 31)]
    data = {
        'Product_ID': products,
        'Product_Name': [f"{np.random.choice(categories)} Item {i}" for i in range(1, 31)],
        'Category': np.random.choice(categories, 30),
        'Price': np.round(np.random.uniform(10, 500, 30), 2),
        'Rating': np.round(np.random.uniform(3.0, 5.0, 30), 1),
        'Sales_Volume': np.random.randint(10, 1000, 30),
        'Stock': np.random.randint(0, 200, 30),
        'Discount': np.random.choice([0, 5, 10, 15, 20], 30)
    }
    df = pd.DataFrame(data)
    df['Revenue'] = np.round(df['Price'] * df['Sales_Volume'] * (1 - df['Discount'] / 100), 2)
    df['Recommendation_Score'] = np.round(
        (df['Rating'] * 0.4) +
        (df['Sales_Volume'] / df['Sales_Volume'].max() * 5 * 0.3) +
        (df['Discount'] / 25 * 5 * 0.3), 2
    )
    return df

# ---------------------------
# Mongo <-> Local sync functions
# ---------------------------
def load_products_from_mongo():
    coll, _ = get_db_collections()
    if coll is not None:
        docs = list(coll.find({}, {"_id": 0}))
        if len(docs) > 0:
            return pd.DataFrame(docs)
    return pd.DataFrame()  # empty DF if none

def push_local_to_mongo(df):
    coll, _ = get_db_collections()
    if coll is not None:
        coll.delete_many({})
        if not df.empty:
            coll.insert_many(df.to_dict("records"))
        return True
    return False

def upsert_product_to_mongo(product_dict):
    coll, _ = get_db_collections()
    if coll is not None:
        # Use Product_ID as identifier
        coll.update_one({"Product_ID": product_dict["Product_ID"]}, {"$set": product_dict}, upsert=True)
        return True
    return False

def delete_product_from_mongo(product_id):
    coll, _ = get_db_collections()
    if coll is not None:
        res = coll.delete_one({"Product_ID": product_id})
        return res.deleted_count > 0
    return False

# ---------------------------
# UI: Login / Register
# ---------------------------
def show_login_register():
    st.title("🛒 Retail Sales Dashboard")
    st.markdown("Sign in to access the dashboard — admins can manage products; users can view & filter.")


    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                else:
                    st.warning("Enter username and password")

    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Choose username", key="reg_user")
            full_name = st.text_input("Full name", key="reg_name")
            new_password = st.text_input("Password", type="password", key="reg_pass")
            confirm = st.text_input("Confirm password", type="password", key="reg_conf")
            reg_submit = st.form_submit_button("Register")
            if reg_submit:
                if not (new_username and new_password and full_name and confirm):
                    st.warning("Fill all fields")
                elif new_password != confirm:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be 6+ chars")
                else:
                    ok, msg = register_user(new_username, new_password, full_name)
                    if ok:
                        st.success("Registered. Login now.")
                    else:
                        st.error(msg)

# ---------------------------
# Dashboard / Product Analysis
# ---------------------------
def show_main_app():
    user = st.session_state.user
    st.sidebar.write(f"👤 **{user['full_name']}**")
    st.sidebar.write(f"Role: **{user['role'].upper()}**")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    # Load data into session_state (local-first, then Mongo)
    if 'df' not in st.session_state:
        # prefer Mongo if available
        mongo_df = load_products_from_mongo()
        if not mongo_df.empty:
            st.session_state.df = mongo_df
        else:
            st.session_state.df = create_local_df()
            # push sample to mongo so users can see the data if desired
            push_local_to_mongo(st.session_state.df)

    df = st.session_state.df.copy()

    # Navigation
    if user['role'] == 'admin':
        page = st.sidebar.radio("Go to", ["Dashboard", "Products", "Manage Products", "Sync"])
    else:
        page = st.sidebar.radio("Go to", ["Dashboard", "Products"])

    if page == "Dashboard":
        show_dashboard_page(df)
    elif page == "Products":
        show_products_page(df)
    elif page == "Manage Products":
        show_manage_products(df)
    elif page == "Sync":
        show_sync_page(df)

# ---------------------------
# Dashboard view
# ---------------------------
def show_dashboard_page(df):
    st.header("📊 Sales Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Products", len(df))
    col2.metric("Total Revenue", f"${df['Revenue'].sum():,.2f}")
    col3.metric("Avg Rating", f"{df['Rating'].mean():.2f}⭐")
    col4.metric("Total Sales", f"{df['Sales_Volume'].sum():,}")

    st.subheader("Revenue by Category")
    cat_rev = df.groupby('Category')['Revenue'].sum().sort_values(ascending=False).reset_index()
    fig = px.bar(cat_rev, x='Category', y='Revenue', title="Revenue by Category")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top products by revenue")
    st.dataframe(df.nlargest(10, 'Revenue')[['Product_ID','Product_Name','Category','Price','Sales_Volume','Revenue','Rating']], use_container_width=True)

# ---------------------------
# Products view (for users)
# ---------------------------
def show_products_page(df):
    st.header("🛍️ Browse Products")
    # Filters
    with st.expander("Filters", expanded=True):
        cols = st.columns(4)
        name_filter = cols[0].text_input("Search name")
        cat_options = ['All'] + sorted(list(df['Category'].unique()))
        selected_cat = cols[1].selectbox("Category", cat_options)
        price_min, price_max = cols[2].slider("Price range", float(df['Price'].min()), float(df['Price'].max()), (float(df['Price'].min()), float(df['Price'].max())))
        min_rating = cols[3].slider("Min rating", 0.0, 5.0, 3.0, 0.1)

    filtered = df.copy()
    if name_filter:
        filtered = filtered[filtered['Product_Name'].str.contains(name_filter, case=False, na=False)]
    if selected_cat != 'All':
        filtered = filtered[filtered['Category'] == selected_cat]
    filtered = filtered[(filtered['Price'] >= price_min) & (filtered['Price'] <= price_max)]
    filtered = filtered[filtered['Rating'] >= min_rating]

    st.write(f"Showing **{len(filtered)}** products")
    st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

# ---------------------------
# Admin: Manage Products (rows only)
# ---------------------------
def show_manage_products(df):
    st.header("🔧 Manage Products (Admin)")
    st.write("You can add, edit, or delete product **rows**. Column structure is fixed.")

    tab1, tab2, tab3 = st.tabs(["Add Product", "Edit Product", "Delete Product"])

    # ----- Add -----
    with tab1:
        st.subheader("➕ Add new product")
        with st.form("add_form"):
            cols = st.columns(2)
            name = cols[0].text_input("Product Name")
            category = cols[1].text_input("Category")
            price = cols[0].number_input("Price ($)", min_value=0.0, step=0.01)
            rating = cols[1].slider("Rating", 0.0, 5.0, 4.0, 0.1)
            sales = cols[0].number_input("Sales Volume", min_value=0, step=1, value=10)
            stock = cols[1].number_input("Stock", min_value=0, step=1, value=10)
            discount = cols[0].selectbox("Discount (%)", [0,5,10,15,20])
            submitted = st.form_submit_button("Add product")
            if submitted:
                if not name or not category:
                    st.error("Name and category are required")
                else:
                    current_ids = [int(pid.split("_")[1]) for pid in df['Product_ID'] if isinstance(pid, str) and "_" in pid]
                    next_id = max(current_ids) + 1 if current_ids else 1
                    new_id = f"Product_{next_id}"
                    new_row = {
                        "Product_ID": new_id,
                        "Product_Name": name,
                        "Category": category,
                        "Price": float(price),
                        "Rating": float(rating),
                        "Sales_Volume": int(sales),
                        "Stock": int(stock),
                        "Discount": int(discount)
                    }
                    new_row["Revenue"] = round(new_row["Price"] * new_row["Sales_Volume"] * (1 - new_row["Discount"]/100), 2)
                    # recommendation score same formula
                    new_row["Recommendation_Score"] = round(
                        (new_row["Rating"] * 0.4) +
                        (new_row["Sales_Volume"] / df['Sales_Volume'].max() * 5 * 0.3) +
                        (new_row["Discount"] / 25 * 5 * 0.3), 2
                    )
                    # update session df and mongo
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                    upsert_product_to_mongo(new_row)
                    st.success("Product added")
                    st.rerun()

    # ----- Edit -----
    with tab2:
        st.subheader("✏️ Edit existing product (row values only)")
        product_list = df['Product_Name'].tolist()
        selected = st.selectbox("Choose product to edit", [""] + product_list)
        if selected:
            product_row = df[df['Product_Name'] == selected].iloc[0]
            with st.form("edit_form"):
                cols = st.columns(2)
                # show product id and do not allow change of column names or Product_ID
                st.text_input("Product ID (read-only)", value=product_row['Product_ID'], disabled=True)
                name = cols[0].text_input("Product Name", value=product_row['Product_Name'])
                category = cols[1].text_input("Category", value=product_row['Category'])
                price = cols[0].number_input("Price ($)", value=float(product_row['Price']), step=0.01)
                rating = cols[1].slider("Rating", 0.0, 5.0, float(product_row['Rating']), 0.1)
                sales = cols[0].number_input("Sales Volume", value=int(product_row['Sales_Volume']), step=1)
                stock = cols[1].number_input("Stock", value=int(product_row['Stock']), step=1)
                discount = cols[0].selectbox("Discount (%)", [0,5,10,15,20], index=[0,5,10,15,20].index(int(product_row['Discount'])))
                update = st.form_submit_button("Update product")
                if update:
                    pid = product_row['Product_ID']
                    new_revenue = round(price * sales * (1 - discount/100), 2)
                    new_rec = round(
                        (rating * 0.4) +
                        (sales / df['Sales_Volume'].max() * 5 * 0.3) +
                        (discount / 25 * 5 * 0.3), 2
                    )
                    # update session df
                    st.session_state.df.loc[st.session_state.df['Product_ID'] == pid, [
                        'Product_Name','Category','Price','Rating','Sales_Volume','Stock','Discount','Revenue','Recommendation_Score'
                    ]] = [name, category, float(price), float(rating), int(sales), int(stock), int(discount), float(new_revenue), float(new_rec)]
                    # update mongo
                    upsert_product_to_mongo({
                        "Product_ID": pid,
                        "Product_Name": name,
                        "Category": category,
                        "Price": float(price),
                        "Rating": float(rating),
                        "Sales_Volume": int(sales),
                        "Stock": int(stock),
                        "Discount": int(discount),
                        "Revenue": float(new_revenue),
                        "Recommendation_Score": float(new_rec)
                    })
                    st.success("Product updated")
                    st.rerun()

    # ----- Delete -----
    with tab3:
        st.subheader("🗑️ Delete a product")
        sel_delete = st.selectbox("Select product to delete", [""] + df['Product_Name'].tolist(), key="del_select")
        if sel_delete:
            row = df[df['Product_Name'] == sel_delete].iloc[0]
            st.write(f"**{row['Product_Name']}** — {row['Category']} — ${row['Price']:.2f}")
            if st.button("Confirm delete"):
                pid = row['Product_ID']
                # update session df and mongo
                st.session_state.df = st.session_state.df[st.session_state.df['Product_ID'] != pid].reset_index(drop=True)
                deleted = delete_product_from_mongo(pid)
                if deleted:
                    st.success("Deleted from Mongo and local")
                else:
                    # even if mongo delete failed, keep local change
                    st.warning("Deleted locally — Mongo delete may have failed")
                st.rerun()

# ---------------------------
# Admin: Sync page
# ---------------------------
def show_sync_page(df):
    st.header("🔁 Sync Local <-> Mongo")
    st.write("Use these options to control dataset synchronization. The app keeps an in-memory (local) DataFrame in session; use these to push/pull to/from MongoDB.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Pull from Mongo (overwrite local)"):
            mongo_df = load_products_from_mongo()
            if not mongo_df.empty:
                st.session_state.df = mongo_df
                st.success("Pulled from Mongo into local session")
                st.rerun()
            else:
                st.warning("Mongo collection empty")
    with col2:
        if st.button("Push local to Mongo (overwrite collection)"):
            ok = push_local_to_mongo(st.session_state.df)
            if ok:
                st.success("Local pushed to Mongo")
            else:
                st.error("Push failed")

# ---------------------------
# Entry point
# ---------------------------
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None

    if not st.session_state.logged_in:
        show_login_register()
    else:
        show_main_app()

if __name__ == "__main__":
    main()





