import base64
import pathlib

import streamlit as st


def get_base64_image(file_path):
    """Reads a local image and converts it to base64 for HTML embedding."""
    try:
        with open(file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception:
        # Fallback empty string if the image isn't found, preventing crashes
        return ""


def render_service_registration_form(form_key):
    """Renders the UI form and returns the gathered data upon interaction."""

    st.markdown("### 📋 Registre de Serveis")
    st.caption("Introdueix les dades del servei")

    # --- FORM UI ---
    with st.form(f"service_form_{form_key}", border=True):

        # ROW 1
        col_label, col_dia = st.columns([1, 3])
        with col_label:
            st.markdown(
                "<div style='margin-top: 10px; font-weight: bold;'>Nou Servei *</div>", unsafe_allow_html=True)
        with col_dia:
            service_date = st.date_input("Dia *", label_visibility="collapsed")

        st.write("")

        # ROW 2
        col1, col2, col3 = st.columns(3)
        with col1:
            service_num = st.text_input(
                "Nº Servei *", value="S-0001", placeholder="S-0001")
        with col2:
            start_time = st.time_input("H. Inici *", value=None)
        with col3:
            end_time = st.time_input("H. Final *", value=None)

        # ROW 3
        col4, col5 = st.columns([1, 2])
        with col4:
            technician = st.text_input(
                "Tècnic *", placeholder="Nom del tècnic")
        with col5:
            address = st.text_input(
                "Adreça *", placeholder="Carrer, número, ciutat")

        # ROW 4
        col6, col7 = st.columns(2)
        with col6:
            client = st.text_input("Client *", placeholder="Nom del client")
        with col7:
            dni = st.text_input("DNI *", placeholder="12345678A")

        st.write("")

        # BUTTONS
        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        with btn_col1:
            submitted = st.form_submit_button("Genera", type="primary")
        with btn_col2:
            netejar = st.form_submit_button("🔄 Netejar")

    # --- RETURN DATA FOR MAIN TO HANDLE ---
    if submitted:
        return {
            "action": "submit",
            "data": {
                "service_date": service_date,
                "service_num": service_num,
                "start_time": start_time,
                "end_time": end_time,
                "technician": technician,
                "address": address,
                "client": client,
                "dni": dni
            }
        }
    elif netejar:
        return {"action": "clear", "data": None}

    return None


def main():
    """Main application controller."""

    # Page configuration (MUST be the first Streamlit command)
    st.set_page_config(page_title="Registre de Serveis",
                       page_icon="📋", layout="wide")

    # Initialize form key for the clear functionality
    if "form_key" not in st.session_state:
        st.session_state.form_key = 0

    # --- LOAD LOGO ---
    # Ensure this path matches exactly where your logo is located
    logo_path = pathlib.Path("resources") / "images" / "logotecniber.png"
    logo_base64 = get_base64_image(logo_path)

    # --- INJECT CUSTOM CSS AND FIXED HEADER ---
    st.markdown(f"""
        <style>
            /* Completely hide Streamlit's default header (Deploy button & 3 dots) */
            header[data-testid="stHeader"] {{
                display: none !important;
            }}

            /* 1. Create the fixed sticky header */
            .fixed-header {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 80px; /* Fixed height for the header */
                background-color: #ffffff;
                z-index: 99990; /* Keep it just below the Streamlit menu */
                padding: 0 3rem;
                border-bottom: 2px solid #f0f2f6;
                box-shadow: 0px 4px 6px -6px rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
            }}
            
            /* Logo sizing inside the fixed header - FIXED CROPPING */
            .fixed-header img {{
                max-width: 250px; 
                max-height: 50px; /* Constrains the image so it cannot be cut off */
                width: auto;
                height: auto;
                object-fit: contain; /* Ensures the whole logo scales to fit */
            }}

            /* 2. Push the main Streamlit content down so the header doesn't cover it */
            .main .block-container {{
                padding-top: 110px !important; 
            }}

            /* Form card styling */
            div[data-testid="stForm"] {{
                background-color: #fcfcfc;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 1px 1px 10px rgba(0,0,0,0.05);
            }}
        </style>

        <div class="fixed-header">
            <img src="data:image/png;base64,{logo_base64}" alt="Tecniber Logo">
        </div>
    """, unsafe_allow_html=True)

    # --- FORM PLACEMENT ---
    # Centering the form by using empty columns on the sides
    spacer_left, main_content, spacer_right = st.columns([1, 3, 1])

    with main_content:
        # Render UI
        form_result = render_service_registration_form(
            st.session_state.form_key)

        # Handle Logic
        if form_result:
            if form_result["action"] == "submit":
                form_data = form_result["data"]
                empty_fields = []

                # Map internal keys to display names for errors
                field_names = {
                    "service_date": "Dia",
                    "service_num": "Nº Servei",
                    "start_time": "H. Inici",
                    "end_time": "H. Final",
                    "technician": "Tècnic",
                    "address": "Adreça",
                    "client": "Client",
                    "dni": "DNI"
                }

                # Check for empty values
                for key, value in form_data.items():
                    if value is None or str(value).strip() == "":
                        empty_fields.append(field_names[key])

                if empty_fields:
                    st.error(
                        f"❌ Error: Tots els camps són obligatoris. Falten: **{', '.join(empty_fields)}**")
                else:
                    st.success(
                        f"✅ Servei **{form_data['service_num']}** generat correctament per al client **{form_data['client']}**!")

            elif form_result["action"] == "clear":
                # Increment the key to destroy the old form state, then rerun
                st.session_state.form_key += 1
                st.rerun()


if __name__ == "__main__":
    main()
