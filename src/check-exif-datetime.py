import os
import re
import argparse
import math
import common_functions
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime


def write_log_exif_datetime_videos(log_filename, dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference):
    with open(log_filename, "a") as f:
        f.write(f"{full_filename.replace(dir, '')}\n")
        if tag_date != None:
            f.write(f"tag_date                             = {tag_date}\n")
        if tag_com_apple_quicktime_creationdate != None:
            f.write(f"tag_com_apple_quicktime_creationdate = {tag_com_apple_quicktime_creationdate}\n")
        if tag_creation_time != None:
            f.write(f"tag_creation_time                    = {tag_creation_time}\n")
        f.write(f"filename_time                        = {filename_time}\n")
        f.write(f"difference_in_days: {str(difference_in_days)}\n")
        f.write(f"time_difference: {str(time_difference)}\n")
        f.write("\n")


def check_exif_datetime_images(dir, logs_dir, do_rename=False):
    count_of_jpg_images = common_functions.count_files_with_the_extension(dir, 'jpg')
    print(f'Count of jpg images: {count_of_jpg_images}')

    extensions = "jpg|png|gif|bmp"
    extension_regex = r'\.(?P<extension>'+extensions+')'
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = r"(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    valid_image_filename_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?'+extension_regex+'$')
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    not_valid_files_extention = re.compile(r'^.+\.(eps|ai|mp3|itm|txt|aup|m4a|7z|xml|wav|nmea|pdf|tif|gpx|mcf|svg)$')
    other_images_extension = re.compile(r'^.+\.(bmp|png|gif)$')
    images_counter = 0

    for folder_name, subfolders, filenames in os.walk(dir):
        ignored_folder_names = re.compile(r'^.*(En proceso|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos).*$')
        if ignored_folder_names.match(folder_name):
            continue
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized" or videos_pattern.match(filename) \
                or not_valid_files_extention.match(filename) or other_images_extension.match(filename):
                continue

            full_filename = os.path.join(folder_name, filename)
            pattern_match = valid_image_filename_pattern.match(filename)
            if not pattern_match:
                continue

            images_counter += 1
            if images_counter % 100 == 0:
                print(f"{images_counter}/{count_of_jpg_images}")

            matched_groups = pattern_match.groupdict()

            datetime_from_filename = "{}:{}:{} {}:{}:{}".format(matched_groups['year'], matched_groups['month'], matched_groups['day'], matched_groups['hour'], matched_groups['minutes'], matched_groups['seconds'])
            try:
                date_time_original = ''
                date_time_digitized = ''
                datetime_original_tag = None
                datetime_digitized_tag = None
                image = Image.open(os.path.join(folder_name, filename))
                exif_data = image._getexif()
                for tag, value in exif_data.items():
                    tag_name = TAGS.get(tag, tag)
                    if tag_name == 'DateTimeOriginal':
                        datetime_original_tag = tag
                        date_time_original = value
                    if tag_name == 'DateTimeDigitized':
                        datetime_digitized_tag = tag
                        date_time_digitized = value
                if datetime_from_filename != date_time_original: # or datetime_from_filename != date_time_digitized:
                    format_string = "%Y:%m:%d %H:%M:%S"
                    date_object_from_filename = datetime.strptime(datetime_from_filename, format_string)
                    date_object_from_exif = datetime.strptime(date_time_original, format_string)
                    time_difference = date_object_from_filename - date_object_from_exif
                    difference_in_hours = math.floor(abs(time_difference.total_seconds() / 3600))

                    new_filename = "diff_datetime " + filename
                    if do_rename:
                        os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                    with open(f'{logs_dir}/exif_date_different_from_filename_date.log', 'a') as file:
                        file.write('file: ' + full_filename.replace(dir, '') + "\n")
                        file.write('datetime_from_file : '+datetime_from_filename + "\n")
                        file.write('date_time_original : '+date_time_original + "\n")
                        file.write('date_time_digitized: '+date_time_digitized + "\n")
            except Exception as e:
                new_filename = "exif_getting_error " + filename
                if do_rename:
                    os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                with open(f'{logs_dir}/exif_getting_error.log', 'a') as file:
                    file.write('file: ' + filename + "\n")
                    file.write("Error on file: " + full_filename.replace(dir, '') + " - " + str(e) + "\n")


