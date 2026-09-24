import React, { useState, useEffect } from 'react'
import { Button, message, Space, Typography, Input, Progress, Slider, Segmented } from 'antd'
import { 
  InboxOutlined, 
  VideoCameraOutlined, 
  FileTextOutlined, 
  SubnodeOutlined,
  YoutubeOutlined,
  LinkOutlined,
  CloudDownloadOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  UserOutlined,
  SearchOutlined,
  RobotOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'
import { useDropzone } from 'react-dropzone'
import { projectApi, watermarkApi, youtubeApi, VideoCategory, WatermarkPreset, BilibiliVideoInfo } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import { validateApiConfig, checkApiConfig, ApiConfigStatus } from '../utils/apiConfigCheck'
import { useApiModalStore } from '../store/useApiModalStore'

const { Text } = Typography

interface FileUploadProps {
  onUploadSuccess?: (projectId: string) => void
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const [importSource, setImportSource] = useState<'file' | 'url'>('file')
  const [videoUrl, setVideoUrl] = useState('')
  const [isParsingUrl, setIsParsingUrl] = useState(false)
  const [parsedInfo, setParsedInfo] = useState<BilibiliVideoInfo | null>(null)
  const [submittingUrl, setSubmittingUrl] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [projectName, setProjectName] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedCaptionStyle, setSelectedCaptionStyle] = useState<string>('hormozi_yellow')
  const [selectedDurationMode, setSelectedDurationMode] = useState<string>('tiktok_crp')
  const [selectedAspectRatio, setSelectedAspectRatio] = useState<string>('9:16_blur')
  const [showHookBanner, setShowHookBanner] = useState<boolean>(true)
  const [watermarkPresets, setWatermarkPresets] = useState<WatermarkPreset[]>([])
  const [selectedWatermarkPreset, setSelectedWatermarkPreset] = useState<string>('none')
  const [watermarkText, setWatermarkText] = useState<string>('')
  const [watermarkTextOpacity, setWatermarkTextOpacity] = useState<number>(50)
  const [watermarkTextPosition, setWatermarkTextPosition] = useState<string>('lower_center')
  const [categories, setCategories] = useState<VideoCategory[]>([])
  const [, setLoadingCategories] = useState(false)
  const [files, setFiles] = useState<{
    video?: File
    srt?: File
  }>({})
  
  const { addProject } = useProjectStore()
  const [apiStatus, setApiStatus] = useState<ApiConfigStatus | null>(null)
  const openApiModal = useApiModalStore(state => state.openModal)

  const refreshApiStatus = async () => {
    try {
      const status = await checkApiConfig()
      setApiStatus(status)
    } catch (e) {
      console.warn('Failed to refresh API status:', e)
    }
  }

  useEffect(() => {
    refreshApiStatus()
  }, [])

  // Load video category & watermark preset configuration
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
        console.error('Failed to load categories/watermarks:', error)
      } finally {
        setLoadingCategories(false)
      }
    }

    loadData()
  }, [])

  const onDrop = (acceptedFiles: File[]) => {
    const newFiles = { ...files }
    
    acceptedFiles.forEach(file => {
      const extension = file.name.split('.').pop()?.toLowerCase()
      
      if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(extension || '')) {
        newFiles.video = file
        // Auto-set project name to video filename (without extension))
        // Update project name on new video file selection
        setProjectName(file.name.replace(/\.[^/.]+$/, ''))
      } else if (extension === 'srt') {
        newFiles.srt = file
      }
    })
    
    setFiles(newFiles)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
      'application/x-subrip': ['.srt']
    },
    multiple: true
  })

  const executeUpload = async () => {
    if (!files.video) {
      message.error('Please select a video file')
      return
    }

    if (!projectName.trim()) {
      message.error('Please enter a project name')
      return
    }

    setUploading(true)
    setUploadProgress(0)
    
    try {
      const newProject = await projectApi.uploadFiles({
        video_file: files.video,
        srt_file: files.srt,
        project_name: projectName.trim(),
        video_category: selectedCategory,
        caption_style: selectedCaptionStyle,
        duration_mode: selectedDurationMode,
        aspect_ratio: selectedAspectRatio,
        show_hook_banner: showHookBanner,
        watermark_preset_id: selectedWatermarkPreset,
        watermark_text: watermarkText.trim() || undefined,
        watermark_text_opacity: watermarkText.trim() ? watermarkTextOpacity / 100 : undefined,
        watermark_text_position: watermarkTextPosition,
      }, (percent) => {
        setUploadProgress(percent)
      })
      
      setUploadProgress(100)
      
      addProject(newProject)
      message.success('Project created successfully! Processing in background.')
      
      // Reset status
      setFiles({})
      setProjectName('')
      setWatermarkText('')
      setWatermarkTextOpacity(50)
      setUploadProgress(0)
      setUploading(false)
      // Reset to default category
      if (categories.length > 0) {
        setSelectedCategory(categories[0].value)
      }
      
      if (onUploadSuccess) {
        onUploadSuccess(newProject.id)
      }
      
    } catch (error: any) {
      console.error('Upload failed:', error)
      
      let errorMessage = 'Upload failed, please try again'
      let errorType = 'error'
      
      // Provide friendlier error message based on error type
      if (error.response?.status === 413) {
        errorMessage = 'File is too large, please choose a smaller video file'
        errorType = 'warning'
      } else if (error.response?.status === 415) {
        errorMessage = 'Unsupported format. Please select MP4, AVI, MOV, MKV, or WEBM'
        errorType = 'warning'
      } else if (error.response?.status === 400) {
        if (error.response?.data?.detail) {
          errorMessage = error.response.data.detail
        } else {
          errorMessage = 'Invalid file format or content, please check and try again'
        }
      } else if (error.response?.status === 500) {
        errorMessage = 'Server error while processing file, please try again later'
      } else if (error.code === 'ECONNABORTED') {
        errorMessage = 'Upload timed out, please check your network connection'
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail
      } else if (error.userMessage) {
        errorMessage = error.userMessage
      } else if (error.message) {
        errorMessage = error.message
      }
      
      // Show error message
      if (errorType === 'warning') {
        message.warning(errorMessage)
      } else {
        message.error(errorMessage)
      }
      
      // If network error, suggest retry
      if (error.code === 'ECONNABORTED' || error.response?.status >= 500) {
        message.info('If this issue persists, please check your connection or logs', 5)
      }
    } finally {
      setUploading(false)
    }
  }

  const handleUpload = async () => {
    if (!files.video) {
      message.error('Please select a video file')
      return
    }

    if (!projectName.trim()) {
      message.error('Please enter a project name')
      return
    }

    // Prompt for API key / provider if nothing is present or not yet chosen
    const hasValid = await validateApiConfig({
      actionName: 'Adding Video',
      onProceed: () => {
        executeUpload()
        refreshApiStatus()
      }
    })
    if (!hasValid) {
      return
    }

    await executeUpload()
  }

  const removeFile = (type: 'video' | 'srt') => {
    setFiles(prev => {
      const newFiles = { ...prev }
      delete newFiles[type]
      return newFiles
    })
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds || seconds <= 0) return '0:00'
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const handleParseUrl = async (urlToParse?: string) => {
    const targetUrl = (urlToParse || videoUrl).trim()
    if (!targetUrl) {
      message.warning('Please enter a YouTube URL first')
      return null
    }
    if (!targetUrl.includes('youtube.com') && !targetUrl.includes('youtu.be')) {
      message.warning('Please enter a valid YouTube video link (youtube.com or youtu.be)')
      return null
    }

    setIsParsingUrl(true)
    try {
      const res = await youtubeApi.parseVideoInfo(targetUrl)
      if (res && res.video_info) {
        setParsedInfo(res.video_info)
        if (!projectName.trim() || projectName === 'YouTube Video') {
          setProjectName(res.video_info.title)
        }
        message.success('Video information retrieved successfully!')
        return res.video_info
      }
    } catch (error: any) {
      console.error('Failed to parse URL:', error)
      const msg = error.response?.data?.detail || error.userMessage || error.message || 'Failed to parse video info'
      message.error(`Unable to parse link: ${msg}`)
    } finally {
      setIsParsingUrl(false)
    }
    return null
  }

  const executeUrlDownload = async (trimmedUrl: string, effectiveProjectName: string) => {
    setSubmittingUrl(true)
    try {
      const res = await youtubeApi.createDownloadTask({
        url: trimmedUrl,
        project_name: effectiveProjectName,
        video_category: selectedCategory,
        caption_style: selectedCaptionStyle,
        duration_mode: selectedDurationMode,
        aspect_ratio: selectedAspectRatio,
        show_hook_banner: showHookBanner,
        watermark_preset_id: selectedWatermarkPreset,
      })

      const projId = (res as any).project_id || res.id
      message.success('YouTube download initiated! Initializing AI clipping pipeline...')
      setVideoUrl('')
      setParsedInfo(null)
      setProjectName('')
      if (onUploadSuccess && projId) {
        onUploadSuccess(projId)
      }
    } catch (error: any) {
      console.error('Failed to create YouTube task:', error)
      const msg = error.response?.data?.detail || error.userMessage || error.message || 'Failed to start download task'
      message.error(msg)
    } finally {
      setSubmittingUrl(false)
    }
  }

  const handleUrlDownload = async () => {
    const trimmedUrl = videoUrl.trim()
    if (!trimmedUrl) {
      message.error('Please enter a YouTube video URL')
      return
    }

    let effectiveProjectName = projectName.trim()
    if (!effectiveProjectName) {
      const info = await handleParseUrl(trimmedUrl)
      if (info?.title) {
        effectiveProjectName = info.title
        setProjectName(info.title)
      } else {
        effectiveProjectName = `YouTube_${Date.now()}`
        setProjectName(effectiveProjectName)
      }
    }

    // Prompt for API key / provider before importing YouTube video
    const hasValid = await validateApiConfig({
      actionName: 'Importing Video',
      onProceed: () => {
        executeUrlDownload(trimmedUrl, effectiveProjectName)
        refreshApiStatus()
      }
    })
    if (!hasValid) {
      return
    }

    await executeUrlDownload(trimmedUrl, effectiveProjectName)
  }

  const hasMediaSelected = importSource === 'file'
    ? Boolean(files.video)
    : Boolean(parsedInfo || (videoUrl.trim().length > 10 && (videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be'))))

  return (
    <div style={{
      borderRadius: '16px',
      padding: '0',
      transition: 'all 0.3s ease',
      position: 'relative',
      overflow: 'hidden',
      width: '100%',
      margin: '0 auto'
    }}>
      {/* Background decoration */}
      <div style={{
        position: 'absolute',
        top: '-50%',
        right: '-50%',
        width: '200%',
        height: '200%',
        background: 'radial-gradient(circle, rgba(79, 172, 254, 0.08) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />
      

      {/* AI Engine Status Banner & Setup Trigger */}
      <div 
        style={{ 
          marginBottom: '16px',
          padding: '12px 18px',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: apiStatus?.hasValidConfig
            ? (apiStatus.isOfflineMode ? 'rgba(59, 130, 246, 0.08)' : 'rgba(82, 196, 26, 0.08)')
            : 'rgba(250, 173, 20, 0.12)',
          border: `1px solid ${apiStatus?.hasValidConfig ? (apiStatus.isOfflineMode ? 'rgba(59, 130, 246, 0.25)' : 'rgba(82, 196, 26, 0.25)') : 'rgba(250, 173, 20, 0.4)'}`,
          transition: 'all 0.3s ease'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: apiStatus?.hasValidConfig
              ? (apiStatus.isOfflineMode ? 'rgba(59, 130, 246, 0.2)' : 'rgba(82, 196, 26, 0.2)')
              : 'rgba(250, 173, 20, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: apiStatus?.hasValidConfig
              ? (apiStatus.isOfflineMode ? '#60A5FA' : '#52c41a')
              : '#faad14',
            fontSize: '16px'
          }}>
            {apiStatus?.isOfflineMode ? <ThunderboltOutlined /> : <RobotOutlined />}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--ac-ink)' }}>
                {apiStatus?.displayLabel || 'Checking AI Engine...'}
              </span>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '1px 6px',
                borderRadius: '4px',
                background: apiStatus?.hasValidConfig
                  ? (apiStatus.isOfflineMode ? 'rgba(59, 130, 246, 0.2)' : 'rgba(82, 196, 26, 0.2)')
                  : 'rgba(250, 173, 20, 0.2)',
                color: apiStatus?.hasValidConfig
                  ? (apiStatus.isOfflineMode ? '#60A5FA' : '#52c41a')
                  : '#faad14'
              }}>
                {apiStatus?.hasValidConfig ? (apiStatus.isOfflineMode ? 'OFFLINE HEURISTIC' : 'CLOUD AI READY') : 'SETUP REQUIRED'}
              </span>
            </div>
            <span style={{ fontSize: '11.5px', color: 'var(--ac-muted)', marginTop: '2px' }}>
              {apiStatus?.hasValidConfig
                ? (apiStatus.isOfflineMode
                    ? 'Using built-in transcript & audio heuristics. No API key required.'
                    : 'AI engine will identify viral hooks, grade highlights, and generate titles.')
                : 'Click to select an AI provider and enter your API key, or choose the built-in offline engine.'}
            </span>
          </div>
        </div>

        <Button
          size="small"
          type={apiStatus?.hasValidConfig ? 'default' : 'primary'}
          onClick={() => {
            openApiModal({
              title: apiStatus?.hasValidConfig ? 'Change AI Provider / Model' : 'Configure AI Engine',
              onSuccess: () => refreshApiStatus()
            })
          }}
          style={{
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            ...(apiStatus?.hasValidConfig 
              ? { borderColor: 'var(--ac-line)', background: 'var(--ac-card)', color: 'var(--ac-ink)' }
              : { background: 'linear-gradient(135deg, #faad14 0%, #ff7875 100%)', border: 'none', color: '#fff', boxShadow: '0 2px 8px rgba(250, 173, 20, 0.4)' }
            )
          }}
        >
          {apiStatus?.hasValidConfig ? 'Change Provider / Key' : 'Set Up AI Engine'}
        </Button>
      </div>

      {/* Source Selection Tabs */}
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'center' }}>
        <Segmented
          value={importSource}
          onChange={(val) => setImportSource(val as 'file' | 'url')}
          size="middle"
          options={[
            {
              value: 'file',
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 18px', fontWeight: 600 }}>
                  <InboxOutlined style={{ fontSize: '15px' }} />
                  <span>Local Video File</span>
                </div>
              ),
            },
            {
              value: 'url',
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 18px', fontWeight: 600 }}>
                  <YoutubeOutlined style={{ fontSize: '15px', color: '#ff4d4f' }} />
                  <span>YouTube / Web URL</span>
                </div>
              ),
            },
          ]}
        />
      </div>

      {importSource === 'file' ? (
        <div 
          {...getRootProps()} 
          className={`upload-area ${isDragActive ? 'dragover' : ''}`}
          style={{
            padding: '24px 16px',
            textAlign: 'center',
            marginBottom: '16px',
            background: isDragActive ? 'rgba(79, 172, 254, 0.15)' : 'var(--ac-line-2)',
            border: `2px dashed ${isDragActive ? '#4facfe' : 'rgba(79, 172, 254, 0.3)'}`,
            borderRadius: '16px',
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            position: 'relative',
            backdropFilter: 'blur(10px)'
          }}
        >
          <input {...getInputProps()} />
          <div style={{
            width: '48px',
            height: '48px',
            margin: '0 auto 12px',
            background: isDragActive ? 'rgba(79, 172, 254, 0.3)' : 'rgba(79, 172, 254, 0.1)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.3s ease',
            border: '1px solid rgba(79, 172, 254, 0.2)'
          }}>
            <InboxOutlined style={{ 
              fontSize: '20px', 
              color: isDragActive ? '#4facfe' : '#4facfe'
            }} />
          </div>
          <div>
            <Text strong style={{ 
              color: '#ffffff',
              fontSize: '16px',
              display: 'block',
              marginBottom: '8px',
              fontWeight: 600
            }}>
              {isDragActive ? 'Drop files here to import' : 'Click or drag video files to this area'}
            </Text>
            <Text style={{ color: 'var(--ac-sub)', fontSize: '14px', lineHeight: '1.5' }}>
              Supports MP4, AVI, MOV, MKV, WebM. <Text style={{ color: '#52c41a', fontWeight: 600 }}>Optional subtitles (.srt) or auto-generate with AI</Text>
            </Text>
          </div>
        </div>
      ) : (
        <div style={{
          padding: '20px',
          background: 'var(--ac-line-2)',
          borderRadius: '16px',
          border: '1px solid rgba(79, 172, 254, 0.25)',
          marginBottom: '16px',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <YoutubeOutlined style={{ color: '#ff4d4f', fontSize: '20px' }} />
            <Text strong style={{ color: '#ffffff', fontSize: '14px' }}>
              Enter YouTube Video URL
            </Text>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Input
              size="large"
              value={videoUrl}
              onChange={(e) => {
                setVideoUrl(e.target.value)
                if (parsedInfo && e.target.value !== parsedInfo.url) {
                  setParsedInfo(null)
                }
              }}
              onPressEnter={() => handleParseUrl()}
              placeholder="Paste YouTube link (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)"
              prefix={<LinkOutlined style={{ color: 'var(--ac-sub)' }} />}
              style={{
                flex: '1 1 300px',
                borderRadius: '10px',
                background: 'rgba(0, 0, 0, 0.25)',
                border: '1px solid rgba(79, 172, 254, 0.3)',
                color: '#ffffff'
              }}
            />
            <Button
              type="primary"
              size="large"
              loading={isParsingUrl}
              onClick={() => handleParseUrl()}
              icon={<SearchOutlined />}
              style={{
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #1890ff 0%, #36cfc9 100%)',
                fontWeight: 600,
                padding: '0 20px'
              }}
            >
              {isParsingUrl ? 'Parsing...' : 'Fetch Info'}
            </Button>
          </div>

          {/* Parsed Video Preview Card */}
          {parsedInfo && (
            <div style={{
              marginTop: '14px',
              padding: '12px 16px',
              borderRadius: '12px',
              background: 'rgba(79, 172, 254, 0.08)',
              border: '1px solid rgba(79, 172, 254, 0.3)',
              display: 'flex',
              gap: '14px',
              alignItems: 'center',
              flexWrap: 'wrap'
            }}>
              {parsedInfo.thumbnail && (
                <div style={{ position: 'relative', width: '110px', height: '62px', borderRadius: '6px', overflow: 'hidden', flexShrink: 0 }}>
                  <img
                    src={parsedInfo.thumbnail}
                    alt={parsedInfo.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                  {parsedInfo.duration > 0 && (
                    <span style={{
                      position: 'absolute',
                      bottom: '3px',
                      right: '3px',
                      background: 'rgba(0,0,0,0.85)',
                      color: '#fff',
                      padding: '1px 4px',
                      borderRadius: '3px',
                      fontSize: '10px',
                      fontWeight: 600
                    }}>
                      {formatDuration(parsedInfo.duration)}
                    </span>
                  )}
                </div>
              )}
              <div style={{ flex: 1, minWidth: '180px' }}>
                <Text strong style={{ color: '#ffffff', fontSize: '13.5px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {parsedInfo.title}
                </Text>
                <div style={{ display: 'flex', gap: '12px', marginTop: '5px', fontSize: '12px', color: 'var(--ac-sub)', flexWrap: 'wrap' }}>
                  {parsedInfo.uploader && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <UserOutlined /> {parsedInfo.uploader}
                    </span>
                  )}
                  {parsedInfo.duration > 0 && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <ClockCircleOutlined /> {formatDuration(parsedInfo.duration)}
                    </span>
                  )}
                  <span style={{ color: '#52c41a', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircleFilled /> Ready to Auto-Clip
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Project name input - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
            Project Name
          </Text>
          <Input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Enter project name"
            style={{ 
              height: '40px',
              borderRadius: '12px',
              fontSize: '14px',
              background: 'var(--ac-line-2)',
              border: '1px solid rgba(79, 172, 254, 0.3)',
              color: '#ffffff'
            }}
          />
        </div>
      )}

      {/* Video category selection - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
            Video Category
          </Text>
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
        </div>
      )}

      {/* Dynamic subtitle style selection - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
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
      )}

      {/* Edit duration preset & top banner hook - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <Text strong style={{ color: '#ffffff', fontSize: '14px' }}>
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
      )}

      {/* Video style & aspect ratio selection - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
            Video Format & Aspect Ratio
          </Text>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px'
          }}>
            {[
              { value: '9:16_blur', label: '🌫️ 9:16 Blurred Canvas', desc: '16:9 video centered with aesthetically dimmed, blurred background. Safe for all multi-speaker videos.' },
              { value: '9:16_header', label: '⬛ 9:16 Black Canvas Header (Meme / Story)', desc: 'Solid black 9:16 canvas with fitted video in lower section and persistent white headline in top header.' },
              { value: '9:16_split', label: '🎙️ 9:16 Podcast Split-Screen', desc: 'Dual-panel stacked layout: Top speaker & Bottom speaker for 2-person interviews.' },
              { value: '9:16_smart', label: '🤖 9:16 Smart Auto-Framing', desc: 'AI face detection selects the optimal podcast split, solo crop, or blurred canvas automatically.' },
              { value: '9:16_crop', label: '📱 9:16 Solo Fullscreen Crop', desc: 'Fills 100% of vertical screen centered on speaker.' },
              { value: '16:9', label: '🖥️ 16:9 Landscape', desc: 'Original widescreen landscape format' },
            ].map(preset => {
              const isSelected = selectedAspectRatio === preset.value
              return (
                <div
                  key={preset.value}
                  onClick={() => setSelectedAspectRatio(preset.value)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: isSelected 
                      ? '2px solid #1890ff' 
                      : '2px solid var(--ac-line)',
                    background: isSelected 
                      ? '#1890ff20' 
                      : 'var(--ac-line)',
                    color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                    boxShadow: isSelected 
                      ? '0 0 12px #1890ff40' 
                      : 'none',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    fontSize: '13px',
                    fontWeight: isSelected ? 600 : 400,
                    userSelect: 'none'
                  }}
                  title={preset.desc}
                >
                  <span>{preset.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Watermark & activity brand preset - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '8px', display: 'block' }}>
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
      )}

      {/* Social Handle / Text Watermark - Display when media is selected */}
      {hasMediaSelected && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <Text strong style={{ color: '#ffffff', fontSize: '14px' }}>
              Social Handle / Text Watermark
            </Text>
            {watermarkText.trim() && (
              <span style={{
                fontSize: '12px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: 'rgba(255, 255, 255, 0.1)',
                color: `rgba(255, 255, 255, ${Math.max(0.4, watermarkTextOpacity / 100)})`,
                letterSpacing: '0.5px'
              }}>
                Preview: {watermarkText} ({watermarkTextOpacity}%)
              </span>
            )}
          </div>
          <div style={{
            padding: '12px 16px',
            background: 'var(--ac-line)',
            borderRadius: '8px',
            border: '1px solid var(--ac-line-2)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <Input
                placeholder="e.g. @yourhandle or channel name (optional)"
                value={watermarkText}
                onChange={e => setWatermarkText(e.target.value)}
                style={{
                  flex: '1 1 240px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#ffffff',
                  borderRadius: '6px'
                }}
                maxLength={40}
              />
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {[
                  { value: 'lower_center', label: 'Lower Center' },
                  { value: 'bottom_center', label: 'Bottom' },
                  { value: 'bottom_right', label: 'Bottom Right' },
                  { value: 'top_right', label: 'Top Right' },
                ].map(pos => {
                  const isPosActive = watermarkTextPosition === pos.value
                  return (
                    <div
                      key={pos.value}
                      onClick={() => setWatermarkTextPosition(pos.value)}
                      style={{
                        fontSize: '11px',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        border: isPosActive ? '1px solid #1890ff' : '1px solid rgba(255, 255, 255, 0.15)',
                        background: isPosActive ? '#1890ff30' : 'transparent',
                        color: isPosActive ? '#ffffff' : 'rgba(255, 255, 255, 0.65)',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {pos.label}
                    </div>
                  )
                })}
              </div>
            </div>

            {watermarkText.trim() && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <span style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)', whiteSpace: 'nowrap' }}>
                  Opacity: {watermarkTextOpacity}%
                </span>
                <div style={{ flex: 1 }}>
                  <Slider
                    min={20}
                    max={90}
                    step={5}
                    value={watermarkTextOpacity}
                    onChange={(val: number) => setWatermarkTextOpacity(val)}
                  />
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[30, 45, 50, 60].map(presetOp => (
                    <button
                      key={presetOp}
                      type="button"
                      onClick={() => setWatermarkTextOpacity(presetOp)}
                      style={{
                        background: watermarkTextOpacity === presetOp ? 'rgba(24, 144, 255, 0.3)' : 'rgba(255, 255, 255, 0.05)',
                        border: watermarkTextOpacity === presetOp ? '1px solid #1890ff' : '1px solid transparent',
                        color: watermarkTextOpacity === presetOp ? '#ffffff' : 'rgba(255, 255, 255, 0.6)',
                        borderRadius: '4px',
                        padding: '2px 6px',
                        fontSize: '11px',
                        cursor: 'pointer'
                      }}
                    >
                      {presetOp}%
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* File list (Local upload mode only) */}
      {importSource === 'file' && Object.keys(files).length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <Text strong style={{ color: '#ffffff', fontSize: '14px', marginBottom: '12px', display: 'block' }}>
            Selected Files
          </Text>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {files.video && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '16px',
                background: 'var(--ac-line-2)',
                borderRadius: '12px',
                border: '1px solid rgba(79, 172, 254, 0.2)',
                backdropFilter: 'blur(10px)'
              }}>
                <Space size="middle">
                  <div style={{
                    width: '36px',
                    height: '36px',
                    background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(79, 172, 254, 0.3)'
                  }}>
                    <VideoCameraOutlined style={{ color: '#ffffff', fontSize: '16px' }} />
                  </div>
                  <div>
                    <Text style={{ color: '#ffffff', fontWeight: 600, display: 'block', fontSize: '14px' }}>
                      {files.video.name}
                    </Text>
                    <Text style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
                      {(files.video.size / 1024 / 1024).toFixed(2)} MB
                    </Text>
                  </div>
                </Space>
                <Button 
                  size="small" 
                  type="text" 
                  onClick={() => removeFile('video')}
                  style={{ 
                    color: '#ff6b6b',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px'
                  }}
                >
                  Remove
                </Button>
              </div>
            )}
            {files.srt && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                padding: '16px',
                background: 'var(--ac-line-2)',
                borderRadius: '12px',
                border: '1px solid rgba(82, 196, 26, 0.3)',
                backdropFilter: 'blur(10px)'
              }}>
                <Space size="middle">
                  <div style={{
                    width: '36px',
                    height: '36px',
                    background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(82, 196, 26, 0.3)'
                  }}>
                    <FileTextOutlined style={{ color: '#ffffff', fontSize: '16px' }} />
                  </div>
                  <div>
                    <Text style={{ color: '#ffffff', fontWeight: 600, display: 'block', fontSize: '14px' }}>
                      {files.srt.name}
                    </Text>
                    <Text style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
                      Subtitle File
                    </Text>
                  </div>
                </Space>
                <Button 
                  size="small" 
                  type="text" 
                  onClick={() => removeFile('srt')}
                  style={{ 
                    color: '#ff6b6b',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px'
                  }}
                >
                  Remove
                </Button>
              </div>
            )}
          </Space>
          
          {/* AISubtitle generation prompt */}
          {files.video && !files.srt && (
            <div style={{
              marginTop: '12px',
              padding: '12px 16px',
              background: 'rgba(82, 196, 26, 0.1)',
              border: '1px solid rgba(82, 196, 26, 0.3)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <SubnodeOutlined style={{ color: '#52c41a', fontSize: '16px' }} />
              <Text style={{ color: '#52c41a', fontSize: '14px', fontWeight: 500 }}>
                AI speech recognition will automatically transcribe subtitles
              </Text>
            </div>
          )}
        </div>
      )}

      {/* Import progress */}
      {uploading && (
        <div style={{ 
          marginBottom: '16px',
          padding: '20px',
          background: 'var(--ac-line-2)',
          borderRadius: '16px',
          border: '1px solid rgba(79, 172, 254, 0.3)',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{ marginBottom: '12px' }}>
            <Text style={{ color: '#ffffff', fontWeight: 600, fontSize: '14px' }}>Upload Progress</Text>
            <Text style={{ color: '#4facfe', float: 'right', fontWeight: 600, fontSize: '14px' }}>
              {uploadProgress}%
            </Text>
          </div>
          <Progress 
            percent={uploadProgress} 
            status="active"
            strokeColor={{
              '0%': '#4facfe',
              '100%': '#00f2fe',
            }}
            trailColor="var(--ac-line)"
            size={{ height: 6 }}
            showInfo={false}
            style={{ marginBottom: '8px' }}
          />
          <Text style={{ color: 'var(--ac-sub)', fontSize: '13px', marginTop: '8px', display: 'block', textAlign: 'center' }}>
            Uploading files, please wait...
          </Text>
        </div>
      )}

      {/* Action / Submit Button */}
      {hasMediaSelected && (
        <div style={{ textAlign: 'center', marginTop: '16px' }}>
          {importSource === 'file' ? (
            <Button 
              type="primary" 
              size="large"
              loading={uploading}
              disabled={!files.video || !projectName.trim()}
              onClick={handleUpload}
              style={{
                height: '48px',
                padding: '0 36px',
                borderRadius: '24px',
                background: uploading ? '#666666' : 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                border: 'none',
                fontSize: '16px',
                fontWeight: 600,
                boxShadow: uploading ? 'none' : '0 4px 20px rgba(79, 172, 254, 0.4)',
                transition: 'all 0.3s ease'
              }}
            >
              {uploading ? 'Uploading...' : 'Start Processing'}
            </Button>
          ) : (
            <Button 
              type="primary" 
              size="large"
              loading={submittingUrl || isParsingUrl}
              disabled={!videoUrl.trim() || !projectName.trim()}
              onClick={handleUrlDownload}
              style={{
                height: '48px',
                padding: '0 36px',
                borderRadius: '24px',
                background: (submittingUrl || isParsingUrl) ? '#666666' : 'linear-gradient(135deg, #ff4d4f 0%, #f5222d 50%, #fa8c16 100%)',
                border: 'none',
                fontSize: '16px',
                fontWeight: 600,
                boxShadow: (submittingUrl || isParsingUrl) ? 'none' : '0 4px 20px rgba(255, 77, 79, 0.4)',
                transition: 'all 0.3s ease'
              }}
              icon={<CloudDownloadOutlined />}
            >
              {submittingUrl ? 'Starting Download & AI Pipeline...' : 'Import & Auto-Clip'}
            </Button>
          )}
        </div>
      )}

    </div>
  )
}

export default FileUpload
