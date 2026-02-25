
import streamlit as st


def render_service_registration_form():
    """
    Renders the UI form and returns the gathered data upon interaction.
    """

    st.markdown("### 📋 Registre de Serveis")
    st.caption("Introdueix les dades del servei")

    # --- FORM UI ---
    with st.form("service_form", border=True):

        # ROW 1
        col_label, col_dia = st.columns([1, 3])
        with col_label:
            st.markdown(
                "<div style='margin-top: 10px; font-weight: bold;'>Nou Servei</div>", unsafe_allow_html=True)
        with col_dia:
            data_servei = st.date_input("Dia", label_visibility="collapsed")

        st.write("")

        # ROW 2
        col1, col2, col3 = st.columns(3)
        with col1:
            num_servicio = st.text_input(
                "Nº Servicio *", value="S-0001", disabled=True)
        with col2:
            h_inici = st.time_input("H. Inici", value=None)
        with col3:
            h_final = st.time_input("H. Final", value=None)

        # ROW 3
        col4, col5 = st.columns([1, 2])
        with col4:
            tecnic = st.text_input("Tècnic", placeholder="Nom del tècnic")
        with col5:
            adreca = st.text_input(
                "Adreça", placeholder="Carrer, número, ciutat")

        # ROW 4
        col6, col7 = st.columns(2)
        with col6:
            client = st.text_input("Client *", placeholder="Nom del client")
        with col7:
            dni = st.text_input("DNI", placeholder="12345678A")

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
                "dia": data_servei,
                "num_servicio": num_servicio,
                "h_inici": h_inici,
                "h_final": h_final,
                "tecnic": tecnic,
                "adreca": adreca,
                "client": client,
                "dni": dni
            }
        }
    elif netejar:
        return {"action": "clear", "data": None}

    # Returns None if no buttons were clicked yet
    return None


def main():
    # Streamlit requires set_page_config to be the first Streamlit command
    # executed
    st.set_page_config(
        page_title="Registre de Serveis", page_icon="📋", layout="centered")

    st.markdown("""
        <style>
            div[data-testid="stForm"] {
                background-color: #fcfcfc;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 1px 1px 10px rgba(0,0,0,0.05);
            }
        </style>
    """, unsafe_allow_html=True)

    # 1. Call the external function to render the UI and catch the result
    form_result = render_service_registration_form()

    # 2. Handle the business logic based on the returned dictionary
    if form_result:
        if form_result["action"] == "submit":
            form_data = form_result["data"]

            # Validation logic inside main
            if not form_data["client"]:
                st.error(
                    "Si us plau, introdueix el nom del client (Camp obligatori).")
            else:
                # Database insertion logic would go here
                st.success(
                    f"Servei {form_data['num_servicio']} generat correctament per al client {form_data['client']}!")

        elif form_result["action"] == "clear":
            st.info("S'ha sol·licitat netejar el formulari.")


if __name__ == "__main__":
    main()
