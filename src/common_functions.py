import shutil
import os
from pathlib import Path

from media_library.filesystem import assert_destination
from media_library.legacy import count_extension, video_tags


def count_files_with_the_extension(source_dir, extension):
    # Se conserva texto en éxito para los llamadores históricos; un fallo ya no es cero.
    return str(count_extension(source_dir, extension))


def convert_milliseconds(milliseconds):
    total_seconds = milliseconds / 1000
    minutes = total_seconds / 60
    seconds = total_seconds % 60
    return minutes, seconds


def sort_file(input_file_path, output_file_path, reverse=False):
    with open(input_file_path, 'r') as file:
        lines = file.readlines()
    
    lines.sort(reverse=reverse)
    
    with open(output_file_path, 'w') as file:
        for line in lines:
            file.write(line)


def move_file(source_file, destination_folder):
    destination = Path(destination_folder)
    if destination.is_dir():
        destination = destination / Path(source_file).name
    assert_destination(destination)
    return shutil.move(source_file, destination)


def move_folder(source_folder, destination_folder):
    return move_file(source_folder, destination_folder)


def remove_file(file):
    trash_dir = os.path.expanduser('~/.Trash/')
    return move_file(file, trash_dir)


def remove_folder(folder):
    trash_dir = os.path.expanduser('~/.Trash/')
    return move_folder(folder, trash_dir)


def create_directory_if_not_exists(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def get_video_metadata(video_path):
    return video_tags(video_path)
