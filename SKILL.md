# Skills & Learnings

- **YC Modernization**: Live YC site has moved to a "Four times a year" investment model (from the classic Twice a year).
- **Tech Stack Observation**: Live YC site is a React/Inertia SPA using Tailwind and custom Google Fonts (Source Serif 4, DM Sans).
- **Scraping Caveats**: React-rendered pages often require deep prop inspection (`data-page` attribute) to find the "source of truth" for directory lists.
- **Font Audit**: Premium fonts like `Outfit` might be suggested by LLMs for "modern" looks, but actual live site verification (CSS inspection) is necessary to ensure accuracy.
- **Search Optimization**: Token-overlap search benefits significantly from weight-biasing (name > description) and including secondary fields like founders.
- **WSL2/Host Connectivity**: Flask apps in WSL2 must bind to `0.0.0.0` to be reachable from the Windows host browser (Edge).
- **Remote Debugging Protocol (CDP)**: When Playwright cannot launch a browser directly (due to WSL2/Windows path issues), connecting over CDP to a host instance is a robust workaround.
- **Algolia Interception**: For sites that use Algolia or other client-side search APIs, intercepting the network response during a live session is often more efficient than scraping the DOM, especially for high-volume directory data.
- **Inertia.js Hydration**: While `data-page` often contains the initial data, it is sometimes intentionally kept thin (e.g. just metadata) with the actual content fetched asynchronously via API calls.
