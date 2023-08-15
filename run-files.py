import os
import re
import argparse

# TODO 
# estimate date for "Fotos antiguas" and "Yo de peque"
# convert videos to mp4
# DONE
# rename ny by ñ
# rename folders like 2001-02-03 (4-5) to 2001-02-03 (04-05)
# extension to lowercase
# extension jpeg to jpg

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

def main():
    parser = argparse.ArgumentParser(description="Check all files recursively to find those that do not match the desired name structure")
    parser.add_argument("--directory", required=True, help="Directory path to check")
    args = parser.parse_args()

    remove_log_files()

    root_directory = args.directory
    check_file_names(root_directory)
    # rename_uppercase_extensions(root_directory)
    # rename_jpeg_extensions(root_directory)

if __name__ == "__main__":
    main()
