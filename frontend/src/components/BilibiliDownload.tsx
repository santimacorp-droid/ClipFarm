import React, { useState, useEffect } from 'react'
import { Button, message, Progress, Input, Card, Typography, Space, Spin, Select, Tag, Row, Col } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { 
  projectApi, 
  bilibiliApi, 
  watermarkApi,
  VideoCategory, 
  BilibiliDownloadTask,
  WatermarkPreset
} from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import { validateApiConfigBeforeProjectCreation } from '../utils/apiConfigCheck'

const { Text } = Typography

interface BilibiliDownloadProps {
  onDownloadSuccess?: (projectId: string) => void
}

// Using fromAPIImportedBilibiliDownloadTaskType

const BilibiliDownload: React.FC<BilibiliDownloadProps> = ({ onDownloadSuccess }) => {
  const [url, setUrl] = useState('')
  const [projectName, setProjectName] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedBrowser, setSelectedBrowser] = useState<string>('')
  const [selectedCaptionStyle, setSelectedCaptionStyle] = useState<string>('hormozi_yellow')
  const [selectedDurationMode, setSelectedDurationMode] = useState<string>('tiktok_crp')
  const [showHookBanner, setShowHookBanner] = useState<boolean>(true)
  const [watermarkPresets, setWatermarkPresets] = useState<WatermarkPreset[]>([])
  const [selectedWatermarkPreset, setSelectedWatermarkPreset] = useState<string>('none')
  const [categories, setCategories] = useState<VideoCategory[]>([])
  const [loadingCategories, setLoadingCategories] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [currentTask, setCurrentTask] = useState<BilibiliDownloadTask | null>(null)
  const [pollingInterval, setPollingInterval] = useState<any>(null)
  const [videoInfo, setVideoInfo] = useState<any>(null)
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState('')
  
  const { addProject } = useProjectStore()

  // Loading video classification and watermark preset config
  useEffect(() => {
    const loadData = async () => {
      setLoadingCategories(true)
      try {
        const [catRes, wmRes] = await Promise.all([
          projectApi.getVideoCategories(),
          watermarkApi.getPresets().catch(() => [])
        ])
        setCategories(catRes.categories)
        if (catRes.default_category) {
          setSelectedCategory(catRes.default_category)
        } else if (catRes.categories.length > 0) {
          setSelectedCategory(catRes.categories[0].value)
        }

        setWatermarkPresets(wmRes)
        const defWm = wmRes.find(p => p.is_default)
        if (defWm) {
          setSelectedWatermarkPreset(defWm.id)
        }
      } catch (error) {
        console.error('Failed to load video categories/watermarks:', error)
      } finally {
        setLoadingCategories(false)
      }
    }

    loadData()
  }, [])

  // Cleaning up polling
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  const getDetectedUrlType = (inputUrl: string): { platform: 'youtube' | 'bilibili' | null; subtype?: string } => {
    const trimmed = inputUrl.trim()
    if (!trimmed) return { platform: null }
    if (/^https?:\/\/((www|m)\.)?youtube\.com\/shorts\/[a-zA-Z0-9_-]+/i.test(trimmed)) {
      return { platform: 'youtube', subtype: 'YouTube Shorts' }
    }
    if (/^https?:\/\/((www|m)\.)?youtube\.com\/live\/[a-zA-Z0-9_-]+/i.test(trimmed)) {
      return { platform: 'youtube', subtype: 'YouTube Live Stream' }
    }
    if (/^https?:\/\/youtu\.be\/[a-zA-Z0-9_-]+/i.test(trimmed)) {
      return { platform: 'youtube', subtype: 'YouTube Share Link (youtu.be)' }
    }
    if (/^https?:\/\/((www|m)\.)?youtube\.com\/(watch\?v=|embed\/|v\/)[a-zA-Z0-9_-]+/i.test(trimmed)) {
      return { platform: 'youtube', subtype: 'YouTube Standard Video' }
    }
    if (/^https?:\/\/(www\.)?bilibili\.com\/video\/[Bb][Vv][0-9A-Za-z]+/i.test(trimmed)) {
      return { platform: 'bilibili', subtype: 'Bilibili Video (BV)' }
    }
    if (/^https?:\/\/b23\.tv\/[0-9A-Za-z]+/i.test(trimmed)) {
      return { platform: 'bilibili', subtype: 'Bilibili Short Link (b23.tv)' }
    }
    if (/^https?:\/\/(www\.)?bilibili\.com\/video\/av\d+/i.test(trimmed)) {
      return { platform: 'bilibili', subtype: 'Bilibili Video (AV)' }
    }
    return { platform: null }
  }

  const validateVideoUrl = (url: string): boolean => {
    return getDetectedUrlType(url).platform !== null
  }
  
  const getVideoType = (url: string): 'bilibili' | 'youtube' | null => {
    return getDetectedUrlType(url).platform
  }

  const parseVideoInfo = async () => {
    if (!url.trim()) {
      setError('Please enter a video URL')
      return
    }

    const videoType = getVideoType(url.trim())
    if (!videoType) {
      setError('Please enter a valid YouTube or Bilibili video link (see supported formats below)')
      return
    }

    setParsing(true)
    setError('') // Clearing previous error information
    
    try {
      let response
      if (videoType === 'bilibili') {
        response = await bilibiliApi.parseVideoInfo(url.trim(), selectedBrowser)
      } else if (videoType === 'youtube') {
        response = await bilibiliApi.parseYouTubeVideoInfo(url.trim(), selectedBrowser)
      }
      
      const parsedVideoInfo = response?.video_info
      
      setVideoInfo(parsedVideoInfo)
      setError('') // Parsing succeeded, clearing error information
      
      // Auto-filling project name
      if (parsedVideoInfo && !projectName && parsedVideoInfo.title) {
        setProjectName(parsedVideoInfo.title)
      }
      
      return parsedVideoInfo
    } catch (error: any) {
      setError('Please enter a valid video link')
      setVideoInfo(null)
    } finally {
      setParsing(false)
    }
  }

  const startPolling = (taskId: string, videoType: 'bilibili' | 'youtube') => {
    const interval = setInterval(async () => {
      try {
        let task
        if (videoType === 'bilibili') {
          task = await bilibiliApi.getTaskStatus(taskId)
        } else {
          task = await bilibiliApi.getYouTubeTaskStatus(taskId)
        }
        setCurrentTask(task)
        
        if (task.status === 'completed') {
          clearInterval(interval)
          setPollingInterval(null)
          setDownloading(false)
          message.success('Video downloaded successfully!')
          
          if (task.project_id && onDownloadSuccess) {
            onDownloadSuccess(task.project_id)
          }
          
          // Resetting state
          resetForm()
        } else if (task.status === 'failed') {
          clearInterval(interval)
          setPollingInterval(null)
          setDownloading(false)
          message.error(`Download failed: ${task.error_message || 'Unknown error'}`)
          resetForm()
        }
      } catch (error) {
        console.error('Polling task failed:', error)
      }
    }, 2000)
    
    setPollingInterval(interval)
  }

  const handleDownload = async () => {
    if (!url.trim()) {
      message.error('Please enter a video URL')
      return
    }

    const videoType = getVideoType(url.trim())
    if (!videoType) {
      message.error('Please enter a valid YouTube or Bilibili video URL')
      return
    }

    // CheckingAPIconfiguration
    const hasValidApiConfig = await validateApiConfigBeforeProjectCreation()
    if (!hasValidApiConfig) {
      return
    }

    setDownloading(true)
    
    try {
      const requestBody: any = {
        url: url.trim(),
        project_name: projectName.trim() || videoInfo?.title || 'New Project',
        video_category: selectedCategory,
        caption_style: selectedCaptionStyle,
        duration_mode: selectedDurationMode,
        show_hook_banner: showHookBanner,
        watermark_preset_id: selectedWatermarkPreset
      }
      
      if (selectedBrowser) {
        requestBody.browser = selectedBrowser
      }

      let response
      if (videoType === 'bilibili') {
        response = await bilibiliApi.createDownloadTask(requestBody)
      } else {
        response = await bilibiliApi.createYouTubeDownloadTask(requestBody)
      }
      
      // Checking if response includes projectID(New optimized response format)
      if (response.project_id) {
        addProject({
          id: response.project_id,
          name: projectName.trim() || (videoInfo?.title ?? 'New Project'),
          status: 'pending',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        // New format: Project created, reset form now
        setCurrentTask(null)
        setDownloading(false)
        resetForm()
        
        // Showing unified success prompt
        const platformName = videoType === 'bilibili' ? 'Bilibili' : 'YouTube'
        message.success(`${platformName} project created! Downloading in background.`)
        
        if (onDownloadSuccess) {
          onDownloadSuccess(response.project_id)
        }
      } else {
        // Old format: Continue polling task status
        setCurrentTask(response)
        startPolling(response.id, videoType)
      }
      
    } catch (error: any) {
      setDownloading(false)
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to create download task'
      message.error(errorMessage)
    }
  }

  const resetForm = () => {
    setUrl('')
    setProjectName('')
    setCurrentTask(null)
    setVideoInfo(null)
    setError('')
  }

  const stopDownload = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }
    setDownloading(false)
    setCurrentTask(null)
    message.info('Stopped monitoring download task')
  }

  const detectedUrlType = getDetectedUrlType(url)

  return (
    <div style={{
      width: '100%',
      margin: '0 auto'
    }}>

      {/* Input Form */}
      <div style={{ marginBottom: '16px' }}>
        <Space direction="vertical" style={{ width: '100%' }} size={14}>
          <div>
            <Input.TextArea
              placeholder="Paste YouTube or Bilibili video link here (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ or https://youtu.be/dQw4w9WgXcQ)..."
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                // Clear previous video info and errors
                if (videoInfo) {
                  setVideoInfo(null)
                  setProjectName('')
                }
                if (error) {
                  setError('')
                }
              }}
              onBlur={() => {
                // Auto parse when blurred if valid
                if (url.trim() && !videoInfo && validateVideoUrl(url.trim())) {
                  parseVideoInfo();
                }
              }}
              style={{
                background: 'var(--ac-line-2)',
                border: '1px solid rgba(79, 172, 254, 0.3)',
                borderRadius: '8px',
                color: '#ffffff',
                fontSize: '14px',
                resize: 'none'
              }}
              rows={3}
              disabled={downloading || parsing}
            />

            {/* Supported URL Formats Card */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--ac-line, rgba(255, 255, 255, 0.08))',
              borderRadius: '8px',
              padding: '12px 16px',
              marginTop: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Text strong style={{ color: 'var(--ac-ink, #ffffff)', fontSize: '13px' }}>
                    Supported Video Formats
                  </Text>
                  <Tag color="blue" style={{ borderRadius: '4px', margin: 0, fontSize: '11px' }}>YouTube & Bilibili</Tag>
                </div>
                {detectedUrlType.subtype && (
                  <Tag color="success" style={{ borderRadius: '4px', margin: 0, fontWeight: 500 }}>
                    ✓ {detectedUrlType.subtype} Detected
                  </Tag>
                )}
              </div>

              <Row gutter={[16, 10]}>
                <Col span={13} xs={24} sm={13}>
                  <div style={{ color: '#ff4d4f', fontSize: '12px', fontWeight: 600, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>📺</span> YouTube Link Formats:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Standard: <Text code style={{ fontSize: '11px' }}>https://www.youtube.com/watch?v=VIDEO_ID</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Share link: <Text code style={{ fontSize: '11px' }}>https://youtu.be/VIDEO_ID</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Shorts: <Text code style={{ fontSize: '11px' }}>https://www.youtube.com/shorts/VIDEO_ID</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Live/Stream: <Text code style={{ fontSize: '11px' }}>https://www.youtube.com/live/VIDEO_ID</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Embed: <Text code style={{ fontSize: '11px' }}>https://www.youtube.com/embed/VIDEO_ID</Text>
                    </Text>
                  </div>
                </Col>

                <Col span={11} xs={24} sm={11}>
                  <div style={{ color: '#1890ff', fontSize: '12px', fontWeight: 600, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>⚡</span> Bilibili Link Formats:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • BV ID: <Text code style={{ fontSize: '11px' }}>https://www.bilibili.com/video/BVxxx</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • Short link: <Text code style={{ fontSize: '11px' }}>https://b23.tv/xxxxxx</Text>
                    </Text>
                    <Text style={{ color: 'var(--ac-sub, rgba(255, 255, 255, 0.75))', fontSize: '11.5px' }}>
                      • AV ID: <Text code style={{ fontSize: '11px' }}>https://www.bilibili.com/video/avxxx</Text>
                    </Text>
                  </div>
                </Col>
              </Row>
            </div>

            {parsing && (
               <div style={{
                 marginTop: '8px',
                 color: '#4facfe',
                 fontSize: '14px',
                 display: 'flex',
                 alignItems: 'center',
                 gap: '8px'
               }}>
                 <Spin size="small" />
                 <span>Parsing video metadata...</span>
               </div>
             )}
             {error && !parsing && (
               <div style={{
                 marginTop: '8px',
                 color: '#ff6b6b',
                 fontSize: '14px',
                 display: 'flex',
                 alignItems: 'center',
                 gap: '8px'
               }}>
                 <span>{error}</span>
               </div>
             )}
          </div>
          
          {/* Showing parsed video info that succeeded */}
          {videoInfo && (
            <div style={{
              background: 'rgba(102, 126, 234, 0.1)',
              border: '1px solid rgba(102, 126, 234, 0.3)',
              borderRadius: '8px',
              padding: '12px',
              marginBottom: '12px'
            }}>
              <Text style={{ color: '#667eea', fontWeight: 600, fontSize: '16px', display: 'block', marginBottom: '8px' }}>
                Video Information Retrieved
              </Text>
              <Text style={{ color: '#ffffff', fontSize: '14px', display: 'block' }}>
                {videoInfo.title}
              </Text>
              <Text style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '12px' }}>
                {getVideoType(url) === 'bilibili' ? 'Uploader' : 'Channel'}: {videoInfo.uploader || 'Unknown'} • Duration: {videoInfo.duration ? `${Math.floor(videoInfo.duration / 60)}:${String(Math.floor(videoInfo.duration % 60)).padStart(2, '0')}` : 'Unknown'}
              </Text>
            </div>
          )}
          
          {/* Only show project name and category after parsing succeeds */}
          {videoInfo && (
            <>
              <div>
                <Text style={{ color: '#ffffff', marginBottom: '12px', display: 'block', fontSize: '16px', fontWeight: 500 }}>Project Name (Optional)</Text>
                <Input
                  placeholder="Leave blank to use video title as project name"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  style={{
                    background: 'var(--ac-line-2)',
                    border: '1px solid rgba(79, 172, 254, 0.3)',
                    borderRadius: '12px',
                    color: '#ffffff',
                    height: '48px',
                    fontSize: '14px'
                  }}
                  disabled={downloading}
                />
              </div>
              
              <div>
                <Text style={{ color: '#ffffff', marginBottom: '12px', display: 'block', fontSize: '16px', fontWeight: 500 }}>Browser Cookie (Optional)</Text>
                <Select
                  placeholder="Select browser to import cookies (optional)"
                  value={selectedBrowser || undefined}
                  onChange={(value) => setSelectedBrowser(value || '')}
                  allowClear
                  style={{
                    width: '100%',
                    height: '48px'
                  }}
                  dropdownStyle={{
                    background: 'var(--ac-line-2)',
                    border: '1px solid rgba(79, 172, 254, 0.3)',
                    borderRadius: '12px'
                  }}
                  disabled={downloading}
                >
                  <Select.Option value="chrome">Chrome</Select.Option>
                  <Select.Option value="firefox">Firefox</Select.Option>
                  <Select.Option value="safari">Safari</Select.Option>
                  <Select.Option value="edge">Edge</Select.Option>
                </Select>
                <Text style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '12px', marginTop: '8px', display: 'block' }}>
                  Select your browser to import login state for premium subtitles. Leave empty for standard downloads.
                </Text>
              </div>
              
              <div>
                <Text style={{ color: '#ffffff', marginBottom: '12px', display: 'block', fontSize: '16px', fontWeight: 500 }}>Video Category</Text>
                {loadingCategories ? (
                  <Spin size="small" />
                ) : (
                  <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px'
                  }}>
                    {categories.map(category => {
                      const isSelected = selectedCategory === category.value
                      return (
                        <div
                          key={category.value}
                          onClick={() => setSelectedCategory(category.value)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: isSelected 
                              ? `2px solid ${category.color}` 
                              : '2px solid var(--ac-line)',
                            background: isSelected 
                              ? `${category.color}25` 
                              : 'var(--ac-line)',
                            color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                            boxShadow: isSelected 
                              ? `0 0 12px ${category.color}40` 
                              : 'none',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            fontSize: '13px',
                            fontWeight: isSelected ? 600 : 400,
                            userSelect: 'none'
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'var(--ac-line)'
                              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'var(--ac-line)'
                              e.currentTarget.style.borderColor = 'var(--ac-line)'
                            }
                          }}
                        >
                          <span style={{ fontSize: '14px' }}>{category.icon}</span>
                          <span>{category.name}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div>
                <Text style={{ color: '#ffffff', marginBottom: '12px', display: 'block', fontSize: '16px', fontWeight: 500 }}>
                  On-Screen Caption Style (Burned Subtitles)
                </Text>
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px'
                }}>
                  {[
                    { value: 'hormozi_yellow', label: '🔥 Hormozi Yellow', desc: 'Viral All-Caps with Yellow Glow' },
                    { value: 'neon_green', label: '🌿 Neon Green', desc: 'High-Energy Green Word Highlight' },
                    { value: 'neon_cyan', label: '💎 Neon Cyan', desc: 'Modern Electric Cyan' },
                    { value: 'clean_box', label: '🎬 Clean Box', desc: 'Minimalist Translucent Background' },
                    { value: 'none', label: '⚡ Raw (No Captions)', desc: 'Clean Source Video Without Burned Text' },
                  ].map(style => {
                    const isSelected = selectedCaptionStyle === style.value
                    return (
                      <div
                        key={style.value}
                        onClick={() => setSelectedCaptionStyle(style.value)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: isSelected 
                            ? '2px solid #5A8BFF' 
                            : '2px solid var(--ac-line)',
                          background: isSelected 
                            ? '#5A8BFF25' 
                            : 'var(--ac-line)',
                          color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                          boxShadow: isSelected 
                            ? '0 0 12px #5A8BFF40' 
                            : 'none',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          fontSize: '13px',
                          fontWeight: isSelected ? 600 : 400,
                          userSelect: 'none'
                        }}
                      >
                        <span>{style.label}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <Text style={{ color: '#ffffff', fontSize: '16px', fontWeight: 500 }}>
                    Target Clip Duration & Hook Strategy
                  </Text>
                  <div 
                    onClick={() => setShowHookBanner(!showHookBanner)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      background: showHookBanner ? 'rgba(82, 196, 26, 0.2)' : 'var(--ac-line)',
                      border: showHookBanner ? '1px solid #52c41a' : '1px solid var(--ac-line-2)',
                      color: showHookBanner ? '#52c41a' : 'var(--ac-sub)',
                      fontSize: '12px',
                      fontWeight: 500
                    }}
                  >
                    <span>{showHookBanner ? '✓ Top Hook Banner: ON' : '✕ Top Hook Banner: OFF'}</span>
                  </div>
                </div>
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px'
                }}>
                  {[
                    { value: 'tiktok_crp', label: '🚀 TikTok Rewards (60s–90s)', desc: 'Meets 60s+ TikTok Creator Rewards requirement with maximum viewer retention' },
                    { value: 'shorts_reels', label: '⚡ Shorts & Reels (30s–60s)', desc: 'Ultra-punchy viral shorts for YouTube Shorts and Instagram Reels' },
                    { value: 'deep_dive', label: '🎬 Topic Highlights (2m–5m)', desc: 'Extended breakdown chapters with complete thoughts' },
                  ].map(preset => {
                    const isSelected = selectedDurationMode === preset.value
                    return (
                      <div
                        key={preset.value}
                        onClick={() => setSelectedDurationMode(preset.value)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: isSelected 
                            ? '2px solid #52c41a' 
                            : '2px solid var(--ac-line)',
                          background: isSelected 
                            ? '#52c41a20' 
                            : 'var(--ac-line)',
                          color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                          boxShadow: isSelected 
                            ? '0 0 12px #52c41a40' 
                            : 'none',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          fontSize: '13px',
                          fontWeight: isSelected ? 600 : 400,
                          userSelect: 'none'
                        }}
                      >
                        <span>{preset.label}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Watermark and active brand presets */}
              <div>
                <Text style={{ color: '#ffffff', marginBottom: '12px', display: 'block', fontSize: '16px', fontWeight: 500 }}>
                  Brand Watermark / Logo Preset
                </Text>
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px'
                }}>
                  <div
                    onClick={() => setSelectedWatermarkPreset('none')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: selectedWatermarkPreset === 'none' 
                        ? '2px solid #ff7a45' 
                        : '2px solid var(--ac-line)',
                      background: selectedWatermarkPreset === 'none' 
                        ? '#ff7a4520' 
                        : 'var(--ac-line)',
                      color: selectedWatermarkPreset === 'none' ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                      boxShadow: selectedWatermarkPreset === 'none' 
                        ? '0 0 12px #ff7a4540' 
                        : 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      fontSize: '13px',
                      fontWeight: selectedWatermarkPreset === 'none' ? 600 : 400,
                      userSelect: 'none'
                    }}
                  >
                    <span>🚫 None (No Watermark)</span>
                  </div>

                  {watermarkPresets.map(preset => {
                    const isSelected = selectedWatermarkPreset === preset.id
                    return (
                      <div
                        key={preset.id}
                        onClick={() => setSelectedWatermarkPreset(preset.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: isSelected 
                            ? '2px solid #faad14' 
                            : '2px solid var(--ac-line)',
                          background: isSelected 
                            ? '#faad1420' 
                            : 'var(--ac-line)',
                          color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                          boxShadow: isSelected 
                            ? '0 0 12px #faad1440' 
                            : 'none',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          fontSize: '13px',
                          fontWeight: isSelected ? 600 : 400,
                          userSelect: 'none'
                        }}
                      >
                        {preset.logo_url && (
                          <img 
                            src={preset.logo_url} 
                            alt="" 
                            style={{ width: '18px', height: '14px', objectFit: 'contain' }} 
                          />
                        )}
                        <span>{preset.name}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}
        </Space>
      </div>

      {/* Operation buttons - only show after parsing succeeds */}
      {videoInfo && (
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'center', gap: '12px' }}>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
            loading={downloading}
            disabled={!url.trim()}
            size="large"
            style={{
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              border: 'none',
              borderRadius: '12px',
              height: '48px',
              padding: '0 32px',
              fontSize: '16px',
              fontWeight: 600,
              boxShadow: '0 4px 20px rgba(79, 172, 254, 0.3)',
              minWidth: '160px'
            }}
          >
            {downloading ? 'Importing...' : 'Start Import'}
          </Button>
          
          {downloading && (
            <Button
              onClick={stopDownload}
              size="large"
              style={{
                background: 'var(--ac-line)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                color: '#ffffff',
                borderRadius: '12px',
                height: '48px',
                padding: '0 24px',
                fontSize: '14px'
              }}
            >
              Stop Monitoring
            </Button>
          )}
        </div>
      )}

      {/* Download progress */}
      {currentTask && (
        <Card
          style={{
            background: 'var(--ac-line-2)',
            border: '1px solid rgba(79, 172, 254, 0.3)',
            borderRadius: '12px',
            marginTop: '16px',
            backdropFilter: 'blur(10px)'
          }}
          styles={{
            body: { padding: '16px' }
          }}
        >
          <div style={{ marginBottom: '16px' }}>
            <Text style={{ color: '#ffffff', fontWeight: 600, fontSize: '18px' }}>Import Progress</Text>
          </div>
          
          {currentTask.video_info && (
            <div style={{ marginBottom: '16px' }}>
              <Text style={{ color: '#4facfe', fontWeight: 600, fontSize: '16px' }}>{currentTask.video_info.title}</Text>
            </div>
          )}
          
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <Text style={{ color: 'var(--ac-sub)', fontSize: '14px' }}>Status: {currentTask.status}</Text>
              <Text style={{ color: 'var(--ac-sub)', fontSize: '14px' }}>{Math.round(currentTask.progress)}%</Text>
            </div>
            
            <Progress
              percent={Math.round(currentTask.progress)}
              status={currentTask.status === 'failed' ? 'exception' : 'active'}
              strokeColor={{
                '0%': '#4facfe',
                '100%': '#00f2fe'
              }}
              trailColor="var(--ac-line)"
              strokeWidth={8}
              showInfo={false}
            />
          </div>
          
          {currentTask.error_message && (
            <div style={{ 
              marginTop: '16px',
              padding: '12px',
              background: 'rgba(255, 77, 79, 0.1)',
              border: '1px solid rgba(255, 77, 79, 0.3)',
              borderRadius: '8px'
            }}>
              <Text style={{ color: '#ff4d4f', fontSize: '14px' }}>Error: {currentTask.error_message}</Text>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

export default BilibiliDownload
