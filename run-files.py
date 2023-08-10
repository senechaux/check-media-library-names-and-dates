import os
import re

def check_file_names(root_dir):
    pattern = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]\.(jpg|png|mp4|avi)$')

    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if not pattern.match(filename):
                print(f"Invalid filename: {filename}")

root_directory = ""
check_file_names(root_directory)
