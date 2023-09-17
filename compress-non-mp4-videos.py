import os
import re
import argparse
import subprocess
import math
import json
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime


def get_all_video_filenames(dir):
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    video_filenames = {}

    for folder_name, subfolders, filenames in os.walk(dir):
        for filename in filenames:
            if not videos_pattern.match(filename):
                continue

            video_filenames[filename] = os.path.join(folder_name, filename)
    
    return video_filenames


def get_numeric_prefix(line):
    starting_number_pattern = re.compile(r'^(?P<number>\d+(\.\d+)).*$')
    starting_number_pattern_match = starting_number_pattern.match(line)
    matched_groups = starting_number_pattern_match.groupdict()

    if starting_number_pattern_match:
        numeric_part = matched_groups['number']
        return float(numeric_part)
    else:
        return 0


def sort_file_by_numeric_prefix(input_file_path, output_file_path, reverse=False):
    with open(input_file_path, 'r') as file:
        lines = file.readlines()
    
    sorted_lines = sorted(lines, key=get_numeric_prefix, reverse=reverse)
    
    with open(output_file_path, 'w') as file:
        for line in sorted_lines:
            file.write(line)


def compress_non_mp4_videos(dir, logs_dir):
    videos_pattern = re.compile(r'^.+\.(?P<video_extension>mp4|avi|mov|mpg|m4v|webm|3gp|wmv|mkv)$')
    for folder_name, subfolders, filenames in os.walk(dir):
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

                if matched_groups['video_extension'] in ['3gp', 'wmv', 'webm', 'mpg', 'mkv', 'm4v', 'avi']:
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
                        with open(f'{logs_dir}/compression_errors.txt', 'a') as file:
                            file.write(handbrake_command)
                    else:
                        if not os.path.exists(full_new_filename):
                            with open(f'{logs_dir}/compression_errors_new_file_not_found.txt', 'a') as file:
                                file.write(handbrake_command+"\n")
                        else:
                            new_file_size = os.path.getsize(full_new_filename) / 1048576
                            print(f"Size of original video {filename}: {file_size:.2f} MB")
                            print(f"Size of new video {new_filename}: {new_file_size:.2f} MB")
                            if new_file_size < file_size*0.5 or new_file_size > file_size*1.5:
                                print("ERROR: new file is too big or too small "+new_filename)
                                with open(f'{logs_dir}/too_different_sizes.txt', 'a') as file:
                                    file.write(f"Size of original video {full_filename}: {file_size:.2f} MB\n")
                                    file.write(f"Size of new video {full_new_filename}: {new_file_size:.2f} MB\n")
                            else:
                                with open(f'{logs_dir}/deleted_videos.txt', 'a') as file:
                                    file.write(f"{full_filename}\n")
                                os.remove(full_filename)


def compare_original_video_with_compressed_video(dir, logs_dir, source_dir, destiny_dir):
    original_videos = []
    compressed_videos = []
    for folder_name, subfolders, filenames in os.walk(destiny_dir):
        for filename in filenames:
            if filename.endswith('.mp4'):
                original_videos.append(filename)
    for folder_name, subfolders, filenames in os.walk(destiny_dir):
        for filename in filenames:
            if filename.endswith('.mp4'):
                compressed_videos.append(filename)
    
    video_filenames = get_all_video_filenames(dir)

    num_original_videos = len(original_videos)
    num_compressed_videos = len(compressed_videos)
    if num_original_videos != num_compressed_videos:
        print(f"Error, there are {num_original_videos} original videos and {num_compressed_videos} compressed videos")
        with open(f'{logs_dir}/compare_original_video_with_compressed_video.log', 'a') as f:
            f.write(f"Error, there are {num_original_videos} original videos and {num_compressed_videos} compressed videos\n")


    for original_video in original_videos:
        if not original_video in compressed_videos:
            print(f"Error video '{original_video}' not compressed")
            with open(f'{logs_dir}/compare_original_video_with_compressed_video.log', 'a') as f:
                f.write(f"Error video '{original_video}' not compressed\n")
            continue

        original_full_filename = os.path.join(source_dir, original_video)
        compressed_full_filename = os.path.join(destiny_dir, original_video)
        original_video_size = os.path.getsize(original_full_filename) / 1048576
        compressed_video_size = os.path.getsize(compressed_full_filename) / 1048576
        percentage_of_original_size = os.path.getsize(compressed_full_filename) * 100 / os.path.getsize(original_full_filename)
        with open(f'{logs_dir}/compare_original_video_with_compressed_video.log', 'a') as f:
            f.write(f"{percentage_of_original_size:.2f}% | Video: '{original_video}' size {original_video_size:.2f} MB => {compressed_video_size:.2f} MB\n")
        if percentage_of_original_size > 80:
            with open(f'{logs_dir}/compressed_videos_without_gain.log', 'a') as f:
                f.write(f'rm "{compressed_full_filename}"\n')
        else:
            print(original_video)
            destiny_filename = video_filenames[original_video].replace('.mp4', ' reduced_size.mp4')
            with open(f'{logs_dir}/copy_compressed_videos.sh', 'a') as f:
                f.write(f'rm "{video_filenames[original_video]}"\n')
                f.write(f'cp "{compressed_full_filename}" "{destiny_filename}"\n')

    executable_permission = 0o744
    try:
        os.chmod("logs/copy_compressed_videos.sh", executable_permission)
        print(f"Executable permission added to logs/copy_compressed_videos.sh")
    except FileNotFoundError:
        print(f"File not found: logs/copy_compressed_videos.sh")
    except PermissionError:
        print(f"Permission denied: logs/copy_compressed_videos.sh")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    sort_file_by_numeric_prefix("logs/compare_original_video_with_compressed_video.log", "logs/compare_original_video_with_compressed_video.log")
    print(f'\n\nYou can remove the original videos folder: rm "{source_dir}"\n\n')


def main():
    print("IT MAY NOT WORK, TEST NEEDED")
    return

    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--dir", required=True, help="")
    parser.add_argument("--source", required=True, help="")
    parser.add_argument("--destiny", required=True, help="")
    args = parser.parse_args()

    dir = args.dir
    source_dir = args.source
    destiny_dir = args.destiny

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_check_filenames'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    compress_non_mp4_videos(dir, logs_dir)
    compare_original_video_with_compressed_video(dir, logs_dir, source_dir, destiny_dir)


if __name__ == "__main__":
    main()
