# 📋 Tecniber - Service Registration App

This project is a streamlined, user-friendly web application built with **Streamlit**. It is designed to capture technical service data—including client details, job timings, and a digital signature—and automatically generate completed PDF forms (such as Endesa service reports and Testo analyzer tickets).

## ✨ Key Features

- **Interactive Frontend:** A clean, centered Streamlit interface featuring a custom sticky header and company logo.
- **Digital Signature Capture:** Integrates a drawing pad using `streamlit-drawable-canvas` to securely capture client signatures on the spot.
- **Robust Form Validation:** Prevents submission errors by strictly checking that all text, time, and signature fields are filled before processing.
- **Automated PDF Processing:** Passes the validated data and the `PIL` signature image to the backend (`src.core`), which dynamically generates, overlays, and saves complex PDF documents without manual data entry.
- **Intelligent Image Handling:** The backend automatically removes canvas backgrounds and tightly crops the signature so it scales perfectly onto the final PDFs.

---

## 🛠️ Tech Stack

- **Frontend:** [Streamlit](https://streamlit.io/)
- **Signature Canvas:** `streamlit-drawable-canvas`
- **Image Processing:** `Pillow` (PIL)
- **PDF Generation & Manipulation:** `pypdf`, `reportlab`
- **Package Management:** `uv` (Astral)

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
```

--

## 🚀 Installation & Setup

This project uses [uv](https://github.com/astral-sh/uv) for lightning-fast environment and dependency management.

**1. Clone the repository and navigate to the project folder:**

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

**2. Create a virtual environment using `uv`:**

```bash
uv venv
```

**3. Activate the virtual environment:**

```bash
# On Windows:
.venv\\Scripts\\activate
# On macOS/Linux:
source .venv/bin/activate
```

**4. Install the required dependencies:**

```bash
uv add install streamlit streamlit-drawable-canvas Pillow pypdf reportlab
```

---

## 💻 Usage

With your virtual environment activated, you can run the application using `uv`:

```bash
uv run streamlit run app.py
```

### How to use the app:

1. Open the local URL provided by Streamlit in your web browser.
2. Fill out all the required fields in the **"Nou Servei"** form.
3. Have the client draw their signature in the designated pad.
4. Verify the input/output folder paths.
5. Click **"Genera"**. The app will validate the data and trigger the backend PDF generation process, saving the final documents to your specified output folder.

---

### A Note on Fonts

The backend PDF generation relies on locating specific fonts (like standard Sans-Serif and handwriting-style fonts) installed on your operating system. If specific fonts are not found, the system will gracefully fall back to default PDF fonts (like Helvetica).
