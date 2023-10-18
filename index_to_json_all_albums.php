<?php
/**
 * Copyright 2018 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

require '../common/common.php';

use Google\Photos\Library\V1\PhotosLibraryClient;

/**
 * Removes the app's access to the user's Photos account.
 */
if (isset($_GET['clear'])) {
    unset($_SESSION['credentials']);
}

checkCredentials($templates->render('albums::connect'));
$photosLibraryClient = new PhotosLibraryClient(['credentials' => $_SESSION['credentials']]);

/**
 * Retrieves the user's albums, and renders them in a grid.
 */

try {
    $pagedResponse = $photosLibraryClient->listAlbums();
    $albums = $pagedResponse->iterateAllElements();
    $albumsCounter = 0;
    $extractedAlbumsCountOfFiles = [];
    $extractedAlbumsWithImages = [];

    foreach ($albums as $album) {
        preg_match('/(?<year>\d{4}).+/', $album->getTitle(), $matches);
        $year = $matches['year'];

        $extractedAlbumsCountOfFiles[$year][$album->getTitle()] = $album->getMediaItemsCount();

        if (!array_key_exists($year, $extractedAlbumsWithImages)) {
            $extractedAlbumsWithImages[$year] = [];
        }

        if (!array_key_exists($album->getTitle(), $extractedAlbumsWithImages[$year])) {
            $extractedAlbumsWithImages[$year][$album->getTitle()] = [];
        }

        echo "looking for images in album: {$album->getTitle()}<br>";
        $searchInAlbumResponse = $photosLibraryClient->searchMediaItems(['albumId' => $album->getId()]);
        $mediaItems = $searchInAlbumResponse->iterateAllElements();
        foreach($mediaItems as $mediaItem) {
            $extractedAlbumsWithImages[$year][$album->getTitle()][] = $mediaItem->getFilename();
        }
    }

    // ksort($extractedAlbumsCountOfFiles);
    // foreach ($extractedAlbumsCountOfFiles as &$innerArray) {
    //     ksort($innerArray);
    // }
    // file_put_contents("albums_in_gphotos_with_counter_{$year}.json", json_encode($extractedAlbumsCountOfFiles, JSON_PRETTY_PRINT));

    ksort($extractedAlbumsWithImages);
    foreach ($extractedAlbumsWithImages as &$innerArray) {
        ksort($innerArray);
    }
    foreach ($extractedAlbumsWithImages as $year => $albums) {
        foreach ($albums as $album => $images) {
            sort($images);
            $extractedAlbumsWithImages[$year][$album] = $images;
        }
    }
    file_put_contents("albums_in_gphotos_with_images.json", json_encode($extractedAlbumsWithImages, JSON_PRETTY_PRINT));

    echo "END of dumping album images<br>";
} catch (\Google\ApiCore\ApiException $e) {
    echo $templates->render('error', ['exception' => $e]);
}
