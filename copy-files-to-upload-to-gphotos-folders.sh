#!/bin/bash

# folders=("1973-1999" "2000" "2001" "2002" "2003" "2004" "2005" "2006" "2007" "2008" "2009" "2010" "2011" "2012" "2013" "2014" "2015" "2016" "2017" "2018" "2019" "2020" "2021" "2022" "2023")
folders=("2000" "2001" "2002" "2003" "2004" "2005" "2006" "2007" "2008" "2009" "2010" "2011" "2012" "2013" "2014" "2015" "2016" "2017" "2018" "2019" "2020" "2021" "2022" "2023")

for folder in "${folders[@]}"; do
  time python3 copy-files-to-upload-to-gphotos.py --source "~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/$folder/" --destiny "~/Fotitos_dir_to_upload_to_gphotos/$folder/" --copy_images
  # time python3 copy-files-to-upload-to-gphotos.py --source "~/Insync/ladirecciondeangel@gmail.com/Google\ Drive/Fotitos/$folder/" --destiny "~/Fotitos_dir_to_upload_to_gphotos/$folder/" --copy_images --copy_videos --video_preset veryfast480p
done
