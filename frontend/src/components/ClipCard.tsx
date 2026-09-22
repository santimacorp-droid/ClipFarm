import React, { useState, useEffect, useRef } from 'react'
import { Card, Button, Tooltip, Modal, message, Dropdown, MenuProps } from 'antd'
import { 
  PlayCircleOutlined, 
  DownloadOutlined, 
  ClockCircleOutlined, 
  StarFilled, 
  FileTextOutlined, 
  CopyOutlined,
  DownOutlined,
  CheckCircleFilled,
  AppstoreOutlined
} from '@ant-design/icons'
import { Clip } from '../store/useProjectStore'
import BilibiliManager from './BilibiliManager'
import EditableTitle from './EditableTitle'
import CaptionEditorModal from './CaptionEditorModal'
import './ClipCard.css'

export interface PlatformConfig {
  id: string
  name: string
  shortName: string
  icon: string
  color: string
  activeBg: string
  activeBorder: string
  activeText: string
  badgeBg: string
  desc: string
}

export const PLATFORMS: PlatformConfig[] = [
  { 
    id: 'tiktok', 
    name: 'TikTok', 
    shortName: 'TikTok',
    icon: '📱', 
    color: '#FE2C55',
    activeBg: 'rgba(254, 44, 85, 0.16)',
    activeBorder: '#FE2C55',
    activeText: '#FE2C55',
    badgeBg: '#FE2C55',
    desc: 'TikTok 9:16 · Animated +Follow CTA'
  },
  { 
    id: 'instagram', 
    name: 'Instagram Reels', 
    shortName: 'Instagram',
    icon: '📷', 
    color: '#E1306C',
    activeBg: 'rgba(225, 48, 108, 0.16)',
    activeBorder: '#E1306C',
    activeText: '#E1306C',
    badgeBg: '#E1306C',
    desc: 'Instagram Reels 9:16 · Sunset Gradient Follow CTA'
  },
  { 
    id: 'youtube_shorts', 
    name: 'YouTube Shorts', 
    shortName: 'Shorts',
    icon: '▶️', 
    color: '#FF0000',
    activeBg: 'rgba(255, 0, 0, 0.16)',
    activeBorder: '#FF0000',
    activeText: '#FF4D4F',
    badgeBg: '#FF0000',
    desc: 'YouTube Shorts 9:16 · Subscribe & Bell CTA'
  },
  { 
    id: 'facebook', 
    name: 'Facebook', 
    shortName: 'Facebook',
    icon: '📘', 
    color: '#1877F2',
    activeBg: 'rgba(24, 119, 242, 0.16)',
    activeBorder: '#1877F2',
    activeText: '#4096FF',
    badgeBg: '#1877F2',
    desc: 'Facebook 9:16 · Blue Follow CTA'
  },
]

interface ClipCardProps {
  clip: Clip
  videoUrl?: string
  onDownload: (clipId: string) => void
  projectId?: string
  onClipUpdate?: (clipId: string, updates: Partial<Clip>) => void
  activePlatformProp?: string
  onPlatformChange?: (platform: string) => void
}

