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
        response = requests.get("https://fastapi-railway-test.onrender.com/pending")
        if response.status_code == 200:
            return response.json().get("pending_invoices", [])
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching invoices from API: {e}")
        return []

def get_invoice_by_id(invoice_id):
    """Fetch a single invoice by its ID."""
    try:
        response = requests.get(f"https://fastapi-railway-test.onrender.com/invoice/{invoice_id}")
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
st.info("Examples:\n\n"
        "- **Specific Invoice ID:** `What is the status of INV1002?` or `Show me details for INV1001.`\n"
        "- **Status:** `Show me all pending invoices.` or `Which invoices are approved?`\n"
        "- **Vendor/Customer:** `Show me invoices from vendor: Acme Corp.` or `Which invoices belong to customer: Global Tech?`\n"
        "- **Amount:** `Show invoices with amount > 5000.` or `List invoices with amount < 10000.` or `Which invoices are equal to 2500?`\n"
        "- **Date:** `Show invoices from last_updated: 2023-01-15.` or `List invoices before 2023-01-20.` or `Which invoices were updated after 2023-01-10?`")


if user_input:
    # Query Gemini to interpret the user's intent
    with st.spinner("Processing your request..."):
        # The prompt is now included here to guide Gemini's response format
        prompt = f"Analyze the user query and identify the invoice ID, status, amount, vendor, customer, or date. Respond with only a lowercase, single-line, structured output like 'invoice:inv1001', 'status:approved', 'vendor:acme corp', 'amount>5000', 'date>2023-01-15'. If you cannot find a specific match, respond with 'unrecognized'."
        gemini_result = query_gemini(f"{prompt} The user query is: '{user_input}'")

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

    # 3. Status Queries (e.g., "pending", "approved", "rejected")
    elif "status:" in gemini_result:
        status_query = gemini_result.split("status:")[1].strip()
        if invoices:
            filtered = [inv for inv in invoices if inv["status"].lower() == status_query]
            st.info(f"✅ Found **{len(filtered)}** {status_query.title()} invoices.")
            if filtered:
                for inv in filtered:
                    st.markdown(f"- **{inv['invoice_id']}** | Status: `{inv['status']}` | Amount: `Rs. {inv['amount']}`")
        else:
            st.warning("Could not retrieve invoice data.")

    # 4. Amount Threshold Query (e.g., "amount > 10000", "amount < 5000", "amount = 2500")
    elif "amount" in gemini_result:
        match = re.search(r'amount\s*([<>=])\s*(\d+)', gemini_result)
        if invoices and match:
            operator = match.group(1)
            threshold = int(match.group(2))
            filtered = []
            
            if operator == '>':
                filtered = [inv for inv in invoices if inv["amount"] > threshold]
            elif operator == '<':
                filtered = [inv for inv in invoices if inv["amount"] < threshold]
            elif operator == '=':
                filtered = [inv for inv in invoices if inv["amount"] == threshold]
            
            st.info(f"💰 Found **{len(filtered)}** invoices with amounts {operator} `Rs. {threshold}`.")
            for inv in filtered:
                st.markdown(f"- **{inv['invoice_id']}** | Amount: `Rs. {inv['amount']}` | Status: `{inv['status']}`")
    
    # 5. Vendor or Customer Query
    elif "vendor:" in gemini_result or "customer:" in gemini_result:
        key = "vendor" if "vendor:" in gemini_result else "customer"
        name = gemini_result.split(":")[1].strip()
        if invoices:
            filtered = [inv for inv in invoices if inv.get(key, "").lower() == name.lower()]
            st.info(f"🔍 Found **{len(filtered)}** invoices for **{key.title()} '{name}'**.")
            for inv in filtered:
                st.markdown(f"- **{inv['invoice_id']}** | Amount: `Rs. {inv['amount']}` | Status: `{inv['status']}`")
        else:
            st.warning("Could not retrieve invoice data.")
    
    # 6. Date Queries (e.g., "last_updated > 2023-01-15")
    elif "date" in gemini_result:
        date_match = re.search(r'date\s*([<>=])\s*(\d{4}-\d{2}-\d{2})', gemini_result)
        if invoices and date_match:
            operator = date_match.group(1)
            date_str = date_match.group(2)
            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            filtered = []
            for inv in invoices:
                invoice_date = datetime.strptime(inv["last_updated"].split('T')[0], "%Y-%m-%d").date()
                if operator == '>':
                    if invoice_date > query_date:
                        filtered.append(inv)
                elif operator == '<':
                    if invoice_date < query_date:
                        filtered.append(inv)
                elif operator == '=':
                    if invoice_date == query_date:
                        filtered.append(inv)
            
            st.info(f"📅 Found **{len(filtered)}** invoices with last_updated date {operator} `{date_str}`.")
            for inv in filtered:
                st.markdown(f"- **{inv['invoice_id']}** | Last Updated: `{inv['last_updated']}` | Status: `{inv['status']}`")
        else:
            st.warning("Could not process the date query. Please use the YYYY-MM-DD format.")
    
    # 7. Fallback/Unrecognized Intent
    else:
        st.warning("🤔 I'm sorry, I couldn't understand that query. Please try rephrasing.")