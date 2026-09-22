/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** PostHog project API key(Public key, Can be packaged into front end. If not configured, beaconing is disabled.  */
  readonly VITE_PUBLIC_POSTHOG_KEY?: string
  /** PostHog Instance address, US: https://us.i.posthog.com, EU: https://eu.i.posthog.com */
  readonly VITE_PUBLIC_POSTHOG_HOST?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.svg' {
  const content: string
  export default content
}

declare module '*.svg?react' {
  import React from 'react'
  const ReactComponent: React.FunctionComponent<React.SVGProps<SVGSVGElement>>
  export default ReactComponent
}