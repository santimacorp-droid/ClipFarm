/**
 * Application lifecycle telemetry + Global attributes(super properties). 
 *
 * - Global attributes: app_version / os / arch / locale, After registration, each event is automatically accompanied by, 
 *   Convenient by "version / system / Architecture slice analysis (e.g., high failure rate for a specific version in a system)). 
 * - Lifecycle events: 
 *   - app_installed: First startup on this device(= Installed device volume metric)
 *   - app_opened: Every time you start(PostHog Based on this, automatically calculate DAU / retain)
 *   - app_updated: Version number changed from the previous one
 */
import { getVersion } from '@tauri-apps/api/app'
import { posthog } from './client'

const INSTALL_FLAG_KEY = 'autoclip.analytics.installed'
const LAST_VERSION_KEY = 'autoclip.analytics.lastVersion'
const SESSION_COUNT_KEY = 'autoclip.analytics.sessionCount'

/** from webview of UA Roughly parse the operating system to avoid introducing changes Rust side of plugin-os dependency.  */
function detectOS(): string {
  const ua = navigator.userAgent
  if (/Mac/i.test(ua)) return 'macos'
  if (/Win/i.test(ua)) return 'windows'
  if (/Linux/i.test(ua)) return 'linux'
  return 'unknown'
}

/** rough parse CPU Architecture (used for distinction) Intel / Apple Silicon equals/like/including).  */
function detectArch(): string {
  const ua = navigator.userAgent
  if (/arm64|aarch64/i.test(ua)) return 'arm64'
  if (/x86_64|x64|Win64|WOW64|Intel/i.test(ua)) return 'x64'
  return 'unknown'
}

async function getAppVersion(): Promise<string> {
  try {
    return await getVersion()
  } catch {
    // not Tauri Environment (such as browser running vite dev)Unable to get the version
    return 'unknown'
  }
}

function readInt(key: string): number {
  try {
    return parseInt(localStorage.getItem(key) || '0', 10) || 0
  } catch {
    return 0
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* ignore */
  }
}

/**
 * Register global attributes and report startup-related lifecycle events. 
 * in initAnalytics() Call once afterward. posthog All when not initialized no-op. 
 */
export async function trackLaunch(): Promise<void> {
  if (typeof posthog?.register !== 'function') return

  const version = await getAppVersion()
  const os = detectOS()
  const arch = detectArch()
  const locale = navigator.language

  // Global attribute: Each subsequent event will carry it automatically
  posthog.register({
    app_version: version,
    os,
    arch,
    app_locale: locale,
  })

  // Session count
  const sessionCount = readInt(SESSION_COUNT_KEY) + 1
  safeSet(SESSION_COUNT_KEY, String(sessionCount))

  // first install
  let isInstalled = false
  try {
    isInstalled = localStorage.getItem(INSTALL_FLAG_KEY) === 'true'
  } catch {
    /* ignore */
  }
  if (!isInstalled) {
    posthog.capture('app_installed', { version, os, arch })
    safeSet(INSTALL_FLAG_KEY, 'true')
  }

  // version update
  let lastVersion: string | null = null
  try {
    lastVersion = localStorage.getItem(LAST_VERSION_KEY)
  } catch {
    /* ignore */
  }
  if (lastVersion && lastVersion !== version) {
    posthog.capture('app_updated', { from_version: lastVersion, to_version: version })
  }
  safeSet(LAST_VERSION_KEY, version)

  // Every time you start
  posthog.capture('app_opened', { version, session_number: sessionCount })
}
