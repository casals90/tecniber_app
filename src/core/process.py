import logging
import pathlib
import random
import tempfile
import zipfile
from typing import Any

from src.endesa import form as endesa_form
from src.settings import VALID_IMAGE_EXTENSIONS
from src.ticket import filler as ticket_filler

logger = logging.getLogger(__name__)


def get_random_image(folder_path: str | pathlib.Path) -> pathlib.Path | None:
    """
    Scans a directory for image files and returns a randomly selected path.

    Args:
        folder_path: The directory path to search for images.

    Returns:
        Optional[pathlib.Path]: The path to a randomly selected image file, 
            or None if the directory is invalid or contains no images.
    """
    images_dir = pathlib.Path(folder_path)

    if not images_dir.exists() or not images_dir.is_dir():
        logger.warning(f"Image directory not found: {images_dir}")
        return None

    # Filter files in the directory
    images = [
        file for file in images_dir.iterdir()
        if file.is_file() and file.suffix.lower() in VALID_IMAGE_EXTENSIONS
    ]

    if not images:
        logger.warning(f"No valid image files found in {images_dir}")
        return None

    selected_image = random.choice(images)
    logger.info(f"Selected random image: {selected_image.name}")

    return selected_image


def execute(input_data: dict[str, Any], output_folder: pathlib.Path | str) \
        -> pathlib.Path:
    """
    Fills the Endesa form, the ticket and a random image from a given folder 
    then packages both into a ZIP file.

    Args:
        input_data: Dictionary containing the service data.
        output_folder: Destination folder where the final ZIP file will 
            be saved.

    Returns:
        pathlib.Path: The absolute path to the generated ZIP file.
    """
    logger.info("Starting document generation process...")

    # Ensure the output directory exists
    out_dir = pathlib.Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_output_path = out_dir / f"Documents-{input_data["service_num"]}.zip"

    # Define input template paths
    template_form_path = pathlib.Path("data") / "endesa" / "form.pdf"
    template_ticket_path = pathlib.Path("data") / "ticket" / "ticket.pdf"

    # Use a temporary directory for the intermediate PDF files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)

        endesa_filled_path = temp_path / \
            f"Parte-{input_data["service_num"]}.pdf"
        ticket_filled_path = temp_path / \
            f"Tiquet-{input_data["service_num"]}.pdf"

        # Fill the Endesa form
        form = endesa_form.EndesaFormFiller(
            input_path=str(template_form_path),
            output_path=str(endesa_filled_path),
            fields=input_data
        )
        form.generate()

        # Fill the Ticket data
        filler = ticket_filler.TicketFiller(
            input_path=str(template_ticket_path),
            output_path=str(ticket_filled_path),
            date1=input_data["service_date"],
            time1=input_data["start_time"],
            time2=input_data["end_time"],
            dni=input_data["dni"],
            signature=input_data["signature"]
        )
        filler.fill()

        # Get the random image
        random_image = get_random_image(input_data.get("images_folder", ""))

        # --- Package into a ZIP file ---
        # Using ZIP_DEFLATED to compress the files slightly
        with zipfile.ZipFile(
                zip_output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # arcname prevents storing the absolute path structure inside
            # the zip
            zip_file.write(endesa_filled_path, arcname=endesa_filled_path.name)
            zip_file.write(ticket_filled_path, arcname=ticket_filled_path.name)

            if random_image:
                zip_file.write(random_image, arcname=random_image.name)

    logger.info(f"✅ Documents successfully zipped at: {zip_output_path}")

    return zip_output_path
