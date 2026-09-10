# AccuWeather final task and UI audit

Audit date: 2026-09-09. Branch: `add-accuweather-mirror`.

The site was reset before every task and browser cookies were cleared. Every run began at `http://localhost:41024/` and used Playwright visible-element locators to search, open results, select tabs, sign in, change preferences, and submit forms. No task used a direct destination URL, database lookup, or source-code answer.

| Task | Result | Flow checked | Screenshot |
|---|---|---|---|
| AccuWeather--0 | Pass | Search → Phoenix current conditions | `outputs/accuweather-review/0-99-final.png` |
| AccuWeather--1 | Pass | Ambiguous Portland search → Maine result | `outputs/accuweather-review/1-99-final.png` |
| AccuWeather--2 | Pass | Search → Seattle → Hourly | `outputs/accuweather-review/2-99-final.png` |
| AccuWeather--3 | Pass | Search → Miami → Daily | `outputs/accuweather-review/3-99-final.png` |
| AccuWeather--4 | Pass | Search and compare Austin / Denver | `outputs/accuweather-review/4-99-final.png` |
| AccuWeather--5 | Pass | Springfield distractors → Missouri → Air Quality | `outputs/accuweather-review/5-99-final.png` |
| AccuWeather--6 | Pass | Login → search → save Seattle → account | `outputs/accuweather-review/6-99-final.png` |
| AccuWeather--7 | Pass | Login → Boston → remove → account | `outputs/accuweather-review/7-99-final.png` |
| AccuWeather--8 | Pass | Login → Chicago → alert form submit | `outputs/accuweather-review/8-99-final.png` |
| AccuWeather--9 | Pass | Login → Settings → Celsius → New York | `outputs/accuweather-review/9-99-final.png` |
| AccuWeather--10 | Pass | Postal search → San Francisco | `outputs/accuweather-review/10-99-final.png` |
| AccuWeather--11 | Pass | Search → radar → current weather | `outputs/accuweather-review/11-99-final.png` |
| AccuWeather--12 | Pass | Compare two Air Quality pages | `outputs/accuweather-review/12-99-final.png` |
| AccuWeather--13 | Pass | Search → Boston seven-day forecast | `outputs/accuweather-review/13-99-final.png` |
| AccuWeather--14 | Pass | London current → Air Quality | `outputs/accuweather-review/14-99-final.png` |
| AccuWeather--15 | Pass | Login → save two cities → account | `outputs/accuweather-review/15-99-final.png` |
| AccuWeather--16 | Pass | Portland Oregon / Maine comparison | `outputs/accuweather-review/16-99-final.png` |
| AccuWeather--17 | Pass | Search → Toronto hourly forecast | `outputs/accuweather-review/17-99-final.png` |
| AccuWeather--18 | Pass | Register → save Atlanta → account | `outputs/accuweather-review/18-99-final.png` |
| AccuWeather--19 | Pass | Phoenix / New Orleans comparison | `outputs/accuweather-review/19-99-final.png` |

## Hardening results

- De-leak: search results disclose only location identity and postal code, never current, hourly, daily, or air-quality answers. The prompt wording, ordering, labels, and cards do not reveal computed answers.
- Distractors: ambiguous Portland and Springfield queries return two and three same-name locations respectively; the 20-location catalog also supplies realistic cross-city comparison choices.
- Catalog breadth: 20 locations, 140 daily rows, and 240 hourly rows cover United States, Canada, and United Kingdom conditions and all captured icon types.
- Cross-field consistency: current temperatures, derived forecasts, unit conversion, conditions, location identity, saved locations, and alerts use relational records shared by all views.
- Leak archetypes checked: direct answer in prompt; target first by artificial ordering; pre-sorted winner; count label; detail on result card; unique target without distractors; answer in URL/slug; hidden data attribute; accessible-name answer; placeholder answer; success without mutation; visit-only verification; unrelated-state acceptance. None were found.
- Five hard multi-step tasks: 4, 5, 12, 13, and 19. Tasks 6–9, 15, and 18 additionally verify persistent state changes.

## Responsive and asset checks

Home, search, current, hourly, and radar pages were checked at 1440, 390, and 320 CSS pixels (15 page/viewport combinations). All had zero horizontal overflow and zero broken images. The committed screenshots below are representative; the full evidence set and structured step log are in `outputs/accuweather-review/`.

- `review-reports/assets/accuweather-homepage-1440.png`
- `review-reports/assets/accuweather-homepage-390.png`
- `review-reports/assets/accuweather-homepage-320.png`

The Solis font, GPS icon, and weather condition SVGs were captured from the live AccuWeather homepage asset inventory. No placeholder image is used.

## Reset proof

After the final task audit, `POST /reset/accuweather` completed ready and both files had MD5 `2701fb49e1edc178024785e6f8601870`:

- `/opt/WebSyn/accuweather/instance/accuweather.db`
- `/opt/WebSyn/accuweather/instance_seed/accuweather.db`
