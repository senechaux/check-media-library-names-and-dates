# Dependencies
`pip3 install Pillow opencv-python scikit-image`

# PROCESS OF CATALOGUING PHOTOS AND VIDEOS
1. Check all images from Elena's phone have been uploaded to Dropbox
2. Copy all uploaded photos from Elena's Dropbox and Angel's Dropbox to Angel's Camera uploads in Google Drive
*** pending to create a script to do this step
3. Review manually, remove useless images
4. Run check-filenames.py and rename if needed in a second running using the argument --do_rename.
   ```.venv/bin/python3 check-filenames.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2024```
5. ******** TO DO ******** It should check if a video is not mp4. Meanwhile it can be checked doing a serach with Finder for files of type Video and ensuring all of them are MP4
6. Run check-exif-datetime.py and review logs in './src/logs'. 
  ```.venv/bin/python3 check-exif-datetime.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2024```
   To fix these articles, run again the script with the parametet '--do_rename', it will add the preffix 'diff_datetime' to all these files making easy to locate them in Finder.
   Use 'A Better Finder Attributes' to fix metadata datetimes or 'A Bettet Finder Rename' to rename files.
7. Run find-biggest-videos.py and review logs in './src/logs'. Use Handbrake to compress videos.
  ```.venv/bin/python find-biggest-videos.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2024```
8. Compress videos in "biggest_videos_to_compress" and output them into "biggest_videos_compressed".
9. Check new sizes are small enough. If they are not then use a smaller size for the reduced video.
10. Set the correct datetime metadata using "A better finder attributes"
11. Run move_biggest_videos.py. It renames the videos adding the suffix " reduced_size", move them to the correct folder, move the original video to "/Users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos videos con bit rate muy alto tmp" and remove the copied videos from folder "biggest_videos_to_compress".
12. Copy photos and videos to gphotos folder: `time .venv/bin/python ~/workspace/check-media-library-names-and-dates/src/copy-files-to-upload-to-gphotos.py --source ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/#########_YEAR_#########/ --destiny ~/Fotitos_compressed_to_upload_to_gphotos/#########_YEAR_#########/ --copy_images --copy_videos --video_preset veryfast480p`
13. Run check-exif-datetime.py on "~/Fotitos_compressed_to_upload_to_gphotos/#########_YEAR_#########/" and review logs in './src/logs'.
   ```.venv/bin/python3 check-exif-datetime.py --dir ~/Fotitos_compressed_to_upload_to_gphotos/#########_YEAR_#########/```
   To fix these articles, run again the script with the parametet '--do_rename', it will add the preffix 'diff_datetime' to all these files making easy to locate them in Finder.
   Use 'A Better Finder Attributes' to fix metadata datetimes or 'A Bettet Finder Rename' to rename files.
14. Run gphotos uploader

# TIPS
- How to look for several file names: `find ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/ -type f \( -name "2023-12-07 12.02.23.mp4" -o -name \)`. If you want to add them to A Better Finder Attributes just change the default application to open MP4 files and click in the filenames in Terminal.

# TODO
- Estimate date for "Fotos antiguas" and "Yo de peque"
- Change check-filenames.py to check if a video is not mp4

# DONE
rename ny by ñ
rename folders like 2001-02-03 (4-5) to 2001-02-03 (04-05)
extension to lowercase
extension jpeg to jpg
convert videos to mp4
change EXIF data based on filename for images
change EXIF data based on filename for videos
remove all photos from google photos
remove all albums from google photos using MacroRecorder
encode to reduce size of biggest videos
  mediainfo --Inform="Video;bitrate:%BitRate%b/s duration:%Duration%ms" video.mp4
download folders from Google Drive and compare with local ones
recover original videos from external disk
check exif datetimes again
check "2010-01-16 Cumpleaños Paloma" in external disk
"2017-01-07 Reyes magos Prosperidad" is empty everywhere! check photos and videos in other folders
split script run-files in several scripts
cut photos with gray areas from "2008-10-04 Paracaidas" folder
upload all photos to google photos
  compress images and videos before uploading
investigate on how to rename videos with names like "rduced_size"
investigate on how to rotate images according to their orientation, then resize them and then reupload them
Create script to compress biggest videos and move them to a different folder, and then move the compressed ones to the same folder the biggest one was. Or at least a script to execute the commands to copy and/or move the biggest videos and the compressed one.


