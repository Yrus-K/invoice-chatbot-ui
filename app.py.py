import streamlit as st
import requests
import re
from datetime import datetime
import google.generativeai as genai

# ---------------------------------------------------
# 🔹 Streamlit Page Setup
# ---------------------------------------------------
st.set_page_config(page_title="Invoice Chatbot", page_icon="💬")
st.title("💬 Invoice Chatbot")
st.markdown("A smart assistant for your accounts payable and receivable queries.")

# ---------------------------------------------------
# 🔹 Configure Gemini API
# ---------------------------------------------------
# ⚠️ WARNING: Never commit API keys directly to your repository!
genai.configure(api_key="AIzaSyDx_TGoWiG6qx-rikSbGmatF8SFuNgufcw")  # Replace with your actual key
model = genai.GenerativeModel("gemini-1.5-flash")

def query_gemini(user_input):
    """Send a query to the Gemini model and return a lowercase text response."""
    try:
        response = model.generate_content(user_input)
        return response.text.strip().lower()
    except Exception as e:
        st.error(f"Error querying Gemini: {e}")
        return ""

# ---------------------------------------------------
# 🔹 Helper Functions for API and Data
# ---------------------------------------------------
def get_all_invoices():
    """Fetch all pending invoices from the mock backend API."""
    try:
        response = requests.get("http://127.0.0.1:8000/pending")
        if response.status_code == 200:
            return response.json().get("pending_invoices", [])
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching invoices from API: {e}")
        return []

def get_invoice_by_id(invoice_id):
    """Fetch a single invoice by its ID."""
    try:
        response = requests.get(f"http://127.0.0.1:8000/invoice/{invoice_id}")
        if response.status_code == 200:
            return response.json()
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

def display_invoice_card(data):
    """Display a single invoice's details in a clean card format."""
    status_icon = {
        "approved": "✅",
        "pending": "⏳",
        "rejected": "❌"
    }.get(data["status"].lower(), "📄")

    st.markdown(f"### {status_icon} Invoice Details: {data['invoice_id']}")
    st.markdown(f"""
    - **Status:** `{data['status'].title()}`
    - **Approver:** `{data['approver']}`
    - **Type:** `{data['type'].title()}`
    - **Vendor:** `{data.get('vendor', 'N/A')}`
    - **Customer:** `{data.get('customer', 'N/A')}`
    - **Amount:** `Rs. {data['amount']}`
    - **Last Updated:** `{data['last_updated']}`
    """)
    st.markdown("---")


# ---------------------------------------------------
# 🔹 Main Chatbot Logic
# ---------------------------------------------------
user_input = st.text_input("Ask a question about invoices:", key="chat_input")
st.info("Examples: 'What is the status of INV1002?', 'Show me all pending invoices', 'Which invoices are from vendor: Acme Corp?', 'Which invoices have an amount > 5000?'")

if user_input:
    # Query Gemini to interpret the user's intent
    with st.spinner("Processing your request..."):
        gemini_result = query_gemini(user_input)

    # Fetch all invoices for general queries
    invoices = get_all_invoices()

    # --- Intent-based routing using regex on Gemini's output ---

    # 1. Specific Invoice Field Query (e.g., "field:vendor invoice:INV1001")
    field_match = re.search(r'field:(\w+)\s+invoice:(inv\d+)', gemini_result)
    if field_match:
        field = field_match.group(1).lower()
        invoice_id = field_match.group(2).upper()
        invoice_data = get_invoice_by_id(invoice_id)
        if invoice_data:
            if field in invoice_data:
                st.success(f"The **{field.title()}** for invoice **{invoice_id}** is: `{invoice_data[field]}`")
            else:
                st.warning(f"Field '{field}' not found for invoice {invoice_id}.")
        else:
            st.error(f"Invoice **{invoice_id}** not found.")

    # 2. General Invoice Details Query (e.g., "inv1002")
    elif re.search(r'\binv\d+\b', gemini_result):
        invoice_id = re.search(r'\binv\d+\b', gemini_result).group(0).upper()
        invoice_data = get_invoice_by_id(invoice_id)
        if invoice_data:
            display_invoice_card(invoice_data)
        else:
            st.error(f"Invoice **{invoice_id}** not found.")

    # 3. Status Queries (e.g., "pending", "approved")
    elif any(status in gemini_result for status in ["pending", "approved", "rejected"]):
        status_query = next((s for s in ["pending", "approved", "rejected"] if s in gemini_result), None)
        if invoices:
            filtered = [inv for inv in invoices if inv["status"].lower() == status_query]
            st.info(f"✅ Found **{len(filtered)}** {status_query.title()} invoices.")
            if filtered:
                for inv in filtered:
                    st.markdown(f"- **{inv['invoice_id']}** | Status: `{inv['status']}` | Amount: `Rs. {inv['amount']}`")
        else:
            st.warning("Could not retrieve invoice data.")

    # 4. Amount Threshold Query (e.g., "amount > 10000")
    elif "amount >" in gemini_result:
        match = re.search(r'amount\s*>\s*(\d+)', gemini_result)
        if invoices and match:
            threshold = int(match.group(1))
            filtered = [inv for inv in invoices if inv["amount"] > threshold]
            st.info(f"💰 Found **{len(filtered)}** invoices with amounts greater than `Rs. {threshold}`.")
            for inv in filtered:
                st.markdown(f"- **{inv['invoice_id']}** | Amount: `Rs. {inv['amount']}` | Status: `{inv['status']}`")

    # 5. Vendor or Customer Query
    elif "vendor:" in gemini_result or "customer:" in gemini_result:
        key = "vendor" if "vendor:" in gemini_result else "customer"
        name = gemini_result.split(":")[1].strip()
        filtered = [inv for inv in invoices if inv.get(key, "").lower() == name.lower()]
        st.info(f"🔍 Found **{len(filtered)}** invoices for **{key.title()} '{name}'**.")
        for inv in filtered:
            st.markdown(f"- **{inv['invoice_id']}** | Amount: `Rs. {inv['amount']}` | Status: `{inv['status']}`")

    # 6. Fallback/Unrecognized Intent
    else:
        st.warning("🤔 I'm sorry, I couldn't understand that query. Please try rephrasing.")