import os
import re
import argparse
from datetime import datetime


def find_and_count_files(dir, logs_dir, include_dir=False):
    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    images_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<image_extension>jpg|jpeg|png|gif|bmp)$')
    any_file_pattern = re.compile(r'^.+\.(?P<extension>.+)$')

    video_extensions = set()
    image_extensions = set()
    any_file_extensions = set()

    counter_images_per_extension = {}
    counter_images_per_year = {}
    meter_images_per_extension = {}
    meter_images_per_year = {}

    counter_videos_per_extension = {}
    counter_videos_per_year = {}
    meter_videos_per_extension = {}
    meter_videos_per_year = {}

    counter_any_files_per_extension = {}
    meter_any_files_per_extension = {}

    video_counter = 0
    image_counter = 0
    any_file_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            videos_pattern_match = videos_pattern.match(filename)
            images_pattern_match = images_pattern.match(filename)
            any_file_pattern_match = any_file_pattern.match(filename)
            if videos_pattern_match:
                video_counter += 1
                matched_groups = videos_pattern_match.groupdict()
                video_extensions.add(matched_groups['video_extension'])

                if matched_groups['video_extension'] not in counter_videos_per_extension:
                    counter_videos_per_extension[matched_groups['video_extension']] = 0
                    meter_videos_per_extension[matched_groups['video_extension']] = 0
                counter_videos_per_extension[matched_groups['video_extension']] += 1
                meter_videos_per_extension[matched_groups['video_extension']] += os.path.getsize(os.path.join(folder_name, filename))

                if matched_groups['year'] not in counter_videos_per_year:
                    counter_videos_per_year[matched_groups['year']] = 0
                    meter_videos_per_year[matched_groups['year']] = 0
                counter_videos_per_year[matched_groups['year']] += 1
                meter_videos_per_year[matched_groups['year']] += os.path.getsize(os.path.join(folder_name, filename))

                with open(f'{logs_dir}/video_names.log', 'a') as file:
                    file.write((os.path.join(folder_name, filename) if include_dir else filename) + "\n")

            elif images_pattern_match:
                image_counter += 1
                matched_groups = images_pattern_match.groupdict()
                image_extensions.add(matched_groups['image_extension'])

                if matched_groups['image_extension'] not in counter_images_per_extension:
                    counter_images_per_extension[matched_groups['image_extension']] = 0
                    meter_images_per_extension[matched_groups['image_extension']] = 0
                counter_images_per_extension[matched_groups['image_extension']] += 1
                meter_images_per_extension[matched_groups['image_extension']] += os.path.getsize(os.path.join(folder_name, filename))

                if matched_groups['year'] not in counter_images_per_year:
                    counter_images_per_year[matched_groups['year']] = 0
                    meter_images_per_year[matched_groups['year']] = 0
                counter_images_per_year[matched_groups['year']] += 1
                meter_images_per_year[matched_groups['year']] += os.path.getsize(os.path.join(folder_name, filename))

                with open(f'{logs_dir}/image_names.log', 'a') as file:
                    file.write((os.path.join(folder_name, filename) if include_dir else filename) + "\n")

            elif any_file_pattern_match:
                any_file_counter += 1
                matched_groups = any_file_pattern_match.groupdict()
                any_file_extensions.add(matched_groups['extension'])
                if matched_groups['extension'] not in counter_any_files_per_extension:
                    counter_any_files_per_extension[matched_groups['extension']] = 0
                    meter_any_files_per_extension[matched_groups['extension']] = 0
                counter_any_files_per_extension[matched_groups['extension']] += 1
                meter_any_files_per_extension[matched_groups['extension']] += os.path.getsize(os.path.join(folder_name, filename))

                with open(f'{logs_dir}/any_file_names.log', 'a') as file:
                    file.write((os.path.join(folder_name, filename) if include_dir else filename) + "\n")


    with open(f'{logs_dir}/file_counts.log', 'a') as file:
        file.write("Count of videos: {}".format(video_counter) + "\n")
        if 'mp4' in counter_videos_per_extension:
            file.write("Count of mp4 videos: {}".format(counter_videos_per_extension['mp4']) + "\n")
        file.write("Count of images: {}".format(image_counter) + "\n")
        file.write("Count of other files: {}".format(any_file_counter) + "\n")
        file.write("Video extensions: " + "\n")
        file.write(str(video_extensions) + "\n")
        file.write("Image extensions: " + "\n")
        file.write(str(image_extensions) + "\n")
        file.write("Other files extensions: " + "\n")
        file.write(str(any_file_extensions) + "\n")

        file.write("Count of videos per extension: " + "\n")
        for ext in counter_videos_per_extension:
            file.write(f"{ext}: {counter_videos_per_extension[ext]}\n")

        file.write("Count of videos per year: " + "\n")
        counter_videos_per_year_sorted = dict(sorted(counter_videos_per_year.items(), key=lambda item: item[0]))
        for year in counter_videos_per_year_sorted:
            file.write(f"{year}: {counter_videos_per_year_sorted[year]}\n")

        percentage_videos_per_year = counter_videos_per_year
        for key in percentage_videos_per_year:
            percentage_videos_per_year[key] = str(round(percentage_videos_per_year[key] * 100 / counter_videos_per_extension['mp4']))+"%"
        file.write("Percentage of videos per year: " + "\n")
        percentage_videos_per_year_sorted = dict(sorted(percentage_videos_per_year.items(), key=lambda item: item[0]))
        for year in percentage_videos_per_year_sorted:
            file.write(f"{year}: {percentage_videos_per_year_sorted[year]}\n")

        file.write("Count of images per extension: " + "\n")
        for ext in counter_images_per_extension:
            file.write(f"{ext}: {counter_images_per_extension[ext]}\n")

        file.write("Count of images per year: " + "\n")
        counter_images_per_year_sorted = dict(sorted(counter_images_per_year.items(), key=lambda item: item[0]))
        for year in counter_images_per_year_sorted:
            file.write(f"{year}: {counter_images_per_year_sorted[year]}\n")

        percentage_images_per_year = counter_images_per_year
        for key in percentage_images_per_year:
            percentage_images_per_year[key] = str(round(percentage_images_per_year[key] * 100 / counter_images_per_extension['jpg']))+"%"
        file.write("Percentage of images per year: " + "\n")
        percentage_images_per_year_sorted = dict(sorted(percentage_images_per_year.items(), key=lambda item: item[0]))
        for year in percentage_images_per_year_sorted:
            file.write(f"{year}: {percentage_images_per_year_sorted[year]}\n")

        file.write("Count of rest of files per extension: " + "\n")
        for ext in counter_any_files_per_extension:
            file.write(f"{ext}: {counter_any_files_per_extension[ext]}\n")

        file.write("Meter of videos per extension: " + "\n")
        for ext in meter_videos_per_extension:
            size = meter_videos_per_extension[ext] / 1048576
            file.write(f"{ext}: {size:.2f} MB\n")

        meter_videos_per_year = dict(sorted(meter_videos_per_year.items(), key=lambda item: item[0]))
        file.write("Meter of videos per year: " + "\n")
        for ext in meter_videos_per_year:
            size = meter_videos_per_year[ext] / 1048576
            file.write(f"{ext}: {size:.2f} MB\n")

        file.write("Meter of images per extension: " + "\n")
        for ext in meter_images_per_extension:
            size = meter_images_per_extension[ext] / 1048576
            file.write(f"{ext}: {size:.2f} MB\n")

        meter_images_per_year = dict(sorted(meter_images_per_year.items(), key=lambda item: item[0]))
        file.write("Meter of images per year: " + "\n")
        for ext in meter_images_per_year:
            size = meter_images_per_year[ext] / 1048576
            file.write(f"{ext}: {size:.2f} MB\n")

        file.write("Meter of any files per extension: " + "\n")
        for ext in meter_any_files_per_extension:
            size = meter_any_files_per_extension[ext] / 1048576
            file.write(f"{ext}: {size:.2f} MB\n")


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    parser.add_argument("--include_dir", action="store_true", help="Log full path filenames")
    args = parser.parse_args()

    dir = args.dir
    include_dir = args.include_dir

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_find_and_count_files'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    find_and_count_files(dir, logs_dir, include_dir)

if __name__ == "__main__":
    main()
