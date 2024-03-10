import os
import re
import argparse
from datetime import datetime


def check_file_names(dir, logs_dir, do_rename=False):
    extensions = "jpg|JPG|jpeg|png|gif|bmp|HEIC|mp4|avi|AVI|mov|MOV|mpg|m4v|webm|3gp|wmv|mkv|wav|m4a"
    extension_regex = r'\.(?P<extension>'+extensions+')'
    yyyymmdd = "(?P<year>[0-9]{4})(?P<month>0[1-9]|1[0-2])(?P<day>[0-2][0-9]|3[01])"
    yyyymmdd_hyphens = "(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>[0-2][0-9]|3[01])"
    hhmmss = "(?P<hour>[0-2][0-9])(?P<minutes>[0-5][0-9])(?P<seconds>[0-5][0-9])"
    hhmmss_hyphens = "(?P<hour>[0-2][0-9])-(?P<minutes>[0-5][0-9])-(?P<seconds>[0-5][0-9])"
    hhmmss_dots = r"(?P<hour>[0-2][0-9])\.(?P<minutes>[0-5][0-9])\.(?P<seconds>[0-5][0-9])"
    valid_filename_pattern = re.compile(r'^'+yyyymmdd_hyphens+' '+hhmmss_dots+'( .+)?'+extension_regex+'$')
    invalid_filename_patterns = [
        # 00 -> 2794 --> filename does not start with a year, i.e.: descenso.jpg or 13.jpg
        re.compile(r'^(?![0-9]{4}).*\.(?:'+extensions+')$'),
        # 01 -> 479 --> 2016-02-28 11.22.592.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_dots+r'(?P<extra_info>[0-9a-zA-Z ]*)'+extension_regex+r'$'),
        # 02 -> 15167 --> 2003-02-23 (10-15-04) Los delicuentes- Angel.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]\('+hhmmss_hyphens+r'\)[ _-]?(?P<extra_info>[a-zA-Z0-9\(\)]*)?'+extension_regex+r'$'),
        # 03 -> 13356 --> 2004-07-03_19-27-48.avi
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_hyphens+extension_regex+r'$'),
        # 04 -> 1350 --> 2012-02-18_11.55.20-1.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_dots+r'[ _-](?P<extra_info>\d{1})'+extension_regex+r'$'),
        # 05 -> 2428 --> 2011-12-16-01-11-18_x264.avi
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_hyphens+r'[ _-](?P<extra_info>.+)'+extension_regex+r'$'),
        # 06 -> 472 --> 2004-03-20_11-02-00l.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_hyphens+r'(?P<extra_info>.+)'+extension_regex+r'$'),
        # 07 -> 58 --> 2004-05-15 (15-37-14l).jpg
        re.compile(r'^'+yyyymmdd_hyphens+r' \('+hhmmss_hyphens+r'(?P<extra_info>.+)\)'+extension_regex+r'$'),
        # 08 -> 78 --> 2003-07-01 (11.08.47).jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]\('+hhmmss_dots+r'(?P<extra_info>.*)\)'+extension_regex+r'$'),
        # 09 -> 439 --> 2017-05-07 17.00.00_36.jpeg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]'+hhmmss_dots+r'[ _-](?P<extra_info>.+)'+extension_regex+r'$'),
        # 10 -> 578 --> 2007-04-06 (18-33-00)-Voltereta en la arena-c.avi
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-]\('+hhmmss_hyphens+r'\)[ _-](?P<extra_info>.+)'+extension_regex+r'$'),
        # 11 -> 783 --> 2004-08-02 Mari Ca lucia luciaate.mpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-](?P<extra_info>[a-zA-Z\(].+)'+extension_regex+r'$'),
        # 12 -> 186 --> 2004-12-18 26.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r'[ _-](?P<extra_info>\d{2,3}|[a-z])'+extension_regex+r'$'),
        # 13 -> 108 --> 2005-12-23 04 fatima.jpg
        re.compile(r'^'+yyyymmdd_hyphens+r' (?P<extra_info>(\d{2}|-) [a-zA-Z].*)'+extension_regex+r'$'),
        # 14 -> 143 --> 1996-08 34_Guernika Pais Vasco.jpg
        re.compile(r'^(?P<year>19[0-9]{2}|20[0-9]{2})[ _-](?P<month>0[1-9]|1[0-2])[ _-](?P<extra_info>.*)'+extension_regex+r'$'),
        # 15 -> 508 --> 2004 Dubrovnik-2.jpg
        re.compile(r'^(?P<year>19[0-9]{2}|20[0-9]{2})[ _-](?P<extra_info>[ ,0-9a-zA-Z\(\)-_]+)'+extension_regex+r'$'),
        # 16 -> 112 --> Not recognized extensions
        re.compile(r'^.+\.(tif|xml|psd|mov_gs1|mov_gs2|mov_gs3|mov_gs4|txt|mcf|asf|xptv|eps|svg|pdf|ai|vob|VOB|IFO|BUP|7z|thm|mp3|url|rss|wlmp|tmp|nmea|itm|gpx|xcf|db|aup|localized)$'),
    ]
    invalid_files_rest_of_cases = []
    invalid_files = [[] for _ in range(len(invalid_filename_patterns))]

    for folder_name, subfolders, filenames in os.walk(dir):
        ignored_folder_names = re.compile(r'^.*(En proceso|Album Jimena primer año|Album Carmela primer año|Fotos de gente|Fotos Alicia|Camera Uploads|Capturas de pantalla|Foto dibujo caricatura Carmela|Castigos de juegos).*$')
        if ignored_folder_names.match(folder_name):
            continue

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
                        if do_rename:
                            os.rename(os.path.join(folder_name, filename), os.path.join(folder_name, new_filename))
                break

            if not matched:
                logged_filename = os.path.join(folder_name, filename)
                invalid_files_rest_of_cases.append(logged_filename)
                #print(f"Invalid filename: {filename} path: {logged_filename.replace(dir, '')}")
                print(f"Invalid filename: {filename}")


    for index, invalid_file_case in enumerate(invalid_files):
        if index < 10:
            log_filename = f"invalid_case_0{index}.log"
        else:
            log_filename = f"invalid_case_{index}.log"
        if len(invalid_file_case) == 0: continue
        with open(f"{logs_dir}/{log_filename}", "w") as f:
            for filename in invalid_file_case:
                filename_logged = filename.replace(dir, "")
                f.write(f"{filename_logged}\n")

    with open(f"{logs_dir}/invalid_files_rest_of_cases.log", "w") as f:
        for filename in invalid_files_rest_of_cases:
            filename_logged = filename.replace(dir, "")
            f.write(f"{filename_logged}\n")

    for index, invalid_file_case in enumerate(invalid_files):
        print(f"Count of case {index} files: {len(invalid_file_case)}")

    print(f"Count of rest of files: {len(invalid_files_rest_of_cases)}")


def main():
    parser = argparse.ArgumentParser(description="Check all files recursively to find those that do not match the desired name structure. Rename to a correct format.")
    parser.add_argument("--dir", required=True, help="Source directory of files")
    parser.add_argument("--do_rename", action="store_true", help="Do rename files, instead of just logging changes")
    args = parser.parse_args()

    dir = args.dir
    do_rename = args.do_rename

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    logs_dir = f'logs/{formatted_datetime}_check_filenames'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    check_file_names(dir, logs_dir, do_rename)


if __name__ == "__main__":
    main()