const ClipCard: React.FC<ClipCardProps> = ({ 
  clip, 
  projectId,
  onClipUpdate,
  activePlatformProp,
  onPlatformChange
}) => {
  const [showPlayer, setShowPlayer] = useState(false)
  const [showCaptionEditor, setShowCaptionEditor] = useState(false)
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [showBilibiliManager, setShowBilibiliManager] = useState(false)
  const [videoVersion, setVideoVersion] = useState<number>(() => Date.now())
  const [localPlatform, setLocalPlatform] = useState<string>('tiktok')

  const activePlatform = activePlatformProp || localPlatform
  const activeConfig = PLATFORMS.find(p => p.id === activePlatform) || PLATFORMS[0]

  const handlePlatformSwitch = (platformId: string) => {
    setLocalPlatform(platformId)
    onPlatformChange?.(platformId)
  }

  const finalVideoUrl = `/api/v1/clips/${clip.id}/video?v=${videoVersion}&platform=${activePlatform}`

  // generate video thumbnail
  useEffect(() => {
    if (finalVideoUrl) {
      generateThumbnail()
    }
  }, [finalVideoUrl])

  const generateThumbnail = () => {
    if (!finalVideoUrl) return
    
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.currentTime = 1
    
    video.onloadeddata = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      ctx.drawImage(video, 0, 0)
      
      const thumbnail = canvas.toDataURL('image/jpeg', 0.8)
      setVideoThumbnail(thumbnail)
    }
    
    video.src = finalVideoUrl
  }

  const handleDirectDownload = (platform: string) => {
    window.open(`/api/v1/clips/${clip.id}/download?platform=${platform}`, '_blank')
    message.success(`Downloading ${clip.title || 'clip'} for ${platform === 'youtube_shorts' ? 'YouTube Shorts' : platform.charAt(0).toUpperCase() + platform.slice(1)}`)
  }

  const handleDownloadAll4 = () => {
    PLATFORMS.forEach((p, index) => {
      setTimeout(() => {
        window.open(`/api/v1/clips/${clip.id}/download?platform=${p.id}`, '_blank')
      }, index * 350)
    })
    message.success('Starting download of all 4 platform deliverables!')
  }

  const getSocialCopyText = (platformKey: 'all' | 'tiktok' | 'instagram' | 'youtube_shorts' = 'all'): string => {
    const sc = clip.social_copy || clip.clip_metadata?.social_copy
    if (sc) {
      if (platformKey === 'tiktok') {
        const tt = sc.platforms?.tiktok
        if (tt?.caption) return `${tt.caption}\n\n${tt.hashtags || ''}`.trim()
      } else if (platformKey === 'instagram') {
        const ig = sc.platforms?.instagram
        if (ig?.caption) return `${ig.caption}\n\n${ig.hashtags || ''}`.trim()
      } else if (platformKey === 'youtube_shorts') {
        const yt = sc.platforms?.youtube_shorts
        if (yt) return `${yt.title}\n\n${yt.description}\n\n${yt.hashtags || ''}`.trim()
      }
      if (sc.post_caption) {
        return sc.post_caption
      }
    }

    // Dynamic intelligent fallback based on clip data
    const title = clip.title || clip.generated_title || 'Clip Highlight'
    const hook = clip.clip_metadata?.hook_text || clip.clip_metadata?.hook_title || title
    const highlights = (clip.content && clip.content.length > 0) ? clip.content.slice(0, 2).join(' ') : ''
    const tags = clip.hashtags?.length ? clip.hashtags.join(' ') : (clip.clip_metadata?.hashtags?.length ? clip.clip_metadata.hashtags.join(' ') : '#shorts #reels #viral #trending')
    return `${hook}\n\n${title}.\n${highlights}\n\nWhat are your thoughts on this? Share below 👇\n\n${tags}`
  }

  const copySocialCopy = (platformKey: 'all' | 'tiktok' | 'instagram' | 'youtube_shorts' = 'all') => {
    const text = getSocialCopyText(platformKey)
    navigator.clipboard.writeText(text)
    const label = platformKey === 'all' ? 'All-in-One' : platformKey === 'tiktok' ? 'TikTok' : platformKey === 'instagram' ? 'Instagram Reels' : 'YouTube Shorts'
    message.success(`Copied ${label} post caption & hashtags!`)
  }

  const socialCopyMenu: MenuProps = {
    items: [
      {
        key: 'all',
        label: '📋 All-in-One (Master Post)',
        onClick: () => copySocialCopy('all')
      },
      {
        type: 'divider'
      },
      {
        key: 'tiktok',
        label: '📱 TikTok (Search & SEO Optimized)',
        onClick: () => copySocialCopy('tiktok')
      },
      {
        key: 'instagram',
        label: '📸 Instagram Reels (Clean Spacing + CTA)',
        onClick: () => copySocialCopy('instagram')
      },
      {
        key: 'youtube_shorts',
        label: '▶️ YouTube Shorts (Title & Description)',
        onClick: () => copySocialCopy('youtube_shorts')
      }
    ]
  }

  const handleTitleUpdate = (newTitle: string) => {
    onClipUpdate?.(clip.id, { title: newTitle })
  }

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '00:00'
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const calculateDuration = (startTime: string, endTime: string): number => {
    if (!startTime || !endTime) return 0
    try {
      const parseTime = (timeStr: string): number => {
        const normalized = timeStr.replace(',', '.')
        const parts = normalized.split(':')
        if (parts.length !== 3) return 0
        const hours = parseInt(parts[0]) || 0
        const minutes = parseInt(parts[1]) || 0
        const seconds = parseFloat(parts[2]) || 0
        return hours * 3600 + minutes * 60 + seconds
      }
      const start = parseTime(startTime)
      const end = parseTime(endTime)
      return Math.max(0, end - start)
    } catch (error) {
      return 0
    }
  }

  const getDuration = () => {
    if (!clip.start_time || !clip.end_time) return '00:00'
    const start = clip.start_time.replace(',', '.')
    const end = clip.end_time.replace(',', '.')
    return `${start.substring(0, 8)} - ${end.substring(0, 8)}`
  }

  const getDisplayContent = () => {
    if (clip.recommend_reason && clip.recommend_reason.trim()) {
      return clip.recommend_reason
    }
    if (clip.content && Array.isArray(clip.content) && clip.content.length > 0) {
      const contentPoints = clip.content.filter(item => {
        const text = item.trim()
        if (text.length > 100) return false
        if (text.split(/[, . ! ? ; : ""''()[]]/).length > 3) return false
        return true
      })
      if (contentPoints.length > 0) {
        return contentPoints.join(' ')
      }
    }
    if (clip.outline && clip.outline.trim()) {
      return clip.outline
    }
    return 'No highlight summary'
  }

  const textRef = useRef<HTMLDivElement>(null)

  const downloadMenuItems: MenuProps['items'] = [
    {
      key: 'tiktok',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0' }}>
          <span>📱</span>
          <span><strong>TikTok</strong> Version (9:16 · Animated +Follow CTA)</span>
        </span>
      ),
      onClick: () => handleDirectDownload('tiktok')
    },
    {
      key: 'instagram',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0' }}>
          <span>📷</span>
          <span><strong>Instagram Reels</strong> Version (9:16 · Sunset Gradient CTA)</span>
        </span>
      ),
      onClick: () => handleDirectDownload('instagram')
    },
    {
      key: 'youtube_shorts',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0' }}>
          <span>▶️</span>
          <span><strong>YouTube Shorts</strong> Version (9:16 · Subscribe & Bell CTA)</span>
        </span>
      ),
      onClick: () => handleDirectDownload('youtube_shorts')
    },
    {
      key: 'facebook',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0' }}>
          <span>📘</span>
          <span><strong>Facebook</strong> Version (9:16 · Blue Follow CTA)</span>
        </span>
      ),
      onClick: () => handleDirectDownload('facebook')
    },
    { type: 'divider' },
    {
      key: 'all',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0', color: 'var(--ac-accent, #5A8BFF)', fontWeight: 600 }}>
          <AppstoreOutlined />
          <span>Download All 4 Platform Deliverables</span>
        </span>
      ),
      onClick: handleDownloadAll4
    }
  ]

  return (
    <>
      <Card
        className="clip-card"
        hoverable
        style={{ 
          width: '100%',
          minHeight: '445px',
          borderRadius: '16px',
          border: '1px solid var(--ac-line)',
          background: 'var(--ac-card)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
        styles={{
          body: {
            padding: '14px 16px 16px 16px',
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            justifyContent: 'space-between'
          },
        }}
        cover={
          <div 
            style={{ 
              height: '190px', 
              background: videoThumbnail 
                ? `url(${videoThumbnail}) center/cover` 
                : 'linear-gradient(135deg, #1f1f23 0%, #121214 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              cursor: 'pointer',
              overflow: 'hidden'
            }}
            onClick={() => setShowPlayer(true)}
          >
            {/* Dark gradient overlay */}
            <div 
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, transparent 40%, rgba(0,0,0,0.7) 100%)'
              }}
            />

            {/* Hover Play Button */}
            <div 
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0,0,0,0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: 0,
                transition: 'opacity 0.25s ease'
              }}
              className="video-overlay"
            >
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '50%',
                  background: 'rgba(255,255,255,0.2)',
                  backdropFilter: 'blur(8px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.4)'
                }}
              >
                <PlayCircleOutlined style={{ fontSize: '36px', color: '#ffffff' }} />
              </div>
            </div>
            
            {/* Top-Left: Active Platform Badge */}
            <div
              style={{
                position: 'absolute',
                top: '10px',
                left: '10px',
                background: 'rgba(0, 0, 0, 0.75)',
                backdropFilter: 'blur(8px)',
                border: `1px solid ${activeConfig.color}66`,
                color: '#ffffff',
                padding: '3px 9px',
                borderRadius: '999px',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                zIndex: 2,
                boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
              }}
            >
              <span>{activeConfig.icon}</span>
              <span>{activeConfig.name}</span>
            </div>

            {/* Top-Right: AI Quality Score */}
            <div
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'rgba(0,0,0,0.7)',
                backdropFilter: 'blur(8px)',
                color: '#ffffff',
                padding: '3px 8px',
                borderRadius: '999px',
                fontSize: '11.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                zIndex: 2
              }}
            >
              <StarFilled style={{ fontSize: '10px', color: '#faad14' }} />
              <span className="ac-mono" style={{ fontWeight: 600 }}>{(clip.final_score * 100).toFixed(0)}</span>
            </div>
            
            {/* Bottom-Left: Timestamp Range */}
            <div
              style={{
                position: 'absolute',
                bottom: '10px',
                left: '10px',
                background: 'rgba(0,0,0,0.7)',
                backdropFilter: 'blur(8px)',
                color: 'rgba(255,255,255,0.9)',
                padding: '3px 8px',
                borderRadius: '999px',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                zIndex: 2
              }}
            >
              <ClockCircleOutlined style={{ fontSize: '10px', opacity: 0.8 }} />
              <span className="ac-mono">{getDuration()}</span>
            </div>

            {/* Bottom-Right: Duration & Aspect */}
            <div
              style={{
                position: 'absolute',
                bottom: '10px',
                right: '10px',
                background: 'rgba(0,0,0,0.7)',
                backdropFilter: 'blur(8px)',
                color: '#ffffff',
                padding: '3px 8px',
                borderRadius: '999px',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                zIndex: 2
              }}
            >
              <span style={{ color: '#52c41a', fontSize: '9px', fontWeight: 700 }}>9:16</span>
              <span className="ac-mono">{formatDuration(calculateDuration(clip.start_time, clip.end_time))}</span>
            </div>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
          {/* Title Area */}
          <div style={{ minHeight: '40px', display: 'flex', alignItems: 'flex-start' }}>
            <EditableTitle
              title={clip.title || clip.generated_title || 'Untitled Clip'}
              clipId={clip.id}
              onTitleUpdate={handleTitleUpdate}
              style={{ 
                fontSize: '15px',
                fontWeight: 600,
                lineHeight: '1.35',
                color: 'var(--ac-ink)',
                width: '100%'
              }}
            />
          </div>
          
          {/* Content Highlights Area */}
          <div style={{ minHeight: '38px' }}>
            <Tooltip 
              title={getDisplayContent()} 
              placement="top" 
              overlayStyle={{ maxWidth: '320px' }}
              mouseEnterDelay={0.4}
            >
              <div 
                ref={textRef}
                style={{ 
                  fontSize: '12.5px',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  lineHeight: '1.45',
                  color: 'var(--ac-sub)',
                  cursor: 'pointer',
                  wordBreak: 'break-word',
                  textOverflow: 'ellipsis'
                }}
              >
                {getDisplayContent()}
              </div>
            </Tooltip>
          </div>

          {/* Platform Deliverables Switcher Bar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', marginTop: '2px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ac-sub)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Platform Deliverable
              </span>
              <span style={{ fontSize: '11px', color: '#52c41a', display: 'flex', alignItems: 'center', gap: '3px' }}>
                <CheckCircleFilled style={{ fontSize: '10px' }} /> 4 Formats Ready
              </span>
            </div>

            {/* 4 Platform Buttons Grid */}
            <div 
              style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(4, 1fr)', 
                gap: '4px', 
                background: 'var(--ac-line-2, #1f1f23)', 
                padding: '3px', 
                borderRadius: '9px',
                border: '1px solid var(--ac-line)'
              }}
            >
              {PLATFORMS.map(p => {
                const isSelected = activePlatform === p.id
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={(e) => { 
                      e.stopPropagation()
                      handlePlatformSwitch(p.id) 
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      padding: '5px 2px',
                      borderRadius: '7px',
                      border: isSelected ? `1px solid ${p.activeBorder}` : '1px solid transparent',
                      background: isSelected ? p.activeBg : 'transparent',
                      color: isSelected ? p.activeText : 'var(--ac-sub)',
                      fontWeight: isSelected ? 600 : 400,
                      fontSize: '11.5px',
                      cursor: 'pointer',
                      transition: 'all 0.18s ease'
                    }}
                    title={`View ${p.name} deliverable (${p.desc})`}
                  >
                    <span style={{ fontSize: '12px' }}>{p.icon}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.shortName}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
          {/* Primary Action: Download Button with Platform Menu */}
          <div style={{ display: 'flex', width: '100%', gap: '6px' }}>
            <Dropdown menu={{ items: downloadMenuItems }} trigger={['click']}>
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                style={{
                  flex: 1,
                  borderRadius: '8px',
                  background: activeConfig.badgeBg,
                  borderColor: activeConfig.badgeBg,
                  height: '34px',
                  fontWeight: 600,
                  fontSize: '12.5px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  boxShadow: `0 2px 10px ${activeConfig.color}40`
                }}
                onClick={(e) => {
                  e.stopPropagation()
                  handleDirectDownload(activePlatform)
                }}
              >
                <span>Download {activeConfig.shortName} (9:16)</span>
                <DownOutlined style={{ fontSize: '10px', marginLeft: 'auto' }} />
              </Button>
            </Dropdown>
          </div>

          {/* Secondary Utility Buttons */}
          <div style={{ display: 'flex', gap: '6px', width: '100%' }}>
            <Button
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => setShowPlayer(true)}
              style={{
                flex: 1,
                borderRadius: '6px',
                height: '28px',
                fontSize: '11.5px',
                background: 'var(--ac-line-2)',
                border: '1px solid var(--ac-line)',
                color: 'var(--ac-ink)'
              }}
            >
              Watch
            </Button>
            <Button
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => setShowCaptionEditor(true)}
              style={{
                flex: 1,
                borderRadius: '6px',
                height: '28px',
                fontSize: '11.5px',
                background: 'rgba(90, 139, 255, 0.08)',
                border: '1px solid rgba(90, 139, 255, 0.3)',
                color: '#5A8BFF'
              }}
            >
              Captions
            </Button>
            <Dropdown menu={socialCopyMenu} placement="bottomRight" trigger={['click']}>
              <Button
                size="small"
                icon={<CopyOutlined />}
                style={{
                  flex: 1,
                  borderRadius: '6px',
                  height: '28px',
                  fontSize: '11.5px',
                  background: 'rgba(250, 173, 20, 0.08)',
                  border: '1px solid rgba(250, 173, 20, 0.3)',
                  color: '#faad14',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px'
                }}
              >
                Copy Post <DownOutlined style={{ fontSize: '9px', marginLeft: '2px' }} />
              </Button>
            </Dropdown>
          </div>
        </div>
      </Card>

      {/* Video Playback Modal with Multi-Platform Switcher */}
      <Modal
        open={showPlayer}
        onCancel={() => setShowPlayer(false)}
        footer={[
          <Dropdown key="copy_dropdown" menu={socialCopyMenu} placement="topLeft" trigger={['click']}>
            <Button
              type="default"
              icon={<CopyOutlined style={{ color: '#faad14' }} />}
              style={{ borderRadius: '8px' }}
            >
              Copy Post & Hashtags <DownOutlined style={{ fontSize: '10px', marginLeft: '4px' }} />
            </Button>
          </Dropdown>,
          <Button 
            key="captions" 
            type="default" 
            icon={<FileTextOutlined />} 
            onClick={() => {
              setShowPlayer(false)
              setShowCaptionEditor(true)
            }}
            style={{ borderRadius: '8px' }}
          >
            Edit Captions
          </Button>,
          <Dropdown key="download_menu" menu={{ items: downloadMenuItems }} trigger={['click']}>
            <Button 
              type="primary" 
              icon={<DownloadOutlined />} 
              style={{ 
                borderRadius: '8px',
                background: activeConfig.badgeBg,
                borderColor: activeConfig.badgeBg
              }}
              onClick={() => handleDirectDownload(activePlatform)}
            >
              Download {activeConfig.shortName} <DownOutlined style={{ fontSize: '10px' }} />
            </Button>
          </Dropdown>
        ]}
        width={620}
        centered
        destroyOnClose
        styles={{
          header: {
            borderBottom: '1px solid var(--ac-line)',
            background: 'var(--ac-card)',
            padding: '16px 20px'
          },
          body: {
            padding: '16px 20px',
            background: '#0a0a0c',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px'
          }
        }}
        closeIcon={
          <span style={{ color: 'var(--ac-ink)', fontSize: '16px' }}>×</span>
        }
        title={
          <div style={{ display: 'flex', alignItems: 'center', width: '100%', paddingRight: '28px' }}>
            <EditableTitle
              title={clip.title || clip.generated_title || 'Video Preview'}
              clipId={clip.id}
              onTitleUpdate={handleTitleUpdate}
              style={{ 
                color: 'var(--ac-ink)',
                fontSize: '16px', 
                fontWeight: 600,
                flex: 1
              }}
            />
          </div>
        }
      >
        {/* Platform Selection Tabs in Modal */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11.5px', color: '#999', fontWeight: 500 }}>
              Select Platform Deliverable Version:
            </span>
            <span style={{ fontSize: '11px', color: activeConfig.color, fontWeight: 600 }}>
              {activeConfig.desc}
            </span>
          </div>

          <div 
            style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(4, 1fr)', 
              gap: '6px', 
              background: '#16161a', 
              padding: '4px', 
              borderRadius: '10px',
              border: '1px solid #2a2a30'
            }}
          >
            {PLATFORMS.map(p => {
              const isSelected = activePlatform === p.id
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handlePlatformSwitch(p.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '8px 4px',
                    borderRadius: '8px',
                    border: isSelected ? `1px solid ${p.activeBorder}` : '1px solid transparent',
                    background: isSelected ? p.activeBg : 'transparent',
                    color: isSelected ? p.activeText : '#888',
                    fontWeight: isSelected ? 600 : 400,
                    fontSize: '12.5px',
                    cursor: 'pointer',
                    transition: 'all 0.18s ease'
                  }}
                >
                  <span style={{ fontSize: '14px' }}>{p.icon}</span>
                  <span>{p.name}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Video Player Container */}
        <div 
          style={{ 
            width: '100%', 
            display: 'flex', 
            justifyContent: 'center', 
            background: '#000', 
            borderRadius: '12px', 
            overflow: 'hidden',
            border: '1px solid #222'
          }}
        >
          <video
            key={`${clip.id}_${activePlatform}_${videoVersion}`}
            controls
            preload="metadata"
            style={{ width: '100%', maxHeight: '500px', borderRadius: '12px' }}
          >
            <source
              src={`/api/v1/clips/${clip.id}/video?v=${videoVersion}&platform=${activePlatform}`}
              type="video/mp4"
            />
            Your browser does not support video playback.
          </video>
        </div>

        {/* Deliverable Info Bar */}
        <div 
          style={{ 
            width: '100%', 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '8px 12px',
            background: '#141418',
            borderRadius: '8px',
            border: '1px solid #25252b'
          }}
        >
          <span style={{ fontSize: '12px', color: '#aaa', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>{activeConfig.icon}</span>
            <span>Delivering: <strong>{activeConfig.name}</strong> (1080x1920 9:16 Vertical HD)</span>
          </span>
          <Button
            size="small"
            type="link"
            icon={<DownloadOutlined />}
            onClick={() => handleDirectDownload(activePlatform)}
            style={{ color: activeConfig.color, padding: 0, fontSize: '12px' }}
          >
            Direct Download
          </Button>
        </div>
      </Modal>

      {/* Bilibili popup */}
      <BilibiliManager
        visible={showBilibiliManager}
        onClose={() => setShowBilibiliManager(false)}
        projectId={projectId || ''}
        clipIds={[clip.id]}
        clipTitles={[clip.title || clip.generated_title || 'Video Clip']}
        onUploadSuccess={() => {
          console.log('submission successful')
        }}
      />

      {/* Caption Editor popup */}
      <CaptionEditorModal
        visible={showCaptionEditor}
        clip={clip}
        projectId={projectId || ''}
        onClose={() => setShowCaptionEditor(false)}
        onSubtitleUpdated={() => {
          setVideoVersion(Date.now())
          if (onClipUpdate) {
            onClipUpdate(clip.id, { updated_at: new Date().toISOString() } as any)
          }
        }}
      />
    </>
  )
}

export default ClipCard
