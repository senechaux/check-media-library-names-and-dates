import os
import re
import argparse
import json
from datetime import datetime

def check_photos_uploaded_to_gphotos(dir, logs_dir):
    albums_with_counter = {}
    albums_with_images = {}
    valid_file = re.compile(r'(?P<year>[0-9]{4}).+$')

    for folder_name, subfolders, filenames in os.walk(dir):
        ignored_folder_names = re.compile(r'^.*(En proceso|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos).*$')
        if ignored_folder_names.match(folder_name):
            continue
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            folder_parts = folder_name.replace(dir, '').split('/')
            folder = folder_parts[2]
            year = folder_parts[1]

            # if year != '2000' and year != '2001':
            #     continue
            # if folder != "2000 Santander - Papa y Mama":
            #     continue

            if not year in albums_with_counter:
                albums_with_counter[year] = {}
            if not folder in albums_with_counter[year]:
                albums_with_counter[year][folder] = 0
            else:
                albums_with_counter[year][folder] += 1


            if not year in albums_with_images:
                albums_with_images[year] = {}
            if not folder in albums_with_images[year]:
                albums_with_images[year][folder] = []
            albums_with_images[year][folder].append(filename)
    
    years = sorted(albums_with_counter.keys())
    sorted_albums_with_counter = {}
    for year in years:
        sorted_albums_with_counter[year] = dict(sorted(albums_with_counter[year].items()))
    with open(f'albums_in_folder_with_counter.json', 'w') as file:
        file.write(json.dumps(sorted_albums_with_counter, indent=4))

    years = sorted(albums_with_images.keys())
    sorted_albums_with_images = {}
    for year in years:
        sorted_albums_with_images[year] = dict(sorted(albums_with_images[year].items()))

    for year in years:
        folders_by_year = sorted_albums_with_images[year].keys()
        for folder_by_year in folders_by_year:
            sorted_albums_with_images[year][folder_by_year] = sorted(sorted_albums_with_images[year][folder_by_year])

    with open(f'albums_in_folder_with_images.json', 'w') as file:
        file.write(json.dumps(sorted_albums_with_images, indent=4))


def main():
    parser = argparse.ArgumentParser(description="Dump to two files a JSON representing the structure of files and folders.")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    args = parser.parse_args()

    dir = args.dir

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_files-and-folders-structure-dumper'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    check_photos_uploaded_to_gphotos(dir, logs_dir)


if __name__ == "__main__":
    main()
