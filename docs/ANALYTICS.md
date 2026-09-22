# AutoClip event tracking framework

> Tool(s): **PostHog**(US Scope, `https://us.i.posthog.com`)
> for details see `ROADMAP.md` Phase 0): **Anonymous · Toggle off · local buffer**. not collected PII, Video content, caption text, API key Plaintext. 

## 1. Metric framework

| Hierarchical | Metric | Data source is |
|------|------|---------|
| 🌟 north star metric | Successful generation count per week | `clips_exported` |
| Get | Number of downloads / installs | download page / `app_installed` |
| Activate | Import→Generation conversion rate, first generation time | Funnel events |
| Retention | D1/D7/D30, Weekly active users | `app_opened`(PostHog auto-calculated) |
| Participation | Average generations per user, feature penetration rate | Various functional events |
| monetization ready | Model distribution, supply key Rate, failure rate | `api_key_configured` / `processing_failed` |

## 2. core funnel

```
Download .dmg → app_installed → video_imported → clips_exported(★Activate) → Retention (re-engagement))
```

## 3. Event dictionary: `Object_Action(s)`, snake_case. Unified code flow for `src/analytics/events.ts`, Not configured key Or when users close it, automatically no-op. 

### lifecycle(`src/analytics/lifecycle.ts`)
| Event(s) | Trigger(s) | Attribute(s) |
|------|------|------|
| `app_installed` | First device startup | `version, os, arch` |
| `app_opened` | on startup | `version, session_number` |
| `app_updated` | Version number changed | `from_version, to_version` |

### Activation funnel
| Event(s) | trigger location | Attribute(s) |
|------|---------|------|
| `video_imported` | `api.ts` `uploadFiles` / `createDownloadTask` / `createYouTubeDownloadTask` | `source(upload/url), fileType, sizeBytes` |
| `clips_exported` ★ | `api.ts` `downloadVideo` | `clipCount, exportType(clip/collection/project)` |

### Configuration
| Event(s) | trigger location | Attribute(s) |
|------|---------|------|
| `api_key_configured` | `SettingsPage` Save successfully after | `provider, hasKey`(**do not pass plaintext**) |

### Error
| Event(s) | trigger location | Attribute(s) |
|------|---------|------|
| `processing_failed` | `api.ts` Import/Export catch | `stage(import/export/...), code, message` |

> Crash/Send error stack to **Sentry**(Phase 0 Redundant), PostHog Record business failures only. 

## 4. global attribute(s)(Super Properties)

Each event is automatically attached to `lifecycle.ts` of `trackLaunch()` Local registration: 
`app_version`(Tauri `getVersion()`)· `os` · `arch` · `app_locale`. 

## 5. - Default: screen recording off, no capture ID(PostHog Auto-, `localStorage` persisted). 
- Phase 1 After account goes live: login `identifyUser(userId)`, Sign out `resetUser()`(`src/analytics/posthog.ts` ready to use). 

## 6. Download count(App External)

App Internal use `app_installed` When installing, if there is a website, add PostHog Webpage snippet Bury `download_clicked`, Landing page→Download→Secure funnel. 

## 7. Privacy / Consent settings page → Application settings → **Privacy and data** Toggle switch(`setAnalyticsEnabled`), State persistence —生效 after restart. PII, key Count only `hasKey`. 
- Online before配套 completion of:**privacy policy**(《Requires compliance with the Personal Information Protection Law). 

## 8. Configuration(`frontend/.env.local`, Already gitignore): 
```
VITE_PUBLIC_POSTHOG_KEY=phc_xxx
VITE_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```
Missing defaults embed全过程 no-op. template at `frontend/.env.example`. 

## 9. Add new events by following these steps

1. In `events.ts` of `AnalyticsEvent` with constant + Type-safe wrapper functions. 
2. At the call site import Call (preferably placed at `services/api.ts` This centralized layer). 
3. Update this event dictionary file. 