def check_exif_datetime_videos(dir, logs_dir, do_rename=False):
    count_of_mp4_videos = common_functions.count_files_with_the_extension(dir, 'mp4')
    print(f'Count of mp4 videos: {count_of_mp4_videos}')

    ignored_folder_names = re.compile(r'^.*(En proceso|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos).*$')
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = r"(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    videos_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+r'( .+)?\.(mp4|mov)$')
    renamed_videos_pattern = re.compile(r'^(equal_with_different_timezone_to_change) '+yyyymmdd_hyphens+' '+hhmmss_dots+r'( .+)?\.(mp4|mov)$')
    videos_counter = 0
    renamed_videos_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        if ignored_folder_names.match(folder_name):
            continue
        for filename in filenames:
            full_filename = os.path.join(folder_name, filename)

            pattern_match = videos_pattern.match(filename)
            if not pattern_match:
                continue
            videos_counter += 1
            if videos_counter % 10 == 0:
                print(f'{videos_counter}/{count_of_mp4_videos}')

            matched_groups = pattern_match.groupdict()
            tag_creation_time = None
            tag_date = None
            tag_com_apple_quicktime_creationdate = None
            filename_time = "{}-{}-{}T{}:{}:{}.000000Z".format(matched_groups['year'], matched_groups['month'], matched_groups['day'], matched_groups['hour'], matched_groups['minutes'], matched_groups['seconds'])
            video_metadata = common_functions.get_video_metadata(full_filename)
            if not video_metadata:
                with open(f'{logs_dir}/videos_diff_no_metadata.log', "a") as f:
                    f.write(f"{full_filename.replace(dir, '')}\n")
                continue

            for key, value in video_metadata.items():
                if key == 'creation_time':
                    tag_creation_time = value
                if key == 'date':
                    tag_date = value
                if key == 'com.apple.quicktime.creationdate':
                    tag_com_apple_quicktime_creationdate = value
            if tag_creation_time == None:
                if do_rename:
                    new_filename = "diff_datetime " + filename
                    os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                with open(f'{logs_dir}/videos_no_tag_creation_time.log', 'a') as f:
                    f.write(f"{full_filename.replace(dir, '')}\n")
                continue

            format_string = "%Y-%m-%dT%H:%M:%S.%fZ"
            date_object_from_filename = datetime.strptime(tag_creation_time, format_string)
            date_object_from_exif = datetime.strptime(filename_time, format_string)
            if date_object_from_filename < date_object_from_exif:
                time_difference = date_object_from_exif - date_object_from_filename
            else:
                time_difference = date_object_from_filename - date_object_from_exif
            
            difference_in_seconds = math.floor(abs(time_difference.total_seconds()))
            difference_in_minutes = math.floor(abs(time_difference.total_seconds() / 60))
            difference_in_hours = math.floor(abs(time_difference.total_seconds() / 3600))
            difference_in_days = math.floor(abs(time_difference.total_seconds() / 3600 / 24))

            if difference_in_hours == 1 or difference_in_hours == 2:
                write_log_exif_datetime_videos(f'{logs_dir}/videos_diff_OK_because_of_timezone.log', dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            else:
                new_filename = "diff_datetime " + filename
                if do_rename:
                    os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                write_log_exif_datetime_videos(f'{logs_dir}/videos_diff_KO.log', dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)


def main():
    parser = argparse.ArgumentParser(description="Check all files recursively and check if the datetime in their name matches the datetime in Exif data")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    parser.add_argument("--do_rename", action="store_true", help="Do not rename files, log changes")
    args = parser.parse_args()

    dir = args.dir
    do_rename = args.do_rename

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_check_filenames'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    check_exif_datetime_images(dir, logs_dir, do_rename)
    check_exif_datetime_videos(dir, logs_dir, do_rename)

    if do_rename:
        print("Files with differences have been renamed to have the preffix 'diff_datetime' or 'exif_getting_error'")


if __name__ == "__main__":
    main()
