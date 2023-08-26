import os
import re
import argparse
import subprocess
import math
import json
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

# TODO 
# estimate date for "Fotos antiguas" and "Yo de peque"
# change EXIF data based on filename for videos
# DONE
# rename ny by ñ
# rename folders like 2001-02-03 (4-5) to 2001-02-03 (04-05)
# extension to lowercase
# extension jpeg to jpg
# convert videos to mp4
# change EXIF data based on filename for images

def remove_log_files():
    directorio = "logs"

    for file in os.listdir(directorio):
        if file.endswith(".log"):
            filename = os.path.join(directorio, file)
            os.remove(filename)
            print(f"Removed file: {filename}")

def check_file_names(root_dir):
    extensions = "jpg|JPG|jpeg|png|gif|bmp|HEIC|mp4|avi|AVI|mov|MOV|mpg|m4v|webm|3gp|wmv|mkv|wav|m4a"
    extension_regex = '\.(?P<extension>'+extensions+')'
    yyyymmdd = "(?P<year>[0-9]{4})(?P<month>0[1-9]|1[0-2])(?P<day>[0-2][0-9]|3[01])"
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss = "(?P<hour>[0-2][0-9])(?P<minutes>[0-5][0-9])(?P<seconds>[0-5][0-9])"
    hhmmss_hyphens = "(?P<hour>[0-2][0-9])-(?P<minutes>[0-5][0-9])-(?P<seconds>[0-5][0-9])"
    hhmmss_dots = "(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    valid_filename_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?'+extension_regex+'$')
    invalid_filename_patterns = [
        # 00 -> 2794 --> filename does not start with a year, i.e.: descenso.jpg or 13.jpg
        re.compile(r'^(?![0-9]{4}).*\.(?:'+extensions+')$'),
        # 01 -> 479 --> 2016-02-28 11.22.592.jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_dots+'(?P<extra_info>[0-9a-zA-Z ]*)'+extension_regex+'$'),
        # 02 -> 15167 --> 2003-02-23 (10-15-04) Los delicuentes- Angel.jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]\('+hhmmss_hyphens+'\)[ _-]?(?P<extra_info>[a-zA-Z0-9\(\)]*)?'+extension_regex+'$'),
        # 03 -> 13356 --> 2004-07-03_19-27-48.avi
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_hyphens+extension_regex+'$'),
        # 04 -> 1350 --> 2012-02-18_11.55.20-1.jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_dots+'[ _-](?P<extra_info>\d{1})'+extension_regex+'$'),
        # 05 -> 2428 --> 2011-12-16-01-11-18_x264.avi
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_hyphens+'[ _-](?P<extra_info>.+)'+extension_regex+'$'),
        # 06 -> 472 --> 2004-03-20_11-02-00l.jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_hyphens+'(?P<extra_info>.+)'+extension_regex+'$'),
        # 07 -> 58 --> 2004-05-15 (15-37-14l).jpg
        re.compile(r'^'+yyyymmdd_hyphens+' \('+hhmmss_hyphens+'(?P<extra_info>.+)\)'+extension_regex+'$'),
        # 08 -> 78 --> 2003-07-01 (11.08.47).jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]\('+hhmmss_dots+'(?P<extra_info>.*)\)'+extension_regex+'$'),
        # 09 -> 439 --> 2017-05-07 17.00.00_36.jpeg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]'+hhmmss_dots+'[ _-](?P<extra_info>.+)'+extension_regex+'$'),
        # 10 -> 578 --> 2007-04-06 (18-33-00)-Voltereta en la arena-c.avi
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-]\('+hhmmss_hyphens+'\)[ _-](?P<extra_info>.+)'+extension_regex+'$'),
        # 11 -> 783 --> 2004-08-02 Mari Ca lucia luciaate.mpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-](?P<extra_info>[a-zA-Z\(].+)'+extension_regex+'$'),
        # 12 -> 186 --> 2004-12-18 26.jpg
        re.compile(r'^'+yyyymmdd_hyphens+'[ _-](?P<extra_info>\d{2,3}|[a-z])'+extension_regex+'$'),
        # 13 -> 108 --> 2005-12-23 04 fatima.jpg
        re.compile(r'^'+yyyymmdd_hyphens+' (?P<extra_info>(\d{2}|-) [a-zA-Z].*)'+extension_regex+'$'),
        # 14 -> 143 --> 1996-08 34_Guernika Pais Vasco.jpg
        re.compile(r'^(?P<year>19[0-9]{2}|20[0-9]{2})[ _-](?P<month>0[1-9]|1[0-2])[ _-](?P<extra_info>.*)'+extension_regex+'$'),
        # 15 -> 508 --> 2004 Dubrovnik-2.jpg
        re.compile(r'^(?P<year>19[0-9]{2}|20[0-9]{2})[ _-](?P<extra_info>[ ,0-9a-zA-Z\(\)-_]+)'+extension_regex+'$'),
        # 16 -> 112 --> Not recognized extensions
        re.compile(r'^.+\.(tif|xml|psd|mov_gs1|mov_gs2|mov_gs3|mov_gs4|txt|mcf|asf|xptv|eps|svg|pdf|ai|vob|VOB|IFO|BUP|7z|thm|mp3|url|rss|wlmp|tmp|nmea|itm|gpx|xcf|db|aup|localized)$'),
    ]
    invalid_files_rest_of_cases = []
    invalid_files = [[] for _ in range(len(invalid_filename_patterns))]

    for folder_name, subfolders, filenames in os.walk(root_dir):
        ignored_folder_names = re.compile(r'^.*(En proceso|Album Jimena primer año|Album Carmela primer año|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos).*$')
        if ignored_folder_names.match(folder_name):
            continue

        # folder_yyyymmdd = ""
        # folder_pattern = re.compile(r'.*\/\d{4}\/'+yyyymmdd_hyphens+'.*')
        # folder_pattern_match = folder_pattern.match(folder_name)
        # if folder_pattern_match:
        #     matched_groups = folder_pattern_match.groupdict()
        #     folder_yyyymmdd = "{}-{}-{}".format(matched_groups['year'], matched_groups['month'], matched_groups['day'])
        #     # print(folder_name)
        #     # print(matched_groups)
        # else:
        #     # print(f"Folder not matched {folder_name}")
        #     folder_pattern = re.compile(r'.*\/L\/\(L\) '+yyyymmdd_hyphens+'.*')
        #     folder_pattern_match = folder_pattern.match(folder_name)
        #     if folder_pattern_match:
        #         matched_groups = folder_pattern_match.groupdict()
        #         folder_yyyymmdd = "{}-{}-{}".format(matched_groups['year'], matched_groups['month'], matched_groups['day'])
        #     else:
        #         folder_pattern = re.compile(r'.*\/L\/\(L\) (?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2]).*')
        #         folder_pattern_match = folder_pattern.match(folder_name)
        #         if folder_pattern_match:
        #             matched_groups = folder_pattern_match.groupdict()
        #             folder_yyyymmdd = "{}-{}-01".format(matched_groups['year'], matched_groups['month'])

        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized" or valid_filename_pattern.match(filename):
                continue

            matched = False
            for index, invalid_filename_pattern in enumerate(invalid_filename_patterns):
                pattern_match = invalid_filename_pattern.match(filename)
                if not pattern_match:
                    continue

                matched = True
                matched_groups = pattern_match.groupdict()
                new_filename = ''
                extra_info = ""
                if 'year' in matched_groups and 'month' in matched_groups and 'day' in matched_groups and 'hour' in matched_groups and 'minutes' in matched_groups and 'seconds' in matched_groups and 'extension' in matched_groups:
                    if 'extra_info' in matched_groups:
                        extra_info = " "+matched_groups['extra_info']
                    new_filename = "{}-{}-{} {}.{}.{}{}.{}".format(matched_groups['year'], matched_groups['month'], matched_groups['day'], matched_groups['hour'], matched_groups['minutes'], matched_groups['seconds'], extra_info, matched_groups['extension'])
                    new_filename = new_filename.replace(" ."+matched_groups['extension'], "."+matched_groups['extension'])
                elif 'year' in matched_groups and 'month' in matched_groups and 'day' in matched_groups and 'extension' in matched_groups:
                    if 'extra_info' in matched_groups:
                        extra_info = " "+matched_groups['extra_info']
                    new_filename = "{}-{}-{} 00.00.00{}.{}".format(matched_groups['year'], matched_groups['month'], matched_groups['day'], extra_info, matched_groups['extension'])
                    new_filename = new_filename.replace(" ."+matched_groups['extension'], "."+matched_groups['extension'])
                elif 'year' in matched_groups and 'month' in matched_groups and 'extension' in matched_groups:
                    if 'extra_info' in matched_groups:
                        extra_info = " "+matched_groups['extra_info']
                    new_filename = "{}-{}-01 00.00.00{}.{}".format(matched_groups['year'], matched_groups['month'], extra_info, matched_groups['extension'])
                    new_filename = new_filename.replace(" ."+matched_groups['extension'], "."+matched_groups['extension'])
                elif 'year' in matched_groups and 'extension' in matched_groups:
                    if 'extra_info' in matched_groups:
                        extra_info = " "+matched_groups['extra_info']
                    new_filename = "{}-01-01 00.00.00{}.{}".format(matched_groups['year'], extra_info, matched_groups['extension'])
                    new_filename = new_filename.replace(" ."+matched_groups['extension'], "."+matched_groups['extension'])
                # elif not folder_yyyymmdd == "":
                #     new_filename = folder_yyyymmdd + " 00.00.00 " + filename

                new_filename = new_filename.replace(" -", " ").replace(" _", " ").replace("..", ".").replace(" .", ".").replace("  ", " ")

                if new_filename == '':
                    invalid_files[index].append(os.path.join(folder_name, filename))
                else:
                    # invalid_files[index].append(filename + " -> " + new_filename)
                    invalid_files[index].append(os.path.join(folder_name, filename) + " -> " + new_filename)
                    if index in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]:
                        print(filename+" -> "+new_filename)
                        # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                break

            if not matched:
                logged_filename = os.path.join(folder_name, filename)
                invalid_files_rest_of_cases.append(logged_filename)
                #print(f"Invalid filename: {filename} path: {logged_filename.replace(root_dir, '')}")
                print(f"Invalid filename: {filename}")


    for index, invalid_file_case in enumerate(invalid_files):
        if index < 10:
            log_filename = f"invalid_case_0{index}.log"
        else:
            log_filename = f"invalid_case_{index}.log"
        if len(invalid_file_case) == 0: continue
        with open(f"logs/{log_filename}", "w") as f:
            for filename in invalid_file_case:
                filename_logged = filename.replace(root_dir, "")
                f.write(f"{filename_logged}\n")

    with open("logs/invalid_files_rest_of_cases.log", "w") as f:
        for filename in invalid_files_rest_of_cases:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

    for index, invalid_file_case in enumerate(invalid_files):
        print(f"Count of case {index} files: {len(invalid_file_case)}")

    print(f"Count of rest of files: {len(invalid_files_rest_of_cases)}")

