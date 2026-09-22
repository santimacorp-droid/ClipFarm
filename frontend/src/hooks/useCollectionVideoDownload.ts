import { useState } from 'react'
import { message } from 'antd'
import { projectApi } from '../services/api'

export const useCollectionVideoDownload = () => {
  const [isGenerating, setIsGenerating] = useState(false)

  const generateAndDownloadCollectionVideo = async (
    projectId: string, 
    collectionId: string,
    _collectionTitle: string
  ) => {
    if (isGenerating) return

    setIsGenerating(true)
    
    try {
      // Generate consolidated video in user-specified order
      message.info('Generating consolidated video in your specified order...')
      
      // Generate collection video
      await projectApi.generateCollectionVideo(projectId, collectionId)
      
      message.success('Collection video generated successfully, starting download...')
      
      setTimeout(async () => {
        try {
          await projectApi.downloadVideo(projectId, undefined, collectionId)
          message.success('Collection video download completed')
        } catch (downloadError) {
          console.error('Download failed:', downloadError)
          message.error('Download failed, please try again')
        }
      }, 1000)
      
    } catch (error) {
      console.error('Failed to generate collection video:', error)
      message.error('Failed to generate collection video')
    } finally {
      setIsGenerating(false)
    }
  }

  return {
    isGenerating,
    generateAndDownloadCollectionVideo
  }
} 