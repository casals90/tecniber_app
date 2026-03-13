import base64
import json
import pathlib

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from src import settings
from src.core import process


def get_base64_image(file_path: str) -> str:
    """
    Reads a local image and converts it to base64 for HTML embedding.
    """
    try:
        with open(file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception:
        # Fallback empty string if the image isn't found, preventing crashes
        return ""


def render_service_registration_form(form_key):
    """
    Renders the UI form and returns the gathered data upon interaction.
    """

    st.markdown("### 📋 Registre de Serveis")
    st.caption("Introdueix les dades del servei")

    # --- FORM UI ---
    with st.form(f"service_form_{form_key}", border=True):

        # ROW 1
        col_label, col_dia = st.columns([1, 3])
        with col_label:
            st.markdown(
                "<div style='margin-top: 10px; font-weight: bold;'>Nou Servei</div>", unsafe_allow_html=True)
        with col_dia:
            service_date = st.date_input("Dia *", label_visibility="collapsed")

        st.write("")

        # ROW 2
        col1, col2, col3 = st.columns(3)
        with col1:
            service_num = st.text_input(
                "Nº Servei *", placeholder="S-0001")
        with col2:
            start_time = st.time_input("H. Inici *", value="09:00")
        with col3:
            end_time = st.time_input("H. Final", value=None)

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
            client = st.text_input(
                "Client *", placeholder="Nom del client")
        with col7:
            dni = st.text_input(
                "DNI *", placeholder="12345678A", max_chars=9)

        # ROW 5
        col8, col9 = st.columns(2)
        with col8:
            images_folder = st.text_input(
                "Carpeta imatges *", placeholder="C:/ruta/a/les/imatges",
                value=st.session_state.get("saved_images_folder", ""))
        with col9:
            output_folder = st.text_input(
                "Guardar zip *", placeholder="C:/ruta/de/sortida",
                value=st.session_state.get("saved_output_folder", ""))

        st.write("")
        st.write("")  # Add a little extra breathing room

        # Center the text label
        st.markdown(
            "<p style='text-align: center; font-weight: bold;'>✍️ Signatura del Client *</p>", unsafe_allow_html=True)

        # Use columns to push the canvas to the center
        # The ratio [1, 2, 1] means the center column is twice as wide
        # as the sides
        _, pad_col2, _ = st.columns([1, 2, 1])

        with pad_col2:
            canvas_result = st_canvas(
                stroke_width=3,
                stroke_color="#000000",
                background_color="#EEEEEE",
                height=150,
                # Fixed width to keep it looking like a standard signature box
                width=400,
                drawing_mode="freedraw",
                key=f"canvas_{form_key}",
            )

        st.write("")

        # BUTTONS
        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        with btn_col1:
            submitted = st.form_submit_button("Genera", type="primary")
        with btn_col2:
            netejar = st.form_submit_button("🔄 Netejar")

    # --- RETURN DATA FOR MAIN TO HANDLE ---
    if submitted:
        # Check if the user actually drew something
        has_signature = False
        if canvas_result.json_data is not None:
            # If the 'objects' list has items, the user drew on the canvas
            if len(canvas_result.json_data.get("objects", [])) > 0:
                has_signature = True

        # Convert to image ONLY if they actually signed
        signature_image = None
        if has_signature and canvas_result.image_data is not None:
            # image_data is a numpy array, convert it to a Pillow Image
            # Using astype(np.uint8) ensures compatibility with PIL
            signature_image = Image.fromarray(
                canvas_result.image_data.astype('uint8'))

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
                "dni": dni,
                "images_folder": images_folder,
                "output_folder": output_folder,
                "signature": signature_image
            }
        }
    elif netejar:
        return {"action": "clear", "data": None}

    return None


def main():
    # Page configuration (MUST be the first Streamlit command)
    st.set_page_config(
        page_title="Registre de Serveis", page_icon="📋", layout="wide")

    # Initialize form key for the clear functionality
    if "form_key" not in st.session_state:
        st.session_state.form_key = 0

    # --- NEW: Check config.json for folder paths on first load ---
    if "saved_images_folder" not in st.session_state or "saved_output_folder" not in st.session_state:
        st.session_state.saved_images_folder = ""
        st.session_state.saved_output_folder = ""

        config_path = pathlib.Path(settings.CONFIG_FILE)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    st.session_state.saved_images_folder = config_data.get(
                        "images_folder", "")
                    st.session_state.saved_output_folder = config_data.get(
                        "output_folder", "")
            except Exception:
                pass  # If file is malformed, just fall back to empty strings
    # -------------------------------------------------------------

    # --- LOAD LOGO ---
    # Ensure this path matches exactly where your logo is located
    logo_path = pathlib.Path("resources") / "logotecniber.png"
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
    _, main_content, _ = st.columns([1, 3, 1])

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
                    # "end_time": "H. Final",
                    "technician": "Tècnic",
                    "address": "Adreça",
                    "client": "Client",
                    "dni": "DNI",
                    "images_folder": "Carpeta imatges",
                    "output_folder": "Guardar zip"
                }

                # Check for empty text/date values
                for key, value in form_data.items():
                    if key not in ("signature", "end_time") and (value is None or str(value).strip() == ""):
                        empty_fields.append(field_names.get(key, key))

                # Specifically check if the signature is missing
                if form_data["signature"] is None:
                    empty_fields.append("Signatura")

                if empty_fields:
                    st.error(
                        f"❌ Error: Hi ha camps obligatoris buits. Falten: **{', '.join(empty_fields)}**")
                else:
                    st.success(
                        f"✅ Servei **{form_data['service_num']}** generat correctament per al client **{form_data['client']}**!")

                    with open(settings.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump({
                            "images_folder": form_data["images_folder"],
                            "output_folder": form_data["output_folder"]
                        }, f, indent=4)

                    # Save folder paths to session state and reset the form
                    st.session_state.saved_images_folder = form_data["images_folder"]
                    st.session_state.saved_output_folder = form_data["output_folder"]
                    st.session_state.form_key += 1

                    output_folder = form_data["output_folder"]

                    # Passed validation, safe to execute!
                    process.execute(form_data, output_folder)

                    st.rerun()

            elif form_result["action"] == "clear":
                # Increment the key to destroy the old form state, then rerun
                st.session_state.form_key += 1
                st.rerun()
