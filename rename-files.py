import os
import re
import argparse
from datetime import datetime


def rename_files(dir, logs_dir, do_rename=False):
    jpeg_extension_pattern = re.compile(r'^(?P<name>.+)\.(?P<extension>jpeg)$')
    uppercase_extension_pattern = re.compile(r'^(?P<name>.+)\.(?P<extension>[A-Z]+)$')

    jpeg_extension_counter = 0
    uppercase_extension_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            uppercase_extension_new_filename = filename
            uppercase_extension_pattern_match = uppercase_extension_pattern.match(filename)
            if uppercase_extension_pattern_match:
                uppercase_extension_counter += 1
                matched_groups = uppercase_extension_pattern_match.groupdict()
                uppercase_extension_new_filename = matched_groups['name'] + "." + matched_groups['extension'].lower()

            jpeg_extension_new_filename = uppercase_extension_new_filename
            jpeg_extension_pattern_match = jpeg_extension_pattern.match(uppercase_extension_new_filename)
            if jpeg_extension_pattern_match:
                jpeg_extension_counter += 1
                matched_groups = jpeg_extension_pattern_match.groupdict()
                jpeg_extension_new_filename = matched_groups['name'] + ".jpg"

            with open(f'{logs_dir}/rename_files.log', 'a') as file:
                file.write(f'{filename} -> {jpeg_extension_new_filename}\n')
            if do_rename:
                os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, jpeg_extension_new_filename))

    print("Count of jpeg extensions: {}".format(jpeg_extension_counter))
    print("Count of uppercase extensions: {}".format(uppercase_extension_counter))


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    parser.add_argument("--do_rename", action="store_true", help="Do not rename files, log changes")
    args = parser.parse_args()

    dir = args.dir
    do_rename = args.do_rename

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_rename_files'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    rename_files(dir, logs_dir, do_rename)

if __name__ == "__main__":
    main()
