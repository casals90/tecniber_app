# 📋 Tecniber - Service Registration App

This project is a streamlined, user-friendly web application built with **Streamlit**. It is designed to capture technical service data—including client details, job timings, and a digital signature—and automatically generate completed PDF forms (such as Endesa service reports and Testo analyzer tickets).

## ✨ Key Features

* **Interactive Frontend:** A clean, centered Streamlit interface featuring a custom sticky header and company logo.
* **Digital Signature Capture:** Integrates a drawing pad using `streamlit-drawable-canvas` to securely capture client signatures on the spot.
* **Robust Form Validation:** Prevents submission errors by strictly checking that all text, time, and signature fields are filled before processing.
* **Automated PDF Processing:** Passes the validated data and the `PIL` signature image to the backend (`src.core`), which dynamically generates, overlays, and saves complex PDF documents without manual data entry.
* **Intelligent Image Handling:** The backend automatically removes canvas backgrounds and tightly crops the signature so it scales perfectly onto the final PDFs.

---

## 🛠️ Tech Stack

* **Frontend:** [Streamlit](https://streamlit.io/)
* **Signature Canvas:** `streamlit-drawable-canvas`
* **Image Processing:** `Pillow` (PIL)
* **PDF Generation & Manipulation:** `pypdf`, `reportlab`
* **Package Management:** `uv` (Astral)

## 📁 Project Structure

While your specific architecture may vary, the core application relies on this general structure:

```text
├── main.py                  # Main Streamlit frontend application
├── resources/
│   └── logotecniber.png    # Company logo used in the sticky header
├── data/                  # Default output folder for generated ZIPs/PDFs
│   ├── endesa/
│   │    └── form_template.pdf
│   ├── ticket/
│   │    └── ticket_template.pdf
└── src/
│   ├── core/
│   │   └── process.py      # Main execution logic bridging UI and PDF generation
│   ├── endesa/
│   │   ├── utils.py        # Helper functions (e.g., finding fonts)
│   │   └── filler.py       # EndesaFormFiller class
│   ├── ticket/
│   │   └── filler.py       # TicketFiller class
│   └── settings.py         # Global configuration (e.g., DEFAULT_FONT_SIZE)
├── pyproject.toml.py  





