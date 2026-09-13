# 4shared asset provenance

All catalog thumbnails are real photographic assets. No generated image, generic
placeholder, or network-loaded runtime image is used. The files live in the
pinned Hugging Face asset bundle because `static/images/` is intentionally
ignored by Git.

## Existing WebHarbor photographs

| 4shared path | Existing WebHarbor source path | SHA-256 |
| --- | --- | --- |
| `static/images/london.jpg` | `sites/google_search/static/images/google_real/london.jpg` | `dd11fcb9d34fff87ce03e9008a68adadd0e182c7bfcb7c657fbd608d7b8ef65c` |
| `static/images/new-york.jpg` | `sites/google_search/static/images/google_real/new_york_city.jpg` | `2bb9a4689eb0e3ed5b5c0d654a4db3eb47304ebca2a82f65bd87e8d2898de24b` |
| `static/images/denali.jpg` | `sites/google_search/static/images/google_real/mount_denali_mckinley_elevation.jpg` | `6857da22b8620bd28791d05340eebb5236497b4a1b0bb65452d2a2754215ff5e` |

## Wikimedia Commons photographs

The remaining photographs were downloaded as 900-pixel thumbnails from their
Commons file pages, visually checked against the corresponding catalog record,
and converted to optimized JPEGs.

| Local file | Commons source | Creator | License |
| --- | --- | --- | --- |
| `library-reading-room.jpg` | [Library of Congress main reading room](https://commons.wikimedia.org/wiki/File:INTERIOR,_MAIN_READING_ROOM,_LOOKING_NORTHEAST_-_Library_of_Congress,_Northeast_corner_of_First_Street_and_Independence_Avenue_Southeast,_Washington,_District_of_Columbia,_DC_HABS_DC,WASH,461A-12.tif) | Library of Congress HABS | Public domain |
| `atlantic-boardwalk.jpg` | [Dunes and Boardwalk at Bethany Beach](https://commons.wikimedia.org/wiki/File:Dunes_and_Boardwalk_at_Bethany_Beach,_Delaware.jpg) | PointsofNoReturn | CC BY-SA 4.0 |
| `garden-pollinators.jpg` | [Bee on a blue flower](https://commons.wikimedia.org/wiki/File:Bee-Mating-Blue-Flower-large_ForestWander.jpg) | ForestWander | CC BY-SA 3.0 US |
| `alpine-lake-mist.jpg` | [Sunrise over Shadow Mountain Lake](https://commons.wikimedia.org/wiki/File:Sunrise_over_Shadow_Mountain_Lake,_CO_9-12_(19957710950).jpg) | Don Graham | CC BY-SA 2.0 |
| `ceramic-workbench.jpg` | [Ceramics workshop in Fes](https://commons.wikimedia.org/wiki/File:Inside_of_ceramics_workshop_Fes_Morrocco.jpg) | cliffwilliams | CC BY-SA 2.0 |
| `red-bicycle-brick-wall.jpg` | [Bicycles at a brick wall](https://commons.wikimedia.org/wiki/File:0020-fahrradsammlung-RalfR.jpg) | Ralf Roletschek | Free Art License |
| `winter-pines-snow.jpg` | [Heavy snow on pine branches](https://commons.wikimedia.org/wiki/File:Heavy_snow_on_pine_branches_in_Tuntorp_8.jpg) | W.carter | CC BY-SA 4.0 |
| `notebook-fountain-pen.jpg` | [Pen and notebook](https://commons.wikimedia.org/wiki/File:Pen_and_notebook_-_Narei.jpg) | Kaori Kita | CC BY-SA 3.0 |
| `harbor-boats-fog.jpg` | [Boats in San Francisco fog](https://commons.wikimedia.org/wiki/File:At_San_Francisco_2015_057.jpg) | Mike Peel | CC BY-SA 4.0 |
| `wildflower-trail.jpg` | [Wildflower-lined trail](https://commons.wikimedia.org/wiki/File:Wildflower_lined_trail_(52013518556).jpg) | Joshua Tree National Park | Public domain |
| `classic-camera.jpg` | [Vintage Canon A-1 camera](https://commons.wikimedia.org/wiki/File:Vintage_Canon_35mm_SLR_Camera,_Model_A-1,_All-Digital_Control,_Made_In_Japan,_Circa_1978_(13366931504).jpg) | Joe Haupt | CC BY-SA 2.0 |
| `rainy-window-lights.jpg` | [Rain Drops](https://commons.wikimedia.org/wiki/File:Rain_Drops_-_panoramio.jpg) | M. PINARCI | CC BY-SA 3.0 |
| `map-compass.jpg` | [Suunto compass and map](https://commons.wikimedia.org/wiki/File:Suunto_compass_%26_map_(48995280172).jpg) | Olgierd | CC BY 2.0 |

## Captured 4shared interface assets

These public interface assets were harvested from the contributor's sanitized
September 2026 Playwright capture. Only the named public files were copied; no
browser profile, cookies, account state, or private capture material is shipped.

| Local file | Live source URL |
| --- | --- |
| `static/images/ui/upload-image-initial.svg` | `https://static.4shared.com/images/upload-image-initial.svg` |
| `static/images/ui/qr-code-frame.svg` | `https://static.4shared.com/images/QR-code-frame.svg` |
| `static/images/ui/mob-app-qr-code.svg` | `https://static.4shared.com/images/mob-app-deeplink-QR-code.svg` |
| `static/images/ui/logo-google.svg` | `https://static.4shared.com/images/d1new/Google.svg` |
| `static/images/ui/logo-apple.svg` | `https://static.4shared.com/images/logo-apple-color.svg` |
| `static/images/ui/logo-huawei.svg` | `https://static.4shared.com/images/logo-huawei-color.svg` |

The repository-native logo mark remains in `static/icons/mark.svg` and is
tracked with the application code.
