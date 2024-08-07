import subprocess
import shutil
import json


def count_files_with_the_extension(source_dir, extension):
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
    try:
        # Use the shutil.move() function to move the file
        shutil.move(source_file, destination_folder)
        print(f"File '{source_file}' moved to '{destination_folder}' successfully.")
    except FileNotFoundError:
        print(f"File '{source_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def remove_file(file):
    move_file(file, '~/.Trash/')


def get_video_metadata(video_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-print_format", "json", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        metadata = json.loads(result.stdout)["format"]["tags"]
        return metadata
    else:
        print("Error retrieving metadata.")
        return None