# HOW TO USE

## files-and-folders-structure-dumper.py
Dump to two files a JSON representing the structure of files and folders.

```python3 files-and-folders-structure-dumper.py --dir ~/Fotitos_compressed_to_upload_to_gphotos```

## copy-files-to-upload-to-gphotos.py
Creates a thumbnail of the images (the larger size will be 1200px) and a compressed copy of the videos from the source directory to the destiny directory.
### args
  --copy_images: to copy images
  --copy_videos --video_preset veryfast480p: to compress and copy videos

```python3 copy-files-to-upload-to-gphotos.py --source "/users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos/2023/" --destiny "/users/angel/Fotitos_compressed_to_upload_to_gphotos/2023/" --copy_images --copy_videos --video_preset veryfast480p```

## find-and-count.py
Count how many files there are per type and year. Log all names to output files.

```python3 find-and-count.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/```

## rename-files.py
Rename files attending to regexp rules. Convert the extension to lowercase and rename 'jpeg' extensions to 'jpg'.

### args
  --do_rename: Do rename files, instead of just logging changes

```python3 rename-files.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/```

## find-biggest-videos.py
Find and log to an output file biggest videos in a folder. Ignores videos which name contains "reduced_video" since they have been already reduced.

```python3 find-biggest-videos.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/```

## compress-non-mp4-videos.py
DO NOT USE. Not needed now.

## check-filenames.py
Check all files recursively to find those that do not match the desired name structure. Rename to a correct format.

### args
  --do_rename: Do rename files, instead of just logging changes

```python3 check-filenames.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/```

## check-exif-datetime.py
Check all files recursively and check if the datetime in their name matches the datetime in Exif data

### args
  --do_rename: Do rename files, instead of just logging changes

```python3 check-exif-datetime.py --dir ~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/2023/```

Fix
===

1973-1999 ******************************************
=========
678 items, totalling 1,0 GB
677 items, totalling 769,1 MB

2000
====
118 items, totalling 68,7 MB
117 items, totalling 12,7 MB

2001
====
29 items, totalling 24,6 MB
29 items, totalling 3,5 MB

2002
====
199 items, totalling 2,9 GB
199 items, totalling 2,2 GB

2003
====
1.771 items, totalling 2,0 GB
1.750 items, totalling 418,7 MB

2004
====
3.412 items, totalling 4,9 GB
3.333 items, totalling 1,3 GB

2005
====
840 items, totalling 1,1 GB
837 items, totalling 381,0 MB

2006
====
3.168 items, totalling 3,9 GB
3.161 items, totalling 1,1 GB

2007
====
5.872 items, totalling 17,8 GB
5.872 items, totalling 6,4 GB

2008
====
2.515 items, totalling 7,0 GB
2.488 items, totalling 2,1 GB

2009
====
1.485 items, totalling 3,8 GB
1.484 items, totalling 1,3 GB

2010
====
1.794 items, totalling 5,7 GB
1.794 items, totalling 1,5 GB

2011
====
2.197 items, totalling 8,1 GB
2.197 items, totalling 2,3 GB

2012
====
1.492 items, totalling 5,5 GB
1.492 items, totalling 1,1 GB

2013
====
8.130 items, totalling 38,6 GB
8.130 items, totalling 4,9 GB

2014
====
2.021 items, totalling 10,4 GB
2.022 items, totalling 1,9 GB

2015
====
3.273 items, totalling 11,7 GB
3.273 items, totalling 1,5 GB

2016
====
2.849 items, totalling 14,2 GB
2.849 items, totalling 2,4 GB

2017
====
3.663 items, totalling 23,6 GB
3.662 items, totalling 4,4 GB

2018
====
3.253 items, totalling 22,6 GB
3.253 items, totalling 4,7 GB

2019
====
2.824 items, totalling 29,2 GB
2.824 items, totalling 2,9 GB

2020
====
2.962 items, totalling 39,3 GB
2.957 items, totalling 4,0 GB

2021
====
2.969 items, totalling 43,6 GB
2.969 items, totalling 5,7 GB

2022
====
3.227 items, totalling 42,1 GB
3.227 items, totalling 5,6 GB

2023
====
1.884 items, totalling 18,8 GB
1.884 items, totalling 2,3 GB
