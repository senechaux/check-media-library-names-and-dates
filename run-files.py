import os
import re
import argparse

def check_file_names(root_dir):
    extensions = "jpg|png|mp4|avi|mov|mpg|wav"
    valid_filename_pattern = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]\.('+extensions+')$')
    invalid_filename_pattern_case_1 = re.compile(r'^(?![0-9]{4}).*\.('+extensions+')$')
    invalid_filename_pattern_case_2 = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)\.('+extensions+')$')
    invalid_filename_pattern_case_3 = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)( [a-zA-Z0-9-_ \(\)]+)?\.('+extensions+')$')
    invalid_filename_pattern_case_4 = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[0-2][0-9]-[0-5][0-9]-[0-5][0-9]\.('+extensions+')$')

    invalid_files = []
    invalid_files_case_1 = [] # filename does not start with a year, i.e.: descenso.jpg or 13.jpg
    invalid_files_case_2 = [] # 2004-11-01 (14-50-36).jpg
    invalid_files_case_3 = [] # 2003-02-23 (10-15-04) Los delicuentes- Angel.jpg
    invalid_files_case_4 = [] # 2004-07-03_19-27-48.avi

    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename != ".DS_Store" and not valid_filename_pattern.match(filename):
                if invalid_filename_pattern_case_1.match(filename):
                    invalid_files_case_1.append(os.path.join(folder_name, filename))
                elif invalid_filename_pattern_case_2.match(filename):
                    invalid_files_case_2.append(os.path.join(folder_name, filename))
                elif invalid_filename_pattern_case_3.match(filename):
                    invalid_files_case_3.append(os.path.join(folder_name, filename))
                elif invalid_filename_pattern_case_4.match(filename):
                    invalid_files_case_4.append(os.path.join(folder_name, filename))
                else:
                    logged_filename = os.path.join(folder_name, filename)
                    invalid_files.append(logged_filename)
                    print(f"Invalid filename: {logged_filename.replace(root_dir, '')}")

    with open("invalid_all.log", "w") as f:
        for filename in invalid_files:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

    with open("invalid_case_1.log", "w") as f:
        for filename in invalid_files_case_1:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

    with open("invalid_case_2.log", "w") as f:
        for filename in invalid_files_case_2:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

    with open("invalid_case_3.log", "w") as f:
        for filename in invalid_files_case_3:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

    with open("invalid_case_4.log", "w") as f:
        for filename in invalid_files_case_4:
            filename_logged = filename.replace(root_dir, "")
            f.write(f"{filename_logged}\n")

def main():
    parser = argparse.ArgumentParser(description="Check all files recursively to find those that do not match the desired name structure")
    parser.add_argument("--directory", required=True, help="Directory path to check")
    args = parser.parse_args()

    root_directory = args.directory
    check_file_names(root_directory)

if __name__ == "__main__":
    main()
