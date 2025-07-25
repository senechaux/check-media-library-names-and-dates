import os
import re
import argparse
import subprocess
import math
import common_functions
import shutil
from datetime import datetime

MIN_FILE_SIZE_IN_MB = 50

def find_biggest_videos(dir, logs_dir):
    biggest_videos_list = []
    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')

    video_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized" or "reduced_size" in filename:
                continue

            videos_pattern_match = videos_pattern.match(filename)
            if not videos_pattern_match:
                continue

            video_counter += 1
            full_filename = os.path.join(folder_name, filename)
            file_size = os.path.getsize(full_filename)
            file_size_mb = math.floor(file_size / 1000 / 1000)
            if file_size_mb < MIN_FILE_SIZE_IN_MB:
                continue
            mediainfo_command = 'mediainfo --Inform="Video;%BitRate% | %Duration% | %Width%x%Height%" "'+full_filename+'"'
            result = subprocess.run(mediainfo_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            bitrate = 0
            duration_milliseconds = 0
            duration_minutes = 0
            duration_seconds = 0
            if result.returncode == 0:
                output = result.stdout.replace("\n", "")
                output_splitted = output.split(' | ')
                bitrate = round(int(output_splitted[0]) / 1000000, 2) # b/s to Mb/s
                bitrate_splitted = str(bitrate).split('.')
                bitrate = bitrate_splitted[0].rjust(2, "0") + '.' + bitrate_splitted[1].ljust(2, "0")
                duration_milliseconds = output_splitted[1]
                duration_minutes, duration_seconds = common_functions.convert_milliseconds(int(duration_milliseconds))
                duration_minutes = math.floor(duration_minutes)
                duration_seconds = math.floor(duration_seconds)
                width_x_height = output_splitted[2]
            else:
                error = result.stderr
                print("Error executing mediainfo_command:")
                print(error)
            file_size_mb_padded = str(file_size_mb).rjust(4, "0")
            with open(f'{logs_dir}/biggest_videos_by_size.log', 'a') as file:
                file.write(str(file_size_mb_padded) + " MB | " + str(bitrate) + " Mb/s | " + str(duration_minutes) + "m" + str(duration_seconds) + "s | " + width_x_height + " -> " + filename + " " + full_filename + "\n")
            with open(f'{logs_dir}/biggest_videos_by_bitrate.log', 'a') as file:
                file.write(str(bitrate) + " Mb/s | " + str(file_size_mb_padded) + " MB | " + str(duration_minutes) + "m" + str(duration_seconds) + "s | " + width_x_height + " -> " + filename + " " + full_filename + "\n")
            biggest_videos_list.append(full_filename)

    if os.path.exists(f'{logs_dir}/biggest_videos_by_size.log'):
        common_functions.sort_file(f'{logs_dir}/biggest_videos_by_size.log', f'{logs_dir}/biggest_videos_by_size.log', reverse=True)
    if os.path.exists(f'{logs_dir}/biggest_videos_by_bitrate.log'):
        common_functions.sort_file(f'{logs_dir}/biggest_videos_by_bitrate.log', f'{logs_dir}/biggest_videos_by_bitrate.log', reverse=True)
    
    return biggest_videos_list


def copy_biggest_videos_for_compression(videos_list, dest_dir):
    for video in videos_list:
        video_filename = os.path.basename(video)
        if not os.path.exists(f'{dest_dir}/{video_filename}'):
            shutil.copy2(video, dest_dir)


def dump_biggest_videos_full_paths(videos_list, dest_dir, dest_dir_compressed):
    for video in videos_list:
        video_filename = os.path.basename(video)
        if not os.path.exists(f'{dest_dir}/{video_filename}_full_path.txt'):
            with open(f'{dest_dir}/{video_filename}_full_path.txt', 'w') as file:
                file.write(video)
        if not os.path.exists(f'{dest_dir_compressed}/{video_filename}_full_path.txt'):
            with open(f'{dest_dir_compressed}/{video_filename}_full_path.txt', 'w') as file:
                file.write(video)


def main():
    parser = argparse.ArgumentParser(description="Find and copy biggest videos in a folder to \
        ./biggest_videos_to_compress. Also log to an output file biggest videos in a folder.")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    args = parser.parse_args()

    dir = args.dir

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_biggest_videos'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    biggest_videos_list = find_biggest_videos(dir, logs_dir)
    dest_dir = '../biggest_videos_to_compress'
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    dest_dir_compressed = '../biggest_videos_compressed'
    if not os.path.exists(dest_dir_compressed):
        os.makedirs(dest_dir_compressed)
    copy_biggest_videos_for_compression(biggest_videos_list, dest_dir)
    dump_biggest_videos_full_paths(biggest_videos_list, dest_dir, dest_dir_compressed)
    print('Compress videos in ../biggest_videos_to_compress and output them into ../biggest_videos_compressed.')
    print('Check new sizes are small enough.')
    print('Set the correct datetime metadata using "A better finder attributes" and run move_biggest_videos.py')

if __name__ == "__main__":
    main()