def rename_uppercase_extensions(root_dir):
    uppercase_extension_pattern = re.compile(r'^(?P<name>.+)\.(?P<extension>[A-Z]+)$')

    counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue
        
            uppercase_extension_pattern_match = uppercase_extension_pattern.match(filename)
            if uppercase_extension_pattern_match:
                counter += 1
                matched_groups = uppercase_extension_pattern_match.groupdict()
                new_filename = matched_groups['name'] + "." + matched_groups['extension'].lower()
                print(filename + " -> " + new_filename)
                # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))

    print("Count of uppercase extensions: {}".format(counter))

def rename_jpeg_extensions(root_dir):
    uppercase_extension_pattern = re.compile(r'^(?P<name>.+)\.(?P<extension>jpeg)$')

    counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            uppercase_extension_pattern_match = uppercase_extension_pattern.match(filename)
            if uppercase_extension_pattern_match:
                counter += 1
                matched_groups = uppercase_extension_pattern_match.groupdict()
                new_filename = matched_groups['name'] + ".jpg"
                print(filename + " -> " + new_filename)
                # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))

    print("Count of jpeg extensions: {}".format(counter))

def rename_special_chars(root_dir):
    special_chars_pattern = re.compile(r'^.+--.+\.(?P<extension>.+)$')

    counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            special_chars_pattern_match = special_chars_pattern.match(filename)
            if special_chars_pattern_match:
                counter += 1
                matched_groups = special_chars_pattern_match.groupdict()
                new_filename = ""
                print(filename + " -> " + new_filename)
                # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))

    print("Count of uppercase extensions: {}".format(counter))

