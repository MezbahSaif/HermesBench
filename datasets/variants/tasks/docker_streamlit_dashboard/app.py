import streamlit as st
import pandas as pd
import numpy as np


st.title("Dashboard")

# Sidebar for filters and options
st.sidebar.header("Filters")
category = st.sidebar.selectbox("Category", ["Sales", "Marketing", "Operations"])

# Generate sample data
np.random.seed(42)
dates = pd.date_range(start="2024-01-01", periods=365, freq="D")
categories_data = {
    "Sales": {"Revenue": (100 + np.random.randn(365)*30).cumsum(), "Profit": 0.3 * (100 + np.random.randn(365)*30).cumsum()},
    "Marketing": {"Spending": 5000 + np.random.randn(365)*200, "Leads": (np.random.randint(50, 200, 365)).cumsum()}
}

if category == "Operations":
    categories_data["Operations"] = {
        "Tickets": (np.random.poisson(15, 365)).cumsum(),
        "Resolved": (np.random.randint(8, 20, 365)).cumsum()
    }

# Display metrics
st.metric("Total Value", f"{categories_data[category]['Revenue'][-1]:,.0f}")
st.metric("Growth Rate", f"{((categories_data[category]['Revenue'][-1] - categories_data[category]['Revenue'][0]) / categories_data[category]['Revenue'][0]):.2%}")

# Line chart
fig = st.line_chart(categories_data[category]["Revenue"][-365:])

# Bar chart for monthly breakdown
monthly = categories_data[category]["Revenue"].resample("ME").sum().tail(12)
st.bar_chart(monthly)
