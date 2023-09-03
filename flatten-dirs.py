import os
import sys
import shutil

# Check if the correct number of arguments are provided
if len(sys.argv) != 2:
    print("Usage: python script.py <source_directory>")
    sys.exit(1)

# Get source and destination directories from command-line arguments
src_dir = sys.argv[1]

for subdir in os.listdir(src_dir):
    # print(subdir)
    subdir_path = os.path.join(src_dir, subdir)
    if not os.path.isdir(subdir_path):
        continue

    for photos_subdir in os.listdir(subdir_path):
        # print(photos_subdir)
        photos_subdir_path = os.path.join(subdir_path, photos_subdir)
        # print(photos_subdir_path)
        if not os.path.isdir(photos_subdir_path):
            continue

        new_photos_subdir_path = os.path.join(src_dir, photos_subdir)
        os.makedirs(new_photos_subdir_path, exist_ok=True)

        # Loop through each file in the subdirectory
        for filename in os.listdir(photos_subdir_path):
            file_path = os.path.join(photos_subdir_path, filename)
            # print(file_path)            
            if os.path.isfile(file_path):
                # Copy or move the file to the destination directory
                dest_file_path = os.path.join(new_photos_subdir_path, filename)
                # shutil.move(file_path, new_photos_subdir_path, copy_function=shutil.copy2)
                # Check if the destination file already exists
                if os.path.exists(dest_file_path):
                    try:
                        # Remove the existing destination file
                        os.remove(dest_file_path)
                        print(f"Removed existing file at '{dest_file_path}'.")
                    except Exception as e:
                        print(f"Error while removing existing file: {e}")

                # Use shutil.move() to move the file to the destination folder
                try:
                    shutil.move(file_path, new_photos_subdir_path)
                    # print(f"The file '{file_path}' has been successfully moved to '{new_photos_subdir_path}'.")
                except Exception as e:
                    print(f"An error occurred while moving the file: {e}")

for subdir in os.listdir(src_dir):
    # print(subdir)
    subdir_path = os.path.join(src_dir, subdir)
    if not os.path.isdir(subdir_path):
        continue

    for photos_subdir in os.listdir(subdir_path):
        # print(photos_subdir)
        photos_subdir_path = os.path.join(subdir_path, photos_subdir)
        # print(photos_subdir_path)
        if not os.path.isdir(photos_subdir_path):
            continue
        items = os.listdir(photos_subdir_path)
        if len(items) == 0:
            try:
                os.rmdir(photos_subdir_path)
                print(f"The folder at '{photos_subdir_path}' has been successfully removed.")
            except OSError as e:
                print(f"Error: {e}")

    items = os.listdir(subdir_path)
    if len(items) == 1 and items[0] == '.DS_Store':
        os.remove(os.path.join(subdir_path, '.DS_Store'))
    items = os.listdir(subdir_path)
    if len(items) == 0:
        try:
            os.rmdir(subdir_path)
            print(f"The folder at '{subdir_path}' has been successfully removed.")
        except OSError as e:
            print(f"Error: {e}")


print("Folder flattening and merging completed.")