def find_videos(root_dir):
    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    images_pattern = re.compile(r'^.+\.(?P<image_extension>jpg|jpeg|png|gif|bmp)$')
    any_file_pattern = re.compile(r'^.+\.(?P<extension>.+)$')

    video_extensions = set()
    image_extensions = set()
    any_file_extensions = set()
    counter_videos_per_extension = {}
    counter_images_per_extension = {}
    counter_any_files_per_extension = {}
    counter_videos_per_year = {}

    video_counter = 0
    image_counter = 0
    any_file_counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
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
                counter_videos_per_extension[matched_groups['video_extension']] += 1
                if matched_groups['year'] not in counter_videos_per_year:
                    counter_videos_per_year[matched_groups['year']] = 0
                counter_videos_per_year[matched_groups['year']] += 1
                # if matched_groups['video_extension'] == '3gp':
                #     print(filename)
            elif images_pattern_match:
                image_counter += 1
                matched_groups = images_pattern_match.groupdict()
                image_extensions.add(matched_groups['image_extension'])
                if matched_groups['image_extension'] not in counter_images_per_extension:
                    counter_images_per_extension[matched_groups['image_extension']] = 0
                counter_images_per_extension[matched_groups['image_extension']] += 1
            elif any_file_pattern_match:
                any_file_counter += 1
                matched_groups = any_file_pattern_match.groupdict()
                any_file_extensions.add(matched_groups['extension'])
                if matched_groups['extension'] not in counter_any_files_per_extension:
                    counter_any_files_per_extension[matched_groups['extension']] = 0
                counter_any_files_per_extension[matched_groups['extension']] += 1

    print("Count of videos: {}".format(video_counter))
    print("Count of mp4 videos: {}".format(counter_videos_per_extension['mp4']))
    print("Count of images: {}".format(image_counter))
    print("Count of other files: {}".format(any_file_counter))
    print("Video extensions: ")
    print(video_extensions)
    print("Image extensions: ")
    print(image_extensions)
    print("Other files extensions: ")
    print(any_file_extensions)
    print("Count of videos per extension: ")
    print(counter_videos_per_extension)
    print("Count of videos per year: ")
    print(dict(sorted(counter_videos_per_year.items(), key=lambda item: item[0])))
    percentage_videos_per_year = counter_videos_per_year
    for key in percentage_videos_per_year:
        percentage_videos_per_year[key] = str(round(percentage_videos_per_year[key] * 100 / counter_videos_per_extension['mp4']))+"%"
    print("Percentage of videos per year: ")
    print(dict(sorted(percentage_videos_per_year.items(), key=lambda item: item[0])))
    print("Count of images per extension: ")
    print(counter_images_per_extension)
    print("Count of rest of files per extension: ")
    print(counter_any_files_per_extension)

