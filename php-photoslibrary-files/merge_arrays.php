<?php
$allYearsArray = [];
foreach (range(2000, 2023) as $year) {
    $filename = "albums_in_gphotos_with_images_{$year}.json";
    if (!file_exists($filename)) {
        continue;
    }
    $yearFileContents = file_get_contents($filename);
    $yearArray = json_decode($yearFileContents, true);
    $allYearsArray = array_replace_recursive($allYearsArray, $yearArray);
}

print_r($allYearsArray);