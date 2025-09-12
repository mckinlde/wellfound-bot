import os

def prepend_dirname_to_files(base_dir):
    # Walk through all subdirectories in base_dir
    for root, dirs, files in os.walk(base_dir):
        dir_name = os.path.basename(root)
        for file in files:
            # Skip if the file already starts with dir_name_
            if file.startswith(f"{dir_name}_"):
                continue

            old_path = os.path.join(root, file)
            new_filename = f"{dir_name}_{file}"
            new_path = os.path.join(root, new_filename)

            print(f"Renaming: {old_path} → {new_path}")
            os.rename(old_path, new_path)

if __name__ == "__main__":
    base_dir = r"C:\Users\mckin\OneDrive\Desktop\wellfound-bot\medicare\UnitedHealthcare\uhc_plan_pdfs"
    prepend_dirname_to_files(base_dir)