def log_filenames(root_dir):
    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    images_pattern = re.compile(r'^.+\.(?P<image_extension>jpg|jpeg|png|gif|bmp)$')
    any_file_pattern = re.compile(r'^.+\.(?P<extension>.+)$')

    video_counter = 0
    image_counter = 0
    any_file_counter = 0
    rest_file_counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            videos_pattern_match = videos_pattern.match(filename)
            images_pattern_match = images_pattern.match(filename)
            any_file_pattern_match = any_file_pattern.match(filename)
            if videos_pattern_match:
                video_counter += 1
                with open('logs/video_names.log', 'a') as file:
                    file.write(filename + "\n")
            elif images_pattern_match:
                image_counter += 1
                with open('logs/image_names.log', 'a') as file:
                    file.write(filename + "\n")
            elif any_file_pattern_match:
                any_file_counter += 1
                with open('logs/any_file_names.log', 'a') as file:
                    file.write(filename + "\n")
            else:
                rest_file_counter += 1
                with open('logs/rest_of_file_names.log', 'a') as file:
                    file.write(filename + "\n")

            print("video_counter: " + str(video_counter))
            print("image_counter: " + str(image_counter))
            print("any_file_counter: " + str(any_file_counter))
            print("rest_file_counter: " + str(rest_file_counter))


