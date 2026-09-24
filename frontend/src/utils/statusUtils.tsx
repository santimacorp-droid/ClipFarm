/**
 * Unified state handling utilities
 * Resolve inconsistencies in frontend state handling
 */

import { 
  ClockCircleOutlined, 
  LoadingOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined
} from '@ant-design/icons'

// Unified status type definitions
export type ProjectStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type UploadStatus = 'pending' | 'processing' | 'success' | 'failed'

// Project status configuration
export interface ProjectStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
  backgroundColor: string
  borderColor: string
}

// Task status configuration
export interface TaskStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
}

// Upload status configuration
export interface UploadStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
}

/**
 * Get project status configuration
 */
export const getProjectStatusConfig = (status: ProjectStatus): ProjectStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: 'Pending',
        badgeStatus: 'processing',
        backgroundColor: 'rgba(217, 217, 217, 0.15)',
        borderColor: 'rgba(217, 217, 217, 0.3)'
      }
    case 'processing':
      return {
        color: '#1890ff',
        icon: LoadingOutlined,
        text: 'Processing',
        badgeStatus: 'processing',
        backgroundColor: 'rgba(24, 144, 255, 0.15)',
        borderColor: 'rgba(24, 144, 255, 0.3)'
      }
    case 'completed':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: 'Completed',
        badgeStatus: 'success',
        backgroundColor: 'rgba(82, 196, 26, 0.15)',
        borderColor: 'rgba(82, 196, 26, 0.3)'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: ExclamationCircleOutlined,
        text: 'Failed',
        badgeStatus: 'error',
        backgroundColor: 'rgba(255, 77, 79, 0.15)',
        borderColor: 'rgba(255, 77, 79, 0.3)'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: 'Unknown',
        badgeStatus: 'default',
        backgroundColor: 'rgba(217, 217, 217, 0.15)',
        borderColor: 'rgba(217, 217, 217, 0.3)'
      }
  }
}

/**
 * Get task status configuration
 */
export const getTaskStatusConfig = (status: TaskStatus): TaskStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: 'Pending',
        badgeStatus: 'processing'
      }
    case 'running':
      return {
        color: '#1890ff',
        icon: PlayCircleOutlined,
        text: 'Running',
        badgeStatus: 'processing'
      }
    case 'completed':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: 'Completed',
        badgeStatus: 'success'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: CloseCircleOutlined,
        text: 'Failed',
        badgeStatus: 'error'
      }
    case 'cancelled':
      return {
        color: '#d9d9d9',
        icon: CloseCircleOutlined,
        text: 'Cancelled',
        badgeStatus: 'default'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: 'Unknown',
        badgeStatus: 'default'
      }
  }
}

/**
 * Get upload status configuration
 */
export const getUploadStatusConfig = (status: UploadStatus): UploadStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: 'Pending',
        badgeStatus: 'processing'
      }
    case 'processing':
      return {
        color: '#1890ff',
        icon: LoadingOutlined,
        text: 'Processing',
        badgeStatus: 'processing'
      }
    case 'success':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: 'Success',
        badgeStatus: 'success'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: CloseCircleOutlined,
        text: 'Failed',
        badgeStatus: 'error'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: 'Unknown',
        badgeStatus: 'default'
      }
  }
}

/**
 * Get progress bar status
 */
export const getProgressStatus = (status: ProjectStatus | TaskStatus | UploadStatus): 'normal' | 'active' | 'success' | 'exception' => {
  switch (status) {
    case 'processing':
    case 'running':
      return 'active'
    case 'completed':
    case 'success':
      return 'success'
    case 'failed':
      return 'exception'
    default:
      return 'normal'
  }
}

/**
 * Calculate project progress percentage
 */
export const calculateProjectProgress = (
  status: ProjectStatus, 
  currentStep?: number, 
  totalSteps?: number
): number => {
  if (status === 'completed') return 100
  if (status === 'failed') return 0
  if (currentStep && totalSteps && totalSteps > 0) {
    return Math.round((currentStep / totalSteps) * 100)
  }
  return 0
}

/**
 * Status compatibility conversion
 * Convert old status values to new unified status values
 */
export const normalizeProjectStatus = (status: string): ProjectStatus => {
  const s = (status || '').toLowerCase().trim()
  switch (s) {
    case 'error':
    case 'failed':
      return 'failed'
    case 'completed':
    case 'success':
    case 'done':
      return 'completed'
    case 'processing':
    case 'running':
    case 'downloading':
    case 'analyzing':
      return 'processing'
    case 'pending':
    case 'queued':
    default:
      return 'pending'
  }
}

export const normalizeTaskStatus = (status: string): TaskStatus => {
  switch (status) {
    case 'pending':
    case 'running':
    case 'completed':
    case 'failed':
    case 'cancelled':
      return status as TaskStatus
    default:
      return 'pending'
  }
}
