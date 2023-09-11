import os
import re
import argparse
import subprocess
import math
import json
from datetime import datetime
from PIL import Image

def resize_image(input_image_path, output_image_path, target_width):
    try:
        with Image.open(input_image_path) as img:
            # Determine whether the image is portrait or landscape
            width, height = img.size
            if width > height:
                # Landscape image
                new_width = target_width
                new_height = int(height * (target_width / width))
            else:
                # Portrait image or square image
                new_height = target_width
                new_width = int(width * (target_width / height))

            # Resize the image while maintaining aspect ratio
            img.thumbnail((new_width, new_height))

            # Save the resized image
            img.save(output_image_path)
            print(f"Image resized and saved as {output_image_path}")
    except FileNotFoundError:
        print(f"File {input_image_path} not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def resize_video(filename, full_filename, full_new_filename, video_preset, log_prefix):
    file_size = os.path.getsize(full_filename) / 1048576
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

    handbrake_command = '/Applications/HandBrakeCLI --input "{}" --output "{}" --width {} --height {} --preset="{}"'.format(
            full_filename,
            full_new_filename,
            width,
            height,
            video_preset
    )
    print(handbrake_command)
    print(f"Size of original video {filename}: {file_size:.2f} MB")
    try:
        with subprocess.Popen(handbrake_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                print(f"{log_prefix} {filename} {line}", end='')
    except subprocess.CalledProcessError as e:
        with open('logs_copy_to_upload_to_gphotos/compression_errors.log', 'a') as file:
            file.write(handbrake_command)
    else:
        if not os.path.exists(full_new_filename):
            with open('logs_copy_to_upload_to_gphotos/compression_errors_new_file_not_found.log', 'a') as file:
                file.write(handbrake_command+"\n")
        else:
            new_file_size = os.path.getsize(full_new_filename) / 1048576
            print(f"Size of original video {filename}: {file_size:.2f} MB")
            print(f"Size of new video {full_new_filename}: {new_file_size:.2f} MB")
            if new_file_size > file_size:
                print(f"ERROR: new file is bigger {filename}")
                with open('logs_copy_to_upload_to_gphotos/bigger_sizes.log', 'a') as file:
                    file.write(f"Size of original video {full_filename}: {file_size:.2f} MB\n")
                    file.write(f"Size of new video {full_new_filename}: {new_file_size:.2f} MB\n")
            else:
                with open('logs_copy_to_upload_to_gphotos/compressed_videos.log', 'a') as file:
                    file.write(f"{full_filename}\n")


def calculate_count_of_files_with_the_extenstion(source_dir, extension):
    count_command = f"find '{source_dir}' -type f -iname '*.{extension}' | wc -l"
    print(count_command)
    result = subprocess.run(count_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        return result.stdout.replace("\n", "").replace(" ", "")
    else:
        error = result.stderr
        print("Error executing count_command:")
        print(error)
        return 0


def find_and_copy(source_dir, destiny_dir, video_preset):
    total_images = calculate_count_of_files_with_the_extenstion(source_dir, 'jpg')
    total_videos = calculate_count_of_files_with_the_extenstion(source_dir, 'mp4')

    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4)$')
    images_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<image_extension>jpg)$')

    video_counter = 0
    image_counter = 0
    for folder_name, subfolders, filenames in os.walk(source_dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue

            full_filename = os.path.join(folder_name, filename)
            new_folder_name = folder_name.replace(source_dir, destiny_dir)
            if not os.path.exists(new_folder_name):
                os.makedirs(new_folder_name)
            full_new_filename = os.path.join(new_folder_name, filename)

            videos_pattern_match = videos_pattern.match(filename)
            images_pattern_match = images_pattern.match(filename)

            if images_pattern_match:
                image_counter += 1
                target_width = 1200
                resize_image(full_filename, full_new_filename, target_width)

            elif videos_pattern_match:
                video_counter += 1
                resize_video(filename, full_filename, full_new_filename, video_preset, f"images: {image_counter}/{total_images} videos: {video_counter}/{total_videos}")

            print(f"images: {image_counter}/{total_images} videos: {video_counter}/{total_videos}")


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--source", required=True, help="Source directory")
    parser.add_argument("--destiny", required=True, help="Destiny directory")
    parser.add_argument("--video_preset", required=True, help="Handbrake Video preset: veryfast480p | social480p | social360p")
    args = parser.parse_args()

    source_dir = args.source
    destiny_dir = args.destiny
    video_presets = {
        "veryfast480p": "Very Fast 480p30",
        "social480p": "Social 50 MB 10 Minutes 480p30",
        "social360p": "Social 8 MB 3 Minutes 360p30"
    }
    video_preset = video_presets[args.video_preset]
    find_and_copy(source_dir, destiny_dir, video_preset)

if __name__ == "__main__":
    main()