def compress_videos(root_dir):
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue


            videos_pattern_match = videos_pattern.match(filename)
            if videos_pattern_match:
                matched_groups = videos_pattern_match.groupdict()
                new_filename = filename.replace("."+matched_groups['video_extension'], ".mp4")
                full_filename = os.path.join(folder_name, filename)
                full_new_filename = os.path.join(folder_name, new_filename)
                if os.path.exists(full_new_filename):
                    continue

                if matched_groups['video_extension'] in ['mov']: # todo  # done 3gp wmv webm mpg mkv m4v avi
                    file_size = os.path.getsize(full_filename) / 1048576                    
                    print(full_filename)
                    mediainfo_command = 'mediainfo --Inform="Video;%Width% %Height%" "'+full_filename+'"'
                    result = subprocess.run(mediainfo_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    width = 0
                    height = 0
                    if result.returncode == 0:
                        output = result.stdout.replace("\n", "")
                        width_and_height = output.split(' ')
                        width = width_and_height[0]
                        height = width_and_height[1]
                        print(width+"x"+height)
                    else:
                        error = result.stderr
                        print("Error executing mediainfo_command:")
                        print(error)

                    handbrake_command = '/Applications/HandBrakeCLI --input "{}" --output "{}" --width {} --height {} --preset="Fast 720p30"'.format(
                        full_filename,
                        full_new_filename,
                        width,
                        height
                    )
                    print(handbrake_command)
                    print(f"Size of original video {filename}: {file_size:.2f} MB")
                    try:
                        with subprocess.Popen(handbrake_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
                            for line in process.stdout:
                                print(filename + ' '  + line, end='')
                    except subprocess.CalledProcessError as e:
                        with open('compression_errors.txt', 'a') as file:
                            file.write(handbrake_command)
                    else:
                        if not os.path.exists(full_new_filename):
                            with open('compression_errors_new_file_not_found.txt', 'a') as file:
                                file.write(handbrake_command+"\n")
                        else:
                            new_file_size = os.path.getsize(full_new_filename) / 1048576
                            print(f"Size of original video {filename}: {file_size:.2f} MB")
                            print(f"Size of new video {new_filename}: {new_file_size:.2f} MB")
                            if new_file_size < file_size*0.5 or new_file_size > file_size*1.5:
                                print("ERROR: new file is too big or too small "+new_filename)
                                with open('too_different_sizes.txt', 'a') as file:
                                    file.write(f"Size of original video {full_filename}: {file_size:.2f} MB\n")
                                    file.write(f"Size of new video {full_new_filename}: {new_file_size:.2f} MB\n")
                            else:
                                with open('deleted_videos.txt', 'a') as file:
                                    file.write(f"{full_filename}\n")
                                os.remove(full_filename)

def check_exif_datetime_images(root_dir):
    extensions = "jpg|png|gif|bmp"
    extension_regex = '\.(?P<extension>'+extensions+')'
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = "(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    valid_filename_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?'+extension_regex+'$')
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    not_valid_files_extention = re.compile(r'^.+\.(eps|ai|mp3|itm|txt|aup|m4a|7z|xml|wav|nmea|pdf|tif|gpx|mcf|svg)$')
    other_images_extention = re.compile(r'^.+\.(bmp|png|gif)$')
    images_counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
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
                            with open('logs/exif_date_different_name_date_01_less_than_one_hour_000000.log', 'a') as file:
                                file.write('file: ' + filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_hour_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_01_less_than_one_hour.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < 24: # 1 day
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_day_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_02_less_than_one_day_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_day_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_02_less_than_one_day.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < (24 * 30): # 1 month
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_month_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_03_less_than_one_month_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_month_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_03_less_than_one_month.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    elif difference_in_hours < (24 * 30 * 12): # 1 year
                        if ' 00:00:00' in datetime_from_filename:
                            new_filename = "diff_less_1_year_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_04_less_than_one_year_000000.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                        else:
                            new_filename = "diff_less_1_year_to_change " + filename
                            # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                            with open('logs/exif_date_different_name_date_04_less_than_one_year.log', 'a') as file:
                                file.write('file: ' + new_filename + "\n")
                                file.write('datetime_from_file : '+datetime_from_filename + "\n")
                                file.write('date_time_original : '+date_time_original + "\n")
                                file.write('date_time_digitized: '+date_time_digitized + "\n")
                    else:
                        new_filename = "diff_more_1_year_to_change " + filename
                        # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                        with open('logs/exif_date_different_name_date_05_more_than_one_year.log', 'a') as file:
                            file.write('file: ' + new_filename + "\n")
                            file.write('datetime_from_file : '+datetime_from_filename + "\n")
                            file.write('date_time_original : '+date_time_original + "\n")
                            file.write('date_time_digitized: '+date_time_digitized + "\n")
            except Exception as e:
                new_filename = "exif_getting_error " + filename
                # os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                with open('logs/exif_getting_error.log', 'a') as file:
                    file.write('file: ' + new_filename + "\n")
                    file.write("Error on file: " + full_filename.replace(root_dir, '') + " - " + str(e) + "\n")

def get_video_metadata(video_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-print_format", "json", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        metadata = json.loads(result.stdout)["format"]["tags"]
        return metadata
    else:
        print("Error retrieving metadata.")
        return None

def write_log_exif_datetime_videos(log_filename, root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference):
    with open(log_filename, "a") as f:
        f.write(f"{full_filename.replace(root_dir, '')}\n")
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


def check_exif_datetime_videos(root_dir):
    # 250 videos / 15 sec => 0,064 sec / video => 340 sec / 5300 videos
    ignored_folder_names = re.compile(r'^.*(En proceso|Album Jimena primer año|Album Carmela primer año|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos|2005-01-05 Fiesta de pijamas).*$')
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss_dots = "(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    videos_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?\.(mp4|mov)$')
    renamed_videos_pattern = re.compile(r'^(equal_with_different_timezone_to_change) '+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?\.(mp4|mov)$')
    videos_counter = 0
    renamed_videos_counter = 0
    for folder_name, subfolders, filenames in os.walk(root_dir):
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

            videos_diff_00_hour_because_of_timezone_so_are_equal = []
            with open('logs_video_analysis_second_pass/videos_diff_00_hour_because_of_timezone_so_are_equal.log', 'r') as file:
                for line in file:
                    videos_diff_00_hour_because_of_timezone_so_are_equal.append(line.strip())
            if full_filename.replace(root_dir, '') in videos_diff_00_hour_because_of_timezone_so_are_equal:
                continue
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
                with open('logs/videos_diff_no_metadata.log', "a") as f:
                    f.write(f"{full_filename.replace(root_dir, '')}\n")
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
                with open(f"logs/videos_no_tag_creation_time.log", "a") as f:
                    f.write(f"{full_filename.replace(root_dir, '')}\n")
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
                write_log_exif_datetime_videos("logs/videos_diff_00_hour_because_of_timezone_so_are_equal.log", root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_seconds == 0:
                write_log_exif_datetime_videos("logs/videos_diff_01_equal_with_different_timezone_so_are_wrong.log", root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_days < 1:
                write_log_exif_datetime_videos("logs/videos_diff_02_less_1_day.log", root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            elif difference_in_days < 365:
                write_log_exif_datetime_videos("logs/videos_diff_03_less_1_year.log", root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)
            else:
                write_log_exif_datetime_videos("logs/videos_diff_04_more_1_year.log", root_dir, full_filename, tag_date, tag_com_apple_quicktime_creationdate, tag_creation_time, filename_time, difference_in_days, time_difference)

def main():
    parser = argparse.ArgumentParser(description="Check all files recursively to find those that do not match the desired name structure")
    parser.add_argument("--directory", required=True, help="Directory path to check")
    args = parser.parse_args()

    remove_log_files()

    root_directory = args.directory
    # check_file_names(root_directory)
    # rename_uppercase_extensions(root_directory)
    # rename_jpeg_extensions(root_directory)
    # rename_special_chars(root_directory)
    # find_videos(root_directory)
    # compress_videos(root_directory)
    # check_exif_datetime_images(root_directory)
    # check_exif_datetime_videos(root_directory)
    log_filenames(root_directory)

if __name__ == "__main__":
    main()
