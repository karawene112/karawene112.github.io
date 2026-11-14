# Database additions (applied to Supabase project layover-logbook)

## Anti-spam (migration `crew_antispam_triggers`)
Triggers that run before a row is added, on top of the daily limits already in `crew_post_add` and `crew_comment_add`:
- `crew_posts`: at most 3 posts in 10 minutes, at most 1 link, no identical post within 24 hours.
- `crew_comments`: at most 10 comments in 5 minutes, at most 1 link, no identical comment on the same post within 1 hour.
- `crew_post_reports`: at most 20 reports in 24 hours.

## Visit counting (migration `cookieless_page_views`)
- Table `page_views`: page path, referring domain, 2-letter language, device type, first-page-of-visit flag, time. No IP, no user id, no cookie. RLS on with no policies, so it can't be read or written directly.
- `track_view(...)`: called by `/analytics.js` on every page; checks and cleans the values, ignores floods.
- `site_stats(p_days)`: totals, views per day, top pages, referrers, devices and languages. Only works for an owner listed in `crew_owners`; shown in the app under Notebook → Account and data → Site statistics.
