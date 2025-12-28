

import os

from app.utils.text_extraction import pdf_to_markdown_ocr_inline


def loop_through_pdfs(main_folder, func):
   
    for root, dirs, files in os.walk(main_folder):
        for file in files:
            if file.lower().endswith(".pdf"):
                file_path = os.path.join(root, file)

                # Preserve relative folder structure under main_folder
                relative_dir = os.path.relpath(root, main_folder)
                if relative_dir != "output":
                    output_dir = os.path.join(main_folder,"output" , relative_dir)
                    os.makedirs(output_dir, exist_ok=True)

                    # Define output file path (e.g., same name but .json)
                    output_filepath = os.path.join(output_dir, f"{os.path.splitext(file)[0]}.md")

                    if not os.path.exists(output_filepath):
                        print(f"Processing: {file_path} -> {output_filepath}")
                        remove_images=True
                        if relative_dir =="datasheets":
                            remove_images=False
                        
                        func(file_path, output_filepath,extract_images=remove_images)
                

main_folder = "/code/app/native_pdf_data"  # <-- replace this
loop_through_pdfs(main_folder, pdf_to_markdown_ocr_inline)
