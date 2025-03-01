import os
import re
import argparse
import math
import common_functions
import shutil
from datetime import datetime


def get_video_list(dir, do_look_for_reduced_videos = False):
    video_list = []
    videos_pattern = re.compile(r'^(?P<year>[0-9]{4})-.+\.(?P<video_extension>mp4)$')

    video_counter = 0
    for folder_name, subfolders, filenames in os.walk(dir):
        for filename in filenames:
            if filename == ".DS_Store" or filename == ".localized":
                continue
            if not do_look_for_reduced_videos and "reduced_size" in filename:
                continue
            if do_look_for_reduced_videos and "reduced_size" not in filename:
                continue

            videos_pattern_match = videos_pattern.match(filename)
            if not videos_pattern_match:
                continue

            video_list.append(filename)  

    return video_list

def rename_videos_compressed(videos_compressed_dir, video_list):
    for filename in video_list:
        new_filename = filename.replace(f'.{filename.split('.')[-1]}', f' reduced_size.{filename.split('.')[-1]}')
        print(f'Renaming "{videos_compressed_dir}/{filename}" to "{videos_compressed_dir}/{new_filename}"')
        os.rename(f'{videos_compressed_dir}/{filename}', f'{videos_compressed_dir}/{new_filename}')


def move_videos_compressed(videos_compressed_dir, video_list):
    for filename in video_list:
        filename_with_fullpath_video_filename = f'{filename.replace(' reduced_size', '')}_full_path.txt'
        with open(f'{videos_compressed_dir}/{filename_with_fullpath_video_filename}', 'r') as file:
            fullpath_video_filename = file.read().rstrip()
        fullpath_video_folder = os.path.dirname(fullpath_video_filename)
        if os.path.exists(f'{fullpath_video_folder}/{filename}'):
            print(f'[ERROR] - The video is duplicated in "{videos_compressed_dir}/{filename}" and "{fullpath_video_folder}"')
            continue
        print(f'Moving "{videos_compressed_dir}/{filename}" to "{fullpath_video_folder}"')
        shutil.move(f'{videos_compressed_dir}/{filename}', fullpath_video_folder)
        common_functions.remove_file(f'{videos_compressed_dir}/{filename_with_fullpath_video_filename}')


def move_videos_original(videos_compressed_dir, dest_dir_original_biggest_videos, video_list):
    for filename in video_list:
        filename_with_fullpath_video_filename = f'{filename.replace(' reduced_size', '')}_full_path.txt'
        with open(f'{videos_compressed_dir}/{filename_with_fullpath_video_filename}', 'r') as file:
            fullpath_video_filename = file.read().rstrip()
        if (os.path.exists(f'{dest_dir_original_biggest_videos}/{filename.replace(' reduced_size', '')}')
            and not os.path.exists(fullpath_video_filename)):
            # print(f'Video already moved from "{fullpath_video_filename}" to "{dest_dir_original_biggest_videos}"')
            continue
        if (os.path.exists(f'{dest_dir_original_biggest_videos}/{filename.replace(' reduced_size', '')}')
            and os.path.exists(fullpath_video_filename)):
            print(f'[ERROR] - The video is duplicated in "{fullpath_video_filename}" and "{dest_dir_original_biggest_videos}"')
            continue
        print(f'Moving original "{fullpath_video_filename}" to "{dest_dir_original_biggest_videos}"')
        shutil.move(fullpath_video_filename, dest_dir_original_biggest_videos)


def remove_videos_to_compress(videos_to_compress_dir, video_list):
    for video in video_list:
        print(f'Removing "{videos_to_compress_dir}/{video}"')
        common_functions.remove_file(f'{videos_to_compress_dir}/{video}')
        common_functions.remove_file(f'{videos_to_compress_dir}/{video}_full_path.txt')


def main():
    parser = argparse.ArgumentParser(description="Rename compressed videos. Move them to the original folder. \
        Move the original video to '~/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos videos con bit rate muy alto tmp'.")
    args = parser.parse_args()

    videos_to_compress_dir = '../biggest_videos_to_compress'
    videos_compressed_dir = '../biggest_videos_compressed'
    dest_dir_original_biggest_videos = '/Users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos videos con bit rate muy alto tmp'
    not_reduced_video_list = get_video_list(videos_compressed_dir, False)
    rename_videos_compressed(videos_compressed_dir, not_reduced_video_list)
    print()
    reduced_video_list = get_video_list(videos_compressed_dir, True)
    move_videos_compressed(videos_compressed_dir, reduced_video_list)
    move_videos_original(videos_compressed_dir, dest_dir_original_biggest_videos, reduced_video_list)
    print()
    to_compress_video_list = get_video_list(videos_to_compress_dir, False)
    remove_videos_to_compress(videos_to_compress_dir, to_compress_video_list)
    print()
    print('Using Google Drive web move files in "/Fotitos videos con bit rate muy alto tmp" to "/Fotitos videos con bit rate muy alto"')

if __name__ == "__main__":
    main()
