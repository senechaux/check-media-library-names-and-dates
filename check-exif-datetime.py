import os
import re
import argparse
import subprocess
import math
import json
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime


def get_video_metadata(video_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-print_format", "json", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        metadata = json.loads(result.stdout)["format"]["tags"]
        return metadata
    else:
        print("Error retrieving metadata.")
        return None


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


def check_exif_datetime_images(dir, logs_dir):
    extensions = "jpg|png|gif|bmp"
    extension_regex = '\.(?P<extension>'+extensions+')'
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = "(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    valid_filename_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?'+extension_regex+'$')
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    not_valid_files_extention = re.compile(r'^.+\.(eps|ai|mp3|itm|txt|aup|m4a|7z|xml|wav|nmea|pdf|tif|gpx|mcf|svg)$')
    other_images_extention = re.compile(r'^.+\.(bmp|png|gif)$')
    images_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        ignored_folder_names = re.compile(r'^.*(En proceso|Album Jimena primer año|Album Carmela primer año|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos|2005-01-05 Fiesta de pijamas).*$')
        if ignored_folder_names.match(folder_name):
            continue
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized" or videos_pattern.match(filename) or not_valid_files_extention.match(filename) or other_images_extention.match(filename):
                continue

            full_filename = os.path.join(folder_name, filename)
            pattern_match = valid_filename_pattern.match(filename)
            if not pattern_match:
                continue

            images_counter += 1
            print(images_counter)
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

                    if difference_in_hours < 1: # 1 hour
                        if ' 00:00:00' in datetime_from_filename:
                            with open(f'{logs_dir}/exif_date_different_name_date_01_less_than_one_hour_000000.log', 'a') as file:
                                file.write('file: ' + filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_hour_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_01_less_than_one_hour.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < 24: # 1 day
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_day_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_02_less_than_one_day_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_day_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_02_less_than_one_day.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < (24 * 30): # 1 month
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_month_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_03_less_than_one_month_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_month_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_03_less_than_one_month.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < (24 * 30 * 12): # 1 year
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_year_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_04_less_than_one_year_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_year_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open(f'{logs_dir}/exif_date_different_name_date_04_less_than_one_year.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    else:
                        new_filename = "diff_more_1_year_to_change " + filename
                        # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                        with open(f'{logs_dir}/exif_date_different_name_date_05_more_than_one_year.log', 'a') as file:
                            file.write('file: ' + new_filename + "\n")
                            file.write('datetime_from_file : '+datetime_from_filename + "\n")
                            file.write('date_time_original : '+date_time_original + "\n")
                            file.write('date_time_digitized: '+date_time_digitized + "\n")
            except Exception as e:
                new_filename = "exif_getting_error " + filename
                # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                with open(f'{logs_dir}/exif_getting_error.log', 'a') as file:
                    file.write('file: ' + new_filename + "\n")
                    file.write("Error on file: " + full_filename.replace(dir, '') + " - " + str(e) + "\n")


def check_exif_datetime_videos(dir, logs_dir):
    # 250 videos / 15 sec => 0,064 sec / video => 340 sec / 5300 videos
    ignored_folder_names = re.compile(r'^.*(En proceso|Album Jimena primer año|Album Carmela primer año|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos|2005-01-05 Fiesta de pijamas).*$')
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = "(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    videos_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?\.(mp4|mov)$')
    renamed_videos_pattern = re.compile(r'^(equal_with_different_timezone_to_change) '+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?\.(mp4|mov)$')
    videos_counter = 0
    renamed_videos_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        if ignored_folder_names.match(folder_name):
            continue
        for filename in filenames:
            full_filename = os.path.join(folder_name, filename)

            # if renamed_videos_pattern.match(filename):
            #     new_filename = filename.replace('equal_with_different_timezone_to_change ', 'equal_with_different_timezone_changed ')
            #     print('renaming to ' + new_filename)
            #     os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))            
            # continue
            
            pattern_match = videos_pattern.match(filename)
            if not pattern_match:
                continue
            videos_counter += 1
            print("\nvideos_counter: " + str(videos_counter))
            print(filename)

            # videos_diff_00_hour_because_of_timezone_so_are_equal = []
            # with open(f'{logs_dir}/logs_video_analysis_second_pass/videos_diff_00_hour_because_of_timezone_so_are_equal.log', 'r') as file:
            #     for line in file:
            #         videos_diff_00_hour_because_of_timezone_so_are_equal.append(line.strip())
            # if full_filename.replace(dir, '') in videos_diff_00_hour_because_of_timezone_so_are_equal:
            #     continue
            #     new_filename = 'equal_with_different_timezone_to_change ' + filename
            #     print('renaming to ' + new_filename)
            #     os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
            # continue

            matched_groups = pattern_match.groupdict()
            tag_creation_time = None
            tag_date = None
            tag_com_apple_quicktime_creationdate = None
            filename_time = "{}-{}-{}T{}:{}:{}.000000Z".format(matched_groups['year'], matched_groups['month'], matched_groups['day'], matched_groups['hour'], matched_groups['minutes'], matched_groups['seconds'])
            video_metadata = get_video_metadata(full_filename)
            if not video_metadata:
                with open(f'{logs_dir}/videos_diff_no_metadata.log', "a") as f:
                    f.write(f"{full_filename.replace(dir, '')}\n")
                continue
            # continue

            for key, value in video_metadata.items():
                if key == 'creation_time':
                    tag_creation_time = value
                if key == 'date':
                    tag_date = value
                if key == 'com.apple.quicktime.creationdate':
                    tag_com_apple_quicktime_creationdate = value
            if tag_creation_time == None:
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
            
            print("time_difference: " + str(time_difference))
            difference_in_seconds = math.floor(abs(time_difference.total_seconds()))
            difference_in_minutes = math.floor(abs(time_difference.total_seconds() / 60))
            difference_in_hours = math.floor(abs(time_difference.total_seconds() / 3600))
            difference_in_days = math.floor(abs(time_difference.total_seconds() / 3600 / 24))

            if difference_in_hours == 1 or difference_in_hours == 2:
                write_log_exif_datetime_videos("logs/videos_diff_00_hour_because_of_timezone_so_are_equal.log", dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_seconds == 0:
                write_log_exif_datetime_videos("logs/videos_diff_01_equal_with_different_timezone_so_are_wrong.log", dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_days < 1:
                write_log_exif_datetime_videos("logs/videos_diff_02_less_1_day.log", dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_days < 365:
                write_log_exif_datetime_videos("logs/videos_diff_03_less_1_year.log", dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            else:
                write_log_exif_datetime_videos("logs/videos_diff_04_more_1_year.log", dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)


def main():
    print("IT MAY NOT WORK, TEST NEEDED")
    return

    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    args = parser.parse_args()

    dir = args.dir

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_check_filenames'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    check_exif_datetime_images(dir, logs_dir)
    check_exif_datetime_videos(dir, logs_dir)


if __name__ == "__main__":
    main()
