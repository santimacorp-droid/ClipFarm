/**
 * PostHog product analysis / instrumentation
 *
 * Design objectives (see) ROADMAP.md Phase 0): Anonymous, can be closed, local buffering. 
 * - Anonymous: don't collect anything by default PII, Use anonymous device before login ID; person profiles only when identify post-creation. 
 * - Can be closed: users can turn off in settings(opt-out), Status persisted in localStorage, Still persists after app restart. 
 * - local buffer: posthog-js Default batch buffer events in memory, offline/Exit proxy without losing main flow. 
 *
 * No configuration available VITE_PUBLIC_POSTHOG_KEY When activated, this module is no-op, 
 * therefore dev Environment (no key)Won't pollute online data. 
 */
import posthog from 'posthog-js'

const POSTHOG_KEY = import.meta.env.VITE_PUBLIC_POSTHOG_KEY as string | undefined
const POSTHOG_HOST =
  (import.meta.env.VITE_PUBLIC_POSTHOG_HOST as string | undefined) ??
  'https://us.i.posthog.com'

/** Key for storing user event tracking preference(true = Collection disabled).  */
const OPT_OUT_STORAGE_KEY = 'autoclip.analytics.optOut'

let initialized = false

/** Whether event tracking is enabled (configured) key And user has not closed it).  */
export function isAnalyticsEnabled(): boolean {
  if (!POSTHOG_KEY) return false
  try {
    return localStorage.getItem(OPT_OUT_STORAGE_KEY) !== 'true'
  } catch {
    return true
  }
}

/**
 * initialization PostHog. Call once at app startup. 
 * none key When offline, simply return without making any network requests. 
 */
export function initAnalytics(): void {
  if (initialized) return
  if (!POSTHOG_KEY) {
    if (import.meta.env.DEV) {
      console.info('[analytics] VITE_PUBLIC_POSTHOG_KEY not configured, analytics disabled')
    }
    return
  }

  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    // Desktop loads from file:// / Custom protocol loaded, cookie Not reliable, use unified localStorage instead to persist anonymous ID
    persistence: 'localStorage',
    // Do not create before login person profile, Keep anonymous; After login through identify Association (see) ROADMAP Phase 1)
    person_profiles: 'identified_only',
    // Automatically capture page clicks/Enter, build funnel with manual key events
    autocapture: true,
    // Privacy first: don't record screen by default(PostHog Also needs to be enabled separately)
    disable_session_recording: true,
    // HashRouter Manually report below pageview(see trackPageview)
    capture_pageview: false,
    capture_pageleave: true,
    // Respect user's preference to close on the local machine
    opt_out_capturing_by_default: !isAnalyticsEnabled(),
    loaded: (ph) => {
      if (import.meta.env.DEV) ph.debug()
    },
  })

  initialized = true
}

/**
 * open/Close event tracking (used in settings). Will persist to localStorage. 
 */
export function setAnalyticsEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(OPT_OUT_STORAGE_KEY, enabled ? 'false' : 'true')
  } catch {
    /* localStorage Ignored when unavailable */
  }
  if (!initialized) return
  if (enabled) posthog.opt_in_capturing()
  else posthog.opt_out_capturing()
}

/** Report once pageview(Call on route change).  */
export function trackPageview(path: string): void {
  if (!initialized) return
  posthog.capture('$pageview', { $current_url: path })
}

/** Associate identity after login(Phase 1 Use when accessing account).  */
export function identifyUser(
  distinctId: string,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return
  posthog.identify(distinctId, properties)
}

/** Reset anonymous identity when logging out.  */
export function resetUser(): void {
  if (!initialized) return
  posthog.reset()
}

export { posthog }
