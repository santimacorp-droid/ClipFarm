import { message } from 'antd'

export async function validateApiConfigBeforeProjectCreation(): Promise<boolean> {
  try {
    return true
  } catch (error) {
    console.error('APIConfiguration check failed:', error)
    message.error('APIConfiguration check failed')
    return false
  }
}
