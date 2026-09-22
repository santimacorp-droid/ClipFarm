import React, { useState, useEffect } from 'react'
import { Button, message, Space, Typography, Input, Progress, Slider } from 'antd'
import { InboxOutlined, VideoCameraOutlined, FileTextOutlined, SubnodeOutlined } from '@ant-design/icons'
import { useDropzone } from 'react-dropzone'
import { projectApi, watermarkApi, VideoCategory, WatermarkPreset } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import { validateApiConfigBeforeProjectCreation } from '../utils/apiConfigCheck'

const { Text } = Typography

interface FileUploadProps {
  onUploadSuccess?: (projectId: string) => void
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
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

  const handleUpload = async () => {
    if (!files.video) {
      message.error('Please select a video file')
      return
    }

    if (!projectName.trim()) {
      message.error('Please enter a project name')
      return
    }

    // Check API configuration
    const hasValidApiConfig = await validateApiConfigBeforeProjectCreation()
    if (!hasValidApiConfig) {
      return
    }

    setUploading(true)
    setUploadProgress(0)
    
    try {
      // Realistic upload progress simulation
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 85) {
            clearInterval(progressInterval)
            return prev
          }
          const increment = Math.max(1, Math.floor((90 - prev) / 10))
          return prev + increment
        })
      }, 300)

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
      })
      
      clearInterval(progressInterval)
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

  const removeFile = (type: 'video' | 'srt') => {
    setFiles(prev => {
      const newFiles = { ...prev }
      delete newFiles[type]
      return newFiles
    })
  }

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

      {/* Project name input - Only display after file selected */}
      {files.video && (
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

      {/* Video category selection - Only display after file selected */}
      {files.video && (
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

      {/* Dynamic subtitle style selection - Only display after file selected */}
      {files.video && (
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

      {/* Edit duration preset & top banner hook - Only display after file selected */}
      {files.video && (
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

      {/* Video style & aspect ratio selection - Only display after file selected */}
      {files.video && (
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

      {/* Watermark & activity brand preset - Only display after file selected */}
      {files.video && (
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

      {/* Social Handle / Text Watermark */}
      {files.video && (
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

      {/* File list */}
      {Object.keys(files).length > 0 && (
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

      {/* Upload button - Only display after file selected */}
      {files.video && (
        <div style={{ textAlign: 'center', marginTop: '8px' }}>
          <Button 
            type="primary" 
            size="large"
            loading={uploading}
            disabled={!files.video || !projectName.trim()}
            onClick={handleUpload}
            style={{
              height: '48px',
              padding: '0 32px',
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
        </div>
      )}
    </div>
  )
}

export default FileUpload
