# Karawene Ben Cheikh — Data Analyst

Personal CV website, hosted on GitHub Pages.

- `index.html`: the CV site (photo and screenshot are built into the page)
- `Karawene_BenCheikh_CV.pdf`: the file the "Download CV" button downloads
- `layover-logbook-demo.mp4` and `layover-demo-poster.jpg`: the 2-minute walkthrough video of Layover Logbook
- `layover/`: **Layover Logbook**, a mobile web app for airline crew (free-time planner, nearby search, spending analytics, fatigue tracking, and a crew photo feed). Live at `/layover/`.
  - `layover/config.js`: public settings (Supabase project, Pro plan prices and Paddle IDs). No secrets go in this file.
  - `layover/backend/paddle-webhook.ts`: a copy of the Supabase Edge Function that records subscriptions from Paddle.
