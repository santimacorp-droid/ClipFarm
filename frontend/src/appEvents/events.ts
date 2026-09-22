/**
 * Critical business events (see ROADMAP.md Phase 0: Import / Exporting / Import failed / Setting key). 
 *
 * Define event names and payload types here to avoid scattered raw string literals. 
 * All capture Are all trackEvent, Not initialized / Closed automatically when no-op. 
 */
import { posthog } from './client'

export const AnalyticsEvent = {
  /** Import media (upload/Select video start project) */
  VideoImported: 'video_imported',
  /** Staging: Successfully generated slices */
  ClipsExported: 'clips_exported',
  /** Critical flow failed (import)/Transcription/Slicing/Export any step) */
  ProcessingFailed: 'processing_failed',
  /** Setting/Update LLM API key */
  ApiKeyConfigured: 'api_key_configured',
} as const

export type AnalyticsEventName =
  (typeof AnalyticsEvent)[keyof typeof AnalyticsEvent]

/** General instrumentation entry point. posthog Not initialized or closed opt-out when in un-imported state no-op(Already handled internally).  */
function trackEvent(
  name: AnalyticsEventName,
  properties?: Record<string, unknown>,
): void {
  // posthog.capture In un-imported state init Will not throw errors; Err on the side of caution by still doing checks
  if (typeof posthog?.capture !== 'function') return
  posthog.capture(name, properties)
}

export function trackVideoImported(props?: {
  source?: 'upload' | 'url' | 'local'
  fileType?: string
  durationSec?: number
  sizeBytes?: number
}): void {
  trackEvent(AnalyticsEvent.VideoImported, props)
}

export function trackClipsExported(props?: {
  clipCount?: number
  durationSec?: number
  withSubtitles?: boolean
  exportType?: 'clip' | 'collection' | 'project' | 'zip_bundle'
}): void {
  trackEvent(AnalyticsEvent.ClipsExported, props)
}

export function trackProcessingFailed(props: {
  stage: 'import' | 'transcribe' | 'analyze' | 'clip' | 'export' | 'other'
  message?: string
  code?: string | number
}): void {
  trackEvent(AnalyticsEvent.ProcessingFailed, props)
}

export function trackApiKeyConfigured(props: {
  provider: string
  /** Do not pass in key Plain text – only marks whether it's filled */
  hasKey: boolean
}): void {
  trackEvent(AnalyticsEvent.ApiKeyConfigured, props)
}
