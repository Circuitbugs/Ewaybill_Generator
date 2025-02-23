import streamlit as st
import pandas as pd
import datetime
import re
import io
import os
import sys

# Helper function for resource paths (for PyInstaller compatibility)
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS  # PyInstaller creates a temporary folder and stores path in _MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Set page configuration as the very first command
st.set_page_config(page_title="E-Way Bill Generator", layout="wide")

# Initialize the login state if not already set
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# -----------------------
# Define Login UI
# -----------------------
def login_ui():
    st.title("Login")
    user_id = st.text_input("User ID", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if user_id == "Admin" and password == "Geeta@2025":
            st.session_state.logged_in = True
        else:
            st.error("Invalid credentials!")

# -----------------------
# Define Main Program UI
# -----------------------
def main_ui():
    # Add a logout button at the top
    if st.button("Logout"):
        st.session_state.logged_in = False

    # --- Rest of Main Program UI below ---
    gstin_mapping = {
        "Gujarat": "24AAACS0764L1ZC", "Haryana": "06AAACS0764L1ZA", "Tamil Nadu": "33AAACS0764L1ZD",
        "Karnataka": "29AAACS0764L1Z2", "Maharashtra": "27AAACS0764L1Z6", "Delhi": "07AAACS0764L1Z8",
        "West Bengal": "19AAACS0764L1Z3", "Madhya Pradesh": "23AAACS0764L1ZE", "Uttar Pradesh": "09AAACS0764L1Z4",
        "Goa": "30AAACS0764L1ZJ", "Puducherry": "34AAACS0764L1ZB", "Chandigarh": "04AAACS0764L1ZE",
        "Telangana": "36AAACS0764L1Z7", "Chhattisgarh": "22AAACS0764L1ZG", "Jammu & Kashmir": "01AAACS0764L1ZK",
        "Himachal Pradesh": "02AAACS0764L1ZI", "Punjab": "03AAACS0764L1ZG", "Uttarakhand": "05AAACS0764L1ZC",
        "Rajasthan": "08AAACS0764L1Z6", "Bihar": "10AAACS0764L1ZL", "Assam": "18AAACS0764L1Z5",
        "Jharkhand": "20AAACS0764L1ZK", "Odisha": "21AAACS0764L1ZI", "Andhra Pradesh (New)": "37AAACS0764L1Z5",
        "Kerala": "32AAACS0764L1ZF", "Meghalaya": "17AAACS0764L1Z7"
    }

    def process_eway_bill(import_file, item_file, vehicle_no, distance_km):
        # Read files
        df_import_job = pd.read_excel(import_file, sheet_name='Sheet1')
        df_item_report = pd.read_csv(item_file, thousands=",")
        
        # Check for required headers in Import Job Register
        required_import_headers = ["Job No", "BE No", "BE Date", "Supplier/Exporter", "Importer", "Importer Address"]
        missing_import_headers = [col for col in required_import_headers if col not in df_import_job.columns]
        
        # Check for required headers in Item Report
        required_item_headers = ["Job No", "Assessable Value (INR)", "SWS Duty Amt", "BCD Foregone", "Total Basic Duty (INR)", "IGST", "IGST Rate", "Product Desc", "CTH", "Quantity", "Unit"]
        missing_item_headers = [col for col in required_item_headers if col not in df_item_report.columns]
        
        # If any required headers are missing, return an error message.
        if missing_import_headers or missing_item_headers:
            error_message = ""
            if missing_import_headers:
                error_message += f"Missing columns in Import Job Register: {', '.join(missing_import_headers)}. "
            if missing_item_headers:
                error_message += f"Missing columns in Item Report: {', '.join(missing_item_headers)}."
            return None, None, None, error_message

        missing_jobs = set(df_item_report["Job No"]) - set(df_import_job["Job No"])
        if missing_jobs:
            return None, None, None, f"Missing Job Numbers: {', '.join(map(str, missing_jobs))}"

        numeric_columns = ["Assessable Value (INR)", "SWS Duty Amt", "BCD Foregone", "Total Basic Duty (INR)", "IGST"]
        for col in numeric_columns:
            df_item_report[col] = pd.to_numeric(df_item_report[col], errors='coerce').fillna(0)

        merged_df = df_item_report.merge(df_import_job, on=["Job No", "BE No"], how="inner")

        # Capture the job numbers for which the E-Way Bill is prepared
        job_numbers = merged_df["Job No"].unique().tolist()

        ewaybill_data = []
        for _, row in merged_df.iterrows():
            total_taxable_value = row["Assessable Value (INR)"] + row["SWS Duty Amt"] + row["BCD Foregone"] + row["Total Basic Duty (INR)"]
            total_invoice_value = total_taxable_value + row["IGST"]
            bill_to_state = row["Importer Address"].strip().split(",")[-2].strip()
            bill_to_gstin = gstin_mapping.get(bill_to_state, "")

            address = row["Importer Address"]
            all_numbers = re.findall(r"\b\d{6}\b", address)
            if all_numbers:
                pin_code = all_numbers[-1]
                address = address.split(pin_code)[0].strip()

            words = address.split()
            mid = len(words) // 2

            ship_to_address = " ".join(words[:mid])
            ship_to_place = " ".join(words[mid:])

            ship_to_pin_code = re.findall(r"\b\d{6}\b", row["Importer Address"])
            ship_to_pin_code = ship_to_pin_code[-1] if ship_to_pin_code else ""
            product_name = row["Product Desc"][:100]
            product_description = row["Product Desc"][:100]

            ewaybill_data.append([
                "Import", "Bill of Entry", row["BE No"], row["BE Date"].strftime('%d-%m-%Y') if pd.notna(row["BE Date"]) else "",
                row["Supplier/Exporter"], "URP", "99", "AIR CARGO COMPLEX", "SAHAR ANDHERI EAST", "400099", "27",
                row["Importer"], bill_to_gstin, bill_to_gstin[:2], ship_to_address, ship_to_place, ship_to_pin_code,
                bill_to_gstin[:2], product_name, product_description, row["CTH"], row["Quantity"], row["Unit"],
                total_taxable_value, 0, 0, row["IGST Rate"], 0, 0, 0, row["IGST"], 0, total_invoice_value,
                "Geeta Freight Forwarders Pvt Ltd", "27AAACG8785D1ZE", distance_km, "Road", "Regular", vehicle_no, "LR",
                datetime.datetime.today().strftime('%d-%m-%Y')
            ])

        df_ewaybill = pd.DataFrame(ewaybill_data, columns=[
            "Sub-type", "Document Type", "Document No", "Document Date", "Bill from Company Name", "Bill from GSTIN ID", "Bill from State", 
            "Despatch from Address", "Despatch from Place", "Despatch from PIN Code", "Bill to State Code", "Bill to Company Name", "Bill to GSTIN ID", 
            "Bill to State", "Ship to Address", "Ship to Place", "Ship to PIN Code", "Ship to State", "Product Name", "Product Description", "HSN", 
            "Quantity", "Unit", "Taxable Value", "CGST Rate", "SGST/UTGST Rate", "IGST Rate", "Cess Rate", "CGST Amount", "SGST Amount", "IGST Amount", 
            "CESS Amount", "Total Invoice Value", "Transporter Name", "Transporter ID", "Approx Distance (km)", "Mode", "Vehicle Type", "Vehicle No", 
            "Transporter Doc No", "Transporter Doc Date"])
            
        # Use the first BE No from the merged data to create the output file name
        be_no = merged_df["BE No"].iloc[0]
        output_filename = f"EWB_{be_no}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        output = io.BytesIO()
        df_ewaybill.to_excel(output, index=False)
        output.seek(0)
        
        # Create a log DataFrame for processed Job No, BE No, and Vehicle No, along with a timestamp
        df_log = merged_df[['Job No', 'BE No']].drop_duplicates()
        df_log["Vehicle No"] = vehicle_no
        df_log['Processed Date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_filename = "Ewaybill_Processing_Log.csv"
        if os.path.exists(log_filename):
            df_log.to_csv(log_filename, mode='a', header=False, index=False)
        else:
            df_log.to_csv(log_filename, mode='w', header=True, index=False)
        
        return output, output_filename, job_numbers, None

    # Center the logo using columns and use the resource_path function
    cols = st.columns(3)
    with cols[1]:
        logo_path = resource_path("geeta_logo.png")
        st.image(logo_path, width=250)

    st.markdown("""<h1 style='color: #120f64; text-align: center;'>E-Way Bill Generator - Geeta Group</h1>""", unsafe_allow_html=True)
    st.markdown("""<p style='color: #741868; text-align: center;'>Upload Import Job Register and Item Report to generate an E-Way Bill.</p>""", unsafe_allow_html=True)

    import_file = st.file_uploader("📂 Upload Import Job Register (Excel)", type=["xlsx"])
    item_file = st.file_uploader("📂 Upload Item Report (CSV)", type=["csv"])
    vehicle_no = st.text_input("🚗 Enter Vehicle Number")
    distance_km = st.number_input("📏 Enter Approximate Distance (km)", min_value=0)

    generate_button = st.button("🚀 Generate E-Way Bill")

    if generate_button:
        # Input validation for required files and fields
        if not import_file:
            st.error("Please upload the Import Job Register (Excel) file.")
            st.stop()
        if not item_file:
            st.error("Please upload the Item Report (CSV) file.")
            st.stop()
        if not vehicle_no.strip():
            st.error("Please enter the Vehicle Number.")
            st.stop()
        if distance_km <= 0:
            st.error("Please enter a valid Approximate Distance (km) greater than 0.")
            st.stop()

        output, output_filename, job_numbers, error = process_eway_bill(import_file, item_file, vehicle_no, distance_km)
        if error:
            st.error(error)
        else:
            st.success("✅ E-Way Bill successfully generated!")
            st.download_button(label="📥 Download E-Way Bill", data=output, file_name=output_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.markdown("### E-Way Bill prepared for Job Numbers:")
            # Display each job number as a clickable button
            for job in job_numbers:
                st.button(f"Job No: {job}")

    # Log Download Section
    st.markdown("## Download Log")
    selected_date = st.date_input("Select Log Date", key="log_date")
    if st.button("Download Log for Selected Date"):
        log_filename = "Ewaybill_Processing_Log.csv"
        if os.path.exists(log_filename):
            df_log = pd.read_csv(log_filename)
            df_log['Processed Date'] = pd.to_datetime(df_log['Processed Date'])
            df_filtered = df_log[df_log['Processed Date'].dt.date == selected_date]
            if df_filtered.empty:
                st.info("No log entries for the selected date.")
            else:
                csv = df_filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Filtered Log",
                    data=csv,
                    file_name=f"Ewaybill_Log_{selected_date}.csv",
                    mime="text/csv"
                )
        else:
            st.error("Log file does not exist.")

# End of main_ui()

# Render the UI based on the login state
if not st.session_state.logged_in:
    login_ui()
else:
    main_ui()
