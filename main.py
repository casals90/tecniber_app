from src.endesa_form import endesa_form


def main():
    print("Hello from tecniber-app!")

    input_dict = {
        "num_service": {
            "value": "12035237"
        },
        "start_time": {
            "value": "10:30"
        },
        "end_time": {
            "value": "11:10"},
        "technician": {
            "value": "Josep Pons"},
        "company": {"value": "PBN290"},
        "client": {"value": "Alba Aumtell"},
        "address": {"value": "C/ Falsa 123"},
        "data": {
            "value": "11/02/2026",
            "styles": {"font_size": 12}
        },
        "dni": {
            "value": "12345678T",
            "styles": {"font_size": 18}
        }
    }

    input_file_path = "data/endesa_form/parte_formulari_editable.pdf"
    output_file_path = "data/endesa_form/endesa_filled.pdf"

    form = endesa_form.EndesaFormFiller(
        input_file_path, output_file_path, input_dict)
    form.generate()


if __name__ == "__main__":
    main()
