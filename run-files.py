import os
import re
import argparse

# TODO 
# extension to lowercase
# extensio jpeg to jpg

def check_file_names(root_dir):
    extensions = "jpg|JPG|jpeg|png|bmp|HEIC|mp4|avi|AVI|mov|MOV|mpg|m4v|webm|3gp|wmv|mkv|wav|m4a"
    valid_filename_pattern = re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]( .+)?\.('+extensions+')$')
    invalid_filename_patterns = [
        # filename does not start with a year, i.e.: descenso.jpg or 13.jpg
        re.compile(r'^(?![0-9]{4}).*\.('+extensions+')$'),
        # 2004-11-01 (14-50-36).jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)\.('+extensions+')$'),
        # 2016-02-28 11.22.592.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9][0-9]\.('+extensions+')$'),
        # 2018-08-14 11.25.12a.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9][a-z]\.('+extensions+')$'),
        # 2018-01-30 10.43.22b DIA DE LA PAZ.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9][a-z] .+\.('+extensions+')$'),
        # 2003-02-23 (10-15-04) Los delicuentes- Angel.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)( [a-zA-Z0-9-_ \(\)]+)?\.('+extensions+')$'),
        # 20140618_191857.jpg
        re.compile(r'^[0-9]{4}(0[1-9]|1[0-2])([0-2][0-9]|3[01])_[0-2][0-9][0-5][0-9][0-5][0-9]\.('+extensions+')$'),
        # 2004-07-03_19-27-48.avi
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[0-2][0-9]-[0-5][0-9]-[0-5][0-9]\.('+extensions+')$'),
        # 2012-02-18_11.55.16.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]\.('+extensions+')$'),
        # 2012-02-18_11.55.20-1.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]-\d{1}\.('+extensions+')$'),
        # 2011-12-15-19-41-54.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])-[0-2][0-9]-[0-5][0-9]-[0-5][0-9]\.('+extensions+')$'),
        # 2011-12-16-01-11-18_x264.avi
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])-[0-2][0-9]-[0-5][0-9]-[0-5][0-9]_.+\.('+extensions+')$'),
        # 2010-11-21-01-50-06-716.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])-[0-2][0-9]-[0-5][0-9]-[0-5][0-9]-\d{3}\.('+extensions+')$'),
        # 2004-03-20_11-02-00l.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[0-2][0-9]-[0-5][0-9]-[0-5][0-9].*\.('+extensions+')$'),
        # 2004-05-15 (15-37-14l).jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9].*\)\.('+extensions+')$'),
        # 2003-07-01 (11.08.47).jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]\.[0-5][0-9]\.[0-5][0-9].*\)\.('+extensions+')$'),
        # 2003-07-09 07-34-04.avi
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]-[0-5][0-9]-[0-5][0-9]\.('+extensions+')$'),
        # 2003-07-06 14-26-32 - Mas desierto.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]-[0-5][0-9]-[0-5][0-9] .+\.('+extensions+')$'),
        # 2014-07-26 14-10-54a.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]-[0-5][0-9]-[0-5][0-9][a-z]\.('+extensions+')$'),
        # 2003-07-06 13-32-49AB.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]-[0-5][0-9]-[0-5][0-9][A-Z]{1,2}\.('+extensions+')$'),
        # 2017-05-07 17.00.00_36.jpeg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]_.+\.('+extensions+')$'),
        # 2017-05-15 11.21.05-4.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [0-2][0-9]\.[0-5][0-9]\.[0-5][0-9]-.+\.('+extensions+')$'),
        # 2008-07-27_(09-36-26).jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_\([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)\.('+extensions+')$'),
        # 2008-07-29_(08-12-41)_pablo.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_\([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)_.+\.('+extensions+')$'),
        # 2007-04-06 (18-33-00)-Voltereta en la arena-c.avi
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\)-.+\.('+extensions+')$'),
        # 2004-03-20 (02-26-08) angel_Alberto bailando¿.avi
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \([0-2][0-9]-[0-5][0-9]-[0-5][0-9]\) .+\.('+extensions+')$'),
        # 2004-08-02 Mari Ca lucia luciaate.mpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [a-zA-Z\(].+\.('+extensions+')$'),
        # 2003-01-01_Nochevieja_18.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_[a-zA-Z\(].+\.('+extensions+')$'),
        # 1967-04-10.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\.('+extensions+')$'),
        # 2004-12-18 26.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \d{2}\.('+extensions+')$'),
        # 2012-07-29 c.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) [a-z]\.('+extensions+')$'),
        # 2020-31-12 Regalo cuadro Elena con color.png
        re.compile(r'^[0-9]{4}-([0-2][0-9]|3[01])-(0[1-9]|1[0-2]) Regalo.+\.('+extensions+')$'),
        # 2014-04-05_09.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])_\d{2,3}\.('+extensions+')$'),
        # 2005-12-23 04 fatima.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) \d{2} [a-zA-Z].*\.('+extensions+')$'),
        # 2022-01-04 - sin retocar 29 Jimena.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01]) - [a-zA-Z].*\.('+extensions+')$'),
        # 1996-08 34_Guernika Pais Vasco.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2]) .+\.('+extensions+')$'),
        # 1970-Oct.jpg
        re.compile(r'^[0-9]{4}-Oct\.('+extensions+')$'),
        # 1970-Oct-1.jpg
        re.compile(r'^[0-9]{4}-Oct-\d{1}\.('+extensions+')$'),
        # 1970-11.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])\.('+extensions+')$'),
        # 1980-14.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[3-9])\.('+extensions+')$'),
        # 1999-06_Ultimo dia de instituto_09.jpg
        re.compile(r'^[0-9]{4}-(0[1-9]|1[0-2])_.+.('+extensions+')$'),
        # 2004 Dubrovnik-2.jpg
        re.compile(r'^(19[0-9]{2}|20[0-9]{2}) [a-zA-Z\(].+\.('+extensions+')$'),
        # 2003-1.jpg
        re.compile(r'^(19[0-9]{2}|20[0-9]{2})-\d{1}\.('+extensions+')$'),
        # 1997 01.jpg
        re.compile(r'^(19[0-9]{2}|20[0-9]{2}) \d{2}\.('+extensions+')$'),
        # 1981.jpg
        re.compile(r'^(19[0-9]{2}|20[0-9]{2})\.('+extensions+')$'),
        # Not recognized extensions
        re.compile(r'^.+\.(tif|gif|xml|psd|mov_gs1|mov_gs2|mov_gs3|mov_gs4|txt|mcf|asf|xptv|eps|svg|pdf|ai|vob|VOB|IFO|BUP|7z|thm|mp3|url|rss|wlmp|tmp|nmea|itm|gpx|xcf|db|aup|localized)$'),
    ]
    invalid_files_rest_of_cases = []
    invalid_files = [[] for _ in range(len(invalid_filename_patterns))]

    for folder_name, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename != ".DS_Store" and filename != ".localized" and not valid_filename_pattern.match(filename):
                matched = False
                for index, invalid_filename_pattern in enumerate(invalid_filename_patterns):
                    if invalid_filename_pattern.match(filename):
                        invalid_files[index].append(os.path.join(folder_name, filename))
                        matched = True
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

def main():
    parser = argparse.ArgumentParser(description="Check all files recursively to find those that do not match the desired name structure")
    parser.add_argument("--directory", required=True, help="Directory path to check")
    args = parser.parse_args()

    root_directory = args.directory
    check_file_names(root_directory)

if __name__ == "__main__":
    main()
