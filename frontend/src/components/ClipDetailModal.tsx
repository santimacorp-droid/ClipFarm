import React, { useState, useEffect, useRef } from 'react'
import { Modal, Typography, Button, Tag, Space, Row, Col, Divider, Segmented, Input, message, Tooltip } from 'antd'
import { 
  PlayCircleOutlined, 
  DownloadOutlined, 
  ClockCircleOutlined, 
  StarFilled,
  CloseOutlined,
  FileTextOutlined,
  CopyOutlined,
  ReloadOutlined,
  SaveOutlined,
  ShareAltOutlined,
  FireOutlined
} from '@ant-design/icons'
import { Clip } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import EditableTitle from './EditableTitle'
import CaptionEditorModal from './CaptionEditorModal'

const { Text, Title } = Typography

interface ClipDetailModalProps {
  visible: boolean
  clip: Clip | null
  projectId: string
  onClose: () => void
  onDownload: (clipId: string) => void
}

const ClipDetailModal: React.FC<ClipDetailModalProps> = ({
  visible,
  clip,
  projectId,
  onClose,
  onDownload
}) => {
  const [playing, setPlaying] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [showCaptionEditor, setShowCaptionEditor] = useState(false)
  const [videoVersion, setVideoVersion] = useState<number>(() => Date.now())
  const [activePlatform, setActivePlatform] = useState<string>('tiktok')
  const videoRef = useRef<HTMLVideoElement>(null)

  // Social Caption & Hashtag State
  const [socialCopy, setSocialCopy] = useState<any>(() => clip?.social_copy || clip?.clip_metadata?.social_copy || null)
  const [activeCaptionTab, setActiveCaptionTab] = useState<string>('master')
  const [editableCaption, setEditableCaption] = useState<string>('')
  const [regeneratingSocial, setRegeneratingSocial] = useState<boolean>(false)
  const [savingSocial, setSavingSocial] = useState<boolean>(false)

  // Synchronize when clip changes
  useEffect(() => {
    const sc = clip?.social_copy || clip?.clip_metadata?.social_copy || null
    setSocialCopy(sc)
  }, [clip])

  // Synchronize editable text when tab or socialCopy changes
  useEffect(() => {
    if (!socialCopy) {
      const title = clip?.title || clip?.generated_title || 'Clip Highlight'
      const hook = clip?.clip_metadata?.hook_text || clip?.clip_metadata?.hook_title || title
      const highlights = (clip?.content && clip.content.length > 0) ? clip.content.slice(0, 2).join(' ') : ''
      const tags = clip?.hashtags?.length ? clip.hashtags.join(' ') : (clip?.clip_metadata?.hashtags?.length ? clip.clip_metadata.hashtags.join(' ') : '#shorts #reels #viral #trending')
      setEditableCaption(`${hook}\n\n${title}.\n${highlights}\n\nWhat are your thoughts on this? Share below 👇\n\n${tags}`)
      return
    }

    if (activeCaptionTab === 'tiktok') {
      const tt = socialCopy.platforms?.tiktok
      setEditableCaption(tt?.caption ? `${tt.caption}\n\n${tt.hashtags || ''}`.trim() : socialCopy.post_caption || '')
    } else if (activeCaptionTab === 'instagram') {
      const ig = socialCopy.platforms?.instagram
      setEditableCaption(ig?.caption ? `${ig.caption}\n\n${ig.hashtags || ''}`.trim() : socialCopy.post_caption || '')
    } else if (activeCaptionTab === 'youtube_shorts') {
      const yt = socialCopy.platforms?.youtube_shorts
      setEditableCaption(yt ? `${yt.title}\n\n${yt.description}\n\n${yt.hashtags || ''}`.trim() : socialCopy.post_caption || '')
    } else {
      setEditableCaption(socialCopy.post_caption || '')
    }
  }, [socialCopy, activeCaptionTab, clip])

  const handleRegenerateSocial = async () => {
    if (!clip) return
    setRegeneratingSocial(true)
    try {
      const res = await projectApi.generateSocialCaption(clip.id)
      if (res && res.social_copy) {
        setSocialCopy(res.social_copy)
        message.success('Regenerated dual-context social caption & hashtags!')
      }
    } catch (e: any) {
      message.error(`Failed to regenerate social caption: ${e?.message || 'Server error'}`)
    } finally {
      setRegeneratingSocial(false)
    }
  }

  const handleSaveSocial = async () => {
    if (!clip) return
    setSavingSocial(true)
    try {
      const updated = socialCopy ? { ...socialCopy } : {}
      if (activeCaptionTab === 'tiktok') {
        if (!updated.platforms) updated.platforms = {}
        if (!updated.platforms.tiktok) updated.platforms.tiktok = {}
        updated.platforms.tiktok.caption = editableCaption
      } else if (activeCaptionTab === 'instagram') {
        if (!updated.platforms) updated.platforms = {}
        if (!updated.platforms.instagram) updated.platforms.instagram = {}
        updated.platforms.instagram.caption = editableCaption
      } else if (activeCaptionTab === 'youtube_shorts') {
        if (!updated.platforms) updated.platforms = {}
        if (!updated.platforms.youtube_shorts) updated.platforms.youtube_shorts = {}
        updated.platforms.youtube_shorts.description = editableCaption
      } else {
        updated.post_caption = editableCaption
      }
      const res = await projectApi.updateSocialCaption(clip.id, updated)
      if (res && res.social_copy) {
        setSocialCopy(res.social_copy)
        message.success('Saved custom caption modifications!')
      }
    } catch (e: any) {
      message.error(`Failed to save caption: ${e?.message || 'Server error'}`)
    } finally {
      setSavingSocial(false)
    }
  }

  const handleCopyCurrentCaption = () => {
    navigator.clipboard.writeText(editableCaption)
    message.success('Copied caption to clipboard!')
  }

  const handleCopyTag = (tag: string) => {
    navigator.clipboard.writeText(tag)
    message.success(`Copied ${tag}`)
  }

  const meta = (clip?.clip_metadata || {}) as any
  const hasCta = Boolean(meta.cta_platforms || meta.cta_video_file || meta.cta_style)

  const formatTime = (timeStr: string) => {
    if (!timeStr) return '00:00:00'
    // Remove milliseconds after decimal point, keep only hours, minutes, and seconds
    return timeStr.replace(',', '.').substring(0, 8)
  }

  const getDuration = () => {
    if (!clip?.start_time || !clip?.end_time) return '00:00:00'
    const start = clip.start_time.replace(',', '.')
    const end = clip.end_time.replace(',', '.')
    return `${start.substring(0, 8)} - ${end.substring(0, 8)}`
  }

  const getScoreColor = (score: number) => {
    // Set different colors based on score ranges
    if (score >= 0.9) return '#52c41a' // Green - Excellent
    if (score >= 0.8) return '#1890ff' // Blue - Good
    if (score >= 0.7) return '#faad14' // Orange - Fair
    if (score >= 0.6) return '#ff7a45' // Red-orange - Poor
    return '#ff4d4f' // Red - Poor
  }

  const handleDownload = async () => {
    if (!clip) return
    if (hasCta && activePlatform) {
      window.open(`/api/v1/clips/${clip.id}/download?platform=${activePlatform}`, '_blank')
    } else {
      setDownloading(true)
      try {
        await onDownload(clip.id)
      } finally {
        setDownloading(false)
      }
    }
  }

  const handleClose = () => {
    if (videoRef.current) {
      videoRef.current.pause()
    }
    setPlaying(false)
    onClose()
  }

  const handleTogglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play()
      setPlaying(true)
    } else {
      videoRef.current.pause()
      setPlaying(false)
    }
  }

  if (!clip) return null

  return (
    <>
      <Modal
        visible={visible}
        onCancel={handleClose}
        footer={null}
        width={880}
        centered
        destroyOnClose
        style={{ top: 20 }}
        styles={{
          body: {
            padding: 0,
            background: 'rgba(26, 26, 46, 0.95)',
            borderRadius: '12px',
            maxHeight: '88vh',
            overflowY: 'auto'
          }
        }}
      >
        <div style={{ padding: '24px' }}>
          {/* header */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '20px'
          }}>
            <Title level={4} style={{ margin: 0, color: '#ffffff' }}>
              slice details
            </Title>
            <Button 
              type="text" 
              icon={<CloseOutlined />} 
              onClick={handleClose}
              style={{ color: '#cccccc' }}
            />
          </div>

          <Row gutter={24}>
            {/* Left-side video player */}
            <Col span={14}>
              {hasCta && (
                <div style={{ marginBottom: '8px' }}>
                  <Segmented
                    value={activePlatform}
                    onChange={(val) => setActivePlatform(String(val))}
                    options={[
                      { label: '📱 TikTok', value: 'tiktok' },
                      { label: '📷 Instagram', value: 'instagram' },
                      { label: '▶️ Shorts', value: 'youtube_shorts' },
                      { label: '📘 Facebook', value: 'facebook' },
                    ]}
                    block
                    size="small"
                  />
                </div>
              )}
              <div style={{ 
                background: '#000', 
                borderRadius: '8px', 
                overflow: 'hidden',
                marginBottom: '16px'
              }}>
                <video
                  ref={videoRef}
                  key={`${clip.id}_${activePlatform}_${videoVersion}`}
                  controls
                  preload="metadata"
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  style={{ width: '100%', height: '300px', borderRadius: '8px', objectFit: 'contain' }}
                >
                  <source
                    src={`/api/v1/clips/${clip.id}/video?v=${videoVersion}${hasCta ? `&platform=${activePlatform}` : ''}`}
                    type="video/mp4"
                  />
                  Your browser does not support video playback.
                </video>
              </div>

              {/* video info */}
              <div style={{ marginBottom: '16px' }}>
                <Space size="middle">
                  <Tag color="blue" icon={<ClockCircleOutlined />}>
                    {getDuration()}
                  </Tag>
                  {clip.final_score && (
                    <Tag 
                      icon={<StarFilled />}
                      style={{ 
                        background: getScoreColor(clip.final_score),
                        color: 'white',
                        border: 'none'
                      }}
                    >
                      rating: {(clip.final_score * 100).toFixed(0)}minutes
                    </Tag>
                  )}
                  {clip.outline && (
                    <Tag color="purple">{clip.outline}</Tag>
                  )}
                </Space>
              </div>

              {/* action buttons */}
              <Space wrap>
                <Button 
                  type="primary" 
                  icon={<PlayCircleOutlined />}
                  onClick={handleTogglePlay}
                  style={{ borderRadius: '999px' }}
                >
                  {playing ? 'Pause ' : 'play'}
                </Button>
                <Button 
                  type="default" 
                  icon={<FileTextOutlined />}
                  onClick={() => setShowCaptionEditor(true)}
                  style={{
                    borderRadius: '999px',
                    borderColor: 'rgba(90, 139, 255, 0.4)',
                    color: '#5A8BFF',
                    background: 'rgba(90, 139, 255, 0.08)'
                  }}
                >
                  edit subtitle
                </Button>
                <Button 
                  type="default" 
                  icon={<DownloadOutlined />}
                  loading={downloading}
                  onClick={handleDownload}
                  style={{ borderRadius: '999px' }}
                >
                  Download slice
                </Button>
              </Space>
            </Col>

            {/* Right-side detailed information */}
            <Col span={10}>
              <div style={{ color: '#ffffff' }}>
                {/* title */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ marginBottom: '8px' }}>
                    <EditableTitle
                      title={clip.generated_title || clip.title || 'Untagged segments'}
                      clipId={clip.id}
                      onTitleUpdate={(newTitle) => {
                        // updatecliptitle of
                        console.log('Title updated successfully:', newTitle)
                        // This may trigger the parent component's update callback
                      }}
                      style={{ color: '#ffffff', fontSize: '18px', fontWeight: '600' }}
                    />
                  </div>
                  <Text style={{ color: '#cccccc', fontSize: '12px' }}>
                    ID: {clip.id}
                  </Text>
                </div>

                <Divider style={{ borderColor: 'rgba(255,255,255,0.1)' }} />

                {/* Content highlights */}
                {clip.content && clip.content.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                      Content highlights:
                    </Text>
                    <div>
                      {clip.content.map((point, index) => (
                        <div key={index} style={{ 
                          color: '#cccccc', 
                          fontSize: '14px',
                          marginBottom: '4px',
                          padding: '4px 8px',
                          background: 'rgba(255,255,255,0.05)',
                          borderRadius: '4px'
                        }}>
                          • {point}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Timestamp information */}
                <div style={{ marginBottom: '16px' }}>
                  <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                    Time information:
                  </Text>
                  <div style={{ color: '#cccccc', fontSize: '14px' }}>
                    <div>Start time: {formatTime(clip.start_time)}</div>
                    <div>End time: {formatTime(clip.end_time)}</div>
                  </div>
                </div>

                {/* CTA Overlay information */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text strong style={{ color: '#ffffff' }}>
                      CTA Overlay:
                    </Text>
                    <Tag color={(clip as any)?.cta_style && (clip as any)?.cta_style !== 'none' ? 'orange' : 'default'}>
                      {(clip as any)?.cta_style && (clip as any)?.cta_style !== 'none'
                        ? `Active (${(clip as any)?.cta_platform || 'auto'})`
                        : 'Off / Project Default'}
                    </Tag>
                  </div>
                </div>

              </div>
            </Col>
          </Row>

          {/* Social Caption & Hashtag Section */}
          <Divider style={{ borderColor: 'rgba(255,255,255,0.12)', margin: '20px 0 16px 0' }} />
          
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '10px',
            padding: '16px 18px',
            border: '1px solid rgba(255, 255, 255, 0.08)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShareAltOutlined style={{ color: '#faad14', fontSize: '18px' }} />
                <Title level={5} style={{ margin: 0, color: '#ffffff', fontSize: '15px' }}>
                  Social Post Caption & Hashtags
                </Title>
                <Tag color="gold" style={{ fontSize: '11px', borderRadius: '4px' }}>
                  Dual-Context AI
                </Tag>
              </div>

              <Space size="small">
                <Button
                  size="small"
                  icon={<ReloadOutlined spin={regeneratingSocial} />}
                  loading={regeneratingSocial}
                  onClick={handleRegenerateSocial}
                  style={{
                    borderRadius: '6px',
                    fontSize: '12px',
                    borderColor: 'rgba(250, 173, 20, 0.4)',
                    color: '#faad14',
                    background: 'rgba(250, 173, 20, 0.08)'
                  }}
                >
                  Regenerate
                </Button>
                <Button
                  size="small"
                  icon={<SaveOutlined />}
                  loading={savingSocial}
                  onClick={handleSaveSocial}
                  style={{
                    borderRadius: '6px',
                    fontSize: '12px',
                    borderColor: 'rgba(82, 196, 26, 0.4)',
                    color: '#52c41a',
                    background: 'rgba(82, 196, 26, 0.08)'
                  }}
                >
                  Save
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<CopyOutlined />}
                  onClick={handleCopyCurrentCaption}
                  style={{
                    borderRadius: '6px',
                    fontSize: '12px',
                    background: '#faad14',
                    borderColor: '#faad14',
                    color: '#000',
                    fontWeight: '600'
                  }}
                >
                  Copy Caption
                </Button>
              </Space>
            </div>

            {/* Platform Segmented Tabs */}
            <div style={{ marginBottom: '12px' }}>
              <Segmented
                value={activeCaptionTab}
                onChange={(val) => setActiveCaptionTab(String(val))}
                options={[
                  { label: '📋 Master Copy', value: 'master' },
                  { label: '📱 TikTok (SEO)', value: 'tiktok' },
                  { label: '📸 Reels (Clean)', value: 'instagram' },
                  { label: '▶️ Shorts (CTR)', value: 'youtube_shorts' },
                ]}
                block
                size="middle"
              />
            </div>

            {/* Editable Caption Textarea */}
            <div style={{ marginBottom: '12px' }}>
              <Input.TextArea
                value={editableCaption}
                onChange={(e) => setEditableCaption(e.target.value)}
                rows={5}
                style={{
                  background: 'rgba(0, 0, 0, 0.35)',
                  borderColor: 'rgba(255, 255, 255, 0.15)',
                  color: '#ffffff',
                  borderRadius: '8px',
                  fontFamily: 'inherit',
                  fontSize: '13px',
                  lineHeight: '1.6'
                }}
                placeholder="Social post caption will appear here..."
              />
            </div>

            {/* Hashtag Cloud & Metadata */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {socialCopy?.hashtags && socialCopy.hashtags.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                  <Text style={{ color: '#aaaaaa', fontSize: '12px', marginRight: '4px' }}>
                    <FireOutlined style={{ color: '#ff7a45' }} /> Hashtags:
                  </Text>
                  {socialCopy.hashtags.map((tag: string, idx: number) => (
                    <Tooltip title="Click to copy" key={idx}>
                      <Tag
                        onClick={() => handleCopyTag(tag)}
                        style={{
                          cursor: 'pointer',
                          borderRadius: '4px',
                          background: 'rgba(90, 139, 255, 0.12)',
                          borderColor: 'rgba(90, 139, 255, 0.3)',
                          color: '#5A8BFF',
                          fontSize: '12px'
                        }}
                      >
                        {tag}
                      </Tag>
                    </Tooltip>
                  ))}
                  <Button
                    type="link"
                    size="small"
                    onClick={() => {
                      navigator.clipboard.writeText(socialCopy.hashtags.join(' '))
                      message.success('Copied all hashtags!')
                    }}
                    style={{ fontSize: '11px', padding: '0 4px', color: '#faad14' }}
                  >
                    Copy All Tags
                  </Button>
                </div>
              )}

              {socialCopy?.engagement_question && (
                <div style={{ fontSize: '12px', color: '#aaaaaa' }}>
                  <Text strong style={{ color: '#cccccc' }}>💡 Hook Question: </Text>
                  <span>{socialCopy.engagement_question}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>

      {/* Subtitle editing popup window */}
      <CaptionEditorModal
        visible={showCaptionEditor}
        clip={clip}
        projectId={projectId}
        onClose={() => setShowCaptionEditor(false)}
        onSubtitleUpdated={() => {
          setVideoVersion(Date.now())
        }}
      />
    </>
  )
}

export default ClipDetailModal 