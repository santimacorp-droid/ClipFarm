/**
 * Simplified progress state management - based on fixed stages and polling
 */

import { create } from 'zustand'

export interface SimpleProgress {
  project_id: string
  stage: string
  percent: number
  message: string
  ts: number
  // Granular progress tracking
  current_step?: number
  total_steps?: number
  step_name?: string
  step_percent?: number
  overall_percent?: number
  substep?: string
  substep_current?: number
  substep_total?: number
  is_alive?: boolean
  last_heartbeat?: number
  elapsed_seconds?: number
  eta_seconds?: number | null
  recent_logs?: string[]
  status?: string
  error_message?: string | null
}

interface SimpleProgressState {
  // State data
  byId: Record<string, SimpleProgress>
  
  // Polling control
  pollingInterval: number | null
  isPolling: boolean
  
  // Operation method
  upsert: (progress: SimpleProgress) => void
  startPolling: (projectIds: string[], intervalMs?: number) => void
  stopPolling: () => void
  clearProgress: (projectId: string) => void
  clearAllProgress: () => void
  
  // Get method
  getProgress: (projectId: string) => SimpleProgress | null
  getAllProgress: () => Record<string, SimpleProgress>
}

export const useSimpleProgressStore = create<SimpleProgressState>((set, get) => {
  let timer: ReturnType<typeof setInterval> | null = null

  return {
    // Initial state
    byId: {},
    pollingInterval: null,
    isPolling: false,

    // Update or insert progress data
    upsert: (progress: SimpleProgress) => {
      set((state) => ({
        byId: {
          ...state.byId,
          [progress.project_id]: progress
        }
      }))
    },

    // Start polling
    startPolling: (projectIds: string[], intervalMs: number = 5000) => {
      const state = get()
      if (state.isPolling) return                          // already running
      if (!projectIds || projectIds.length === 0) return   // nothing to poll for

      console.log(`Starting progress polling: ${projectIds.join(', ')}`)

      // Fetch immediately
      const fetchSnapshots = async () => {
        try {
          const queryString = projectIds.map(id => `project_ids=${id}`).join('&')
          const response = await fetch(`/api/v1/simple-progress/snapshot?${queryString}`)
          
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`)
          }
          
          const snapshots: SimpleProgress[] = await response.json()
          
          // Update state
          snapshots.forEach(snapshot => {
            console.log(`Progress update: ${snapshot.project_id} - ${snapshot.stage} (${snapshot.percent}%)`)
            get().upsert(snapshot)
          })
          
          console.log(`Polling update: ${snapshots.length} project(s)`)
          
          // Automatically stop polling if all projects reached a terminal state
          try {
            const allTerminal = snapshots.length > 0 && snapshots.every(s => {
              return isCompleted(s.stage) || isFailed(s.message)
            })
            if (snapshots.length > 0 && allTerminal) {
              console.log('All projects completed, stopping progress polling')
              get().stopPolling()
            } else if (snapshots.length === 0) {
              console.log('Projects pending or running, continuing polling')
            }
          } catch (e) {
            console.warn('Error checking terminal status, continuing polling:', e)
          }
          
        } catch (error) {
          console.error('Failed to poll progress:', error)
        }
      }

      // Execute immediately once
      fetchSnapshots()

      // Set timer
      timer = setInterval(fetchSnapshots, intervalMs)

      set({
        isPolling: true,
        pollingInterval: intervalMs
      })
    },

    // Stop polling
    stopPolling: () => {
      const state = get()
      if (!timer && !state.isPolling) return

      if (timer) {
        clearInterval(timer)
        timer = null
      }
      
      set({
        isPolling: false,
        pollingInterval: null
      })
      
      console.log('Stopped progress polling')
    },

    // Clear single item progress
    clearProgress: (projectId: string) => {
      set((state) => {
        const newById = { ...state.byId }
        delete newById[projectId]
        return { byId: newById }
      })
    },

    // Clear all progress
    clearAllProgress: () => {
      set({ byId: {} })
    },

    // Get single item progress
    getProgress: (projectId: string) => {
      return get().byId[projectId] || null
    },

    // Get all progress
    getAllProgress: () => {
      return get().byId
    }
  }
})

// Stage display name mapping
export const STAGE_DISPLAY_NAMES: Record<string, string> = {
  'INGEST': 'Preparing Media',
  'SUBTITLE': 'Processing Subtitles',
  'ANALYZE': 'AI Analysis', 
  'HIGHLIGHT': 'Locating Highlights',
  'EXPORT': 'Exporting Video',
  'DONE': 'Completed'
}

// Stage color mapping
export const STAGE_COLORS: Record<string, string> = {
  'INGEST': '#1890ff',      // Blue
  'SUBTITLE': '#52c41a',    // Green
  'ANALYZE': '#fa8c16',     // Orange
  'HIGHLIGHT': '#722ed1',   // Purple
  'EXPORT': '#eb2f96',      // Pink
  'DONE': '#13c2c2'         // Cyan
}

// Get stage display name
export const getStageDisplayName = (stage: string): string => {
  return STAGE_DISPLAY_NAMES[stage] || stage
}

// Get stage color
export const getStageColor = (stage: string): string => {
  return STAGE_COLORS[stage] || '#666666'
}

// Determine whether it is a completion status
export const isCompleted = (stage: string, status?: string): boolean => {
  return stage === 'DONE' || status === 'completed'
}

// Determine whether it is a failure status
export const isFailed = (message: string, status?: string): boolean => {
  if (status === 'failed') return true
  if (!message) return false
  const lower = message.toLowerCase()
  return lower.includes('fail') || lower.includes('error') || message.includes('Failure') || message.includes('Error')
}
