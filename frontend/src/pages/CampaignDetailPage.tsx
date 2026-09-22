import React, { useState, useEffect, useRef } from 'react'
import {
  Typography,
  Button,
  Space,
  Spin,
  message,
  Divider,
  Row,
  Col,
  Upload,
  Input,
  Segmented,
  Tooltip,
  Modal,
  Switch,
  Select
} from 'antd'
import {
  ArrowLeft,
  UploadCloud,
  FileVideo,
  Plus,
  Trash2,
  RefreshCw,
  Sparkles,
  Scissors,
  CheckCircle2,
  Download,
  RotateCcw
} from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import { campaignApi, Campaign, CampaignSchema, SourceVideoInfo, PriorityMoment } from '../api/campaigns'
import CampaignClipCard from '../components/CampaignClipCard'

const { Title, Text, Paragraph } = Typography

const MOMENT_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316']

export const CampaignDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [resetting, setResetting] = useState(false)

  // Source video element ref & playback state
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTime, setCurrentTime] = useState<number>(0)

  // Template modal state
  const [templateModalOpen, setTemplateModalOpen] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [savingTemplate, setSavingTemplate] = useState(false)

  // Source video state
  const [videoInfo, setVideoInfo] = useState<SourceVideoInfo>({ exists: false })
  const [sourcesList, setSourcesList] = useState<Array<SourceVideoInfo & { filename: string; is_active: boolean }>>([])
  const [uploadingVideo, setUploadingVideo] = useState(false)
  const [importingUrl, setImportingUrl] = useState(false)
  const [urlInput, setUrlInput] = useState('')

  // Logo state
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [hasLogo, setHasLogo] = useState(false)

  // Clip quantity limit state: 1, 2, 3, or 'all'
  const [maxClipsLimit, setMaxClipsLimit] = useState<number | 'all'>('all')

  // Output format state: 'blur_pad' | 'crop_center' | 'original'
  const [outputFormat, setOutputFormat] = useState<string>('blur_pad')

  // Subtitles & Captions state
  const [subtitleMode, setSubtitleMode] = useState<string>('native_preferred')
  const [captionStyle, setCaptionStyle] = useState<string>('hormozi_yellow')
  const [showHookBanner, setShowHookBanner] = useState<boolean>(true)

  const handleHookBannerChange = async (checked: boolean) => {
    setShowHookBanner(checked)
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        restrictions: {
          ...campaign.schema?.restrictions,
          show_hook_banner: checked
        }
      }
      setCampaign(prev => prev ? { ...prev, schema: updatedSchema as any } : prev)
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to save hook banner preference:', err)
    }
  }

  const handleFormatChange = async (format: string) => {
    setOutputFormat(format)
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        restrictions: {
          ...campaign.schema?.restrictions,
          output_format: format
        }
      }
      setCampaign(prev => prev ? { ...prev, schema: updatedSchema as any } : prev)
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to save format preference:', err)
    }
  }

  const handleCaptionModeChange = async (mode: string) => {
    setSubtitleMode(mode)
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        restrictions: {
          ...campaign.schema?.restrictions,
          subtitles: mode,
          caption_style: mode === 'styled_burned' ? (campaign.schema?.restrictions?.caption_style || captionStyle || 'hormozi_yellow') : campaign.schema?.restrictions?.caption_style
        }
      }
      setCampaign(prev => prev ? { ...prev, schema: updatedSchema as any } : prev)
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to save caption mode:', err)
    }
  }

  const handleCaptionStyleChange = async (style: string) => {
    setCaptionStyle(style)
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        restrictions: {
          ...campaign.schema?.restrictions,
          caption_style: style
        }
      }
      setCampaign(prev => prev ? { ...prev, schema: updatedSchema as any } : prev)
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to save caption style:', err)
    }
  }

  // Edit mode & Outro state
  const [editMode, setEditMode] = useState<string>(
    campaign?.schema?.restrictions?.edit_mode || 'moment_extraction'
  )
  const [outroStyle, setOutroStyle] = useState<string>(
    campaign?.schema?.restrictions?.outro_style || 'none'
  )
  const [outroHandle, setOutroHandle] = useState<string>(
    campaign?.schema?.restrictions?.outro_handle || ''
  )
  const [outroText, setOutroText] = useState<string>(
    campaign?.schema?.restrictions?.outro_text || ''
  )

  // CTA Overlay state
  const [ctaStyle, setCtaStyle] = useState<string>(
    campaign?.schema?.restrictions?.cta_style || 'none'
  )
  const [ctaPlatform, setCtaPlatform] = useState<string>(
    campaign?.schema?.restrictions?.cta_platform || 'auto'
  )
  const [ctaHandle, setCtaHandle] = useState<string>(
    campaign?.schema?.restrictions?.cta_handle || ''
  )
  const [ctaPosition, setCtaPosition] = useState<string>(
    campaign?.schema?.restrictions?.cta_position || 'bottom_right'
  )

  const _saveRestrictions = async (patch: Record<string, any>) => {
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        restrictions: { ...campaign.schema?.restrictions, ...patch }
      }
      setCampaign(prev => prev ? { ...prev, schema: updatedSchema as any } : prev)
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to save restrictions:', err)
    }
  }

  const handleEditModeChange = async (mode: string) => {
    setEditMode(mode)
    await _saveRestrictions({ edit_mode: mode })
  }
  const handleOutroStyleChange = async (style: string) => {
    setOutroStyle(style)
    await _saveRestrictions({ outro_style: style })
  }
  const handleOutroHandleBlur = async () => {
    await _saveRestrictions({ outro_handle: outroHandle })
  }
  const handleOutroTextBlur = async () => {
    await _saveRestrictions({ outro_text: outroText })
  }

  // Moment editing state
  const [editingMoments, setEditingMoments] = useState(false)
  const [momentsList, setMomentsList] = useState<PriorityMoment[]>([])

  const handleSaveTemplate = async () => {
    if (!id || !templateName.trim()) return
    setSavingTemplate(true)
    try {
      await campaignApi.saveAsTemplate(id, templateName.trim())
      message.success('Campaign saved as reusable template!')
      setTemplateModalOpen(false)
    } catch (err: any) {
      message.error(err.message || 'Failed to save template')
    } finally {
      setSavingTemplate(false)
    }
  }

  const loadDetails = async () => {
    if (!id) return
    try {
      const data = await campaignApi.get(id)
      setCampaign(data)
      if (data.schema?.priority_moments) {
        setMomentsList(data.schema.priority_moments)
      }
      if (data.schema?.max_clips) {
        setMaxClipsLimit(data.schema.max_clips)
      }
      if (data.schema?.restrictions?.output_format) {
        setOutputFormat(data.schema.restrictions.output_format)
      }
      if (data.schema?.restrictions?.subtitles) {
        setSubtitleMode(data.schema.restrictions.subtitles)
      }
      if (data.schema?.restrictions?.show_hook_banner !== undefined) {
        setShowHookBanner(Boolean(data.schema.restrictions.show_hook_banner))
      }
      if (data.schema?.restrictions?.caption_style) {
        setCaptionStyle(data.schema.restrictions.caption_style)
      }
      if (data.schema?.restrictions?.edit_mode) {
        setEditMode(data.schema.restrictions.edit_mode)
      }
      if (data.schema?.restrictions?.outro_style) {
        setOutroStyle(data.schema.restrictions.outro_style)
      }
      if (data.schema?.restrictions?.outro_handle) {
        setOutroHandle(data.schema.restrictions.outro_handle)
      }
      if (data.schema?.restrictions?.outro_text) {
        setOutroText(data.schema.restrictions.outro_text)
      }
      if (data.schema?.restrictions?.cta_style) {
        setCtaStyle(data.schema.restrictions.cta_style)
      }
      if (data.schema?.restrictions?.cta_platform) {
        setCtaPlatform(data.schema.restrictions.cta_platform)
      }
      if (data.schema?.restrictions?.cta_handle !== undefined) {
        setCtaHandle(data.schema.restrictions.cta_handle)
      }
      if (data.schema?.restrictions?.cta_position) {
        setCtaPosition(data.schema.restrictions.cta_position)
      }
      setHasLogo(Boolean(data.schema?.logo_url || data.schema?.restrictions?.logo_required))
    } catch (err: any) {
      console.error('Failed to load campaign:', err)
      message.error('Failed to load campaign details')
    } finally {
      setLoading(false)
    }
  }

  const loadVideoInfo = async () => {
    if (!id) return
    try {
      const info = await campaignApi.getSourceInfo(id)
      setVideoInfo(info)
      const list = await campaignApi.listSources(id)
      setSourcesList(list || [])
    } catch (err) {
      console.error('Failed to check source video info:', err)
    }
  }

  useEffect(() => {
    loadDetails()
    loadVideoInfo()
  }, [id])

  // Poll status while campaign is processing
  useEffect(() => {
    if (!campaign) return
    const isProcessing = ['downloading', 'transcribing', 'finding_moments', 'cutting', 'editing', 'active'].includes(campaign.status)
    if (!isProcessing) return

    const interval = setInterval(() => {
      loadDetails()
      loadVideoInfo()
    }, 3000)

    return () => clearInterval(interval)
  }, [campaign?.status])

  const handleRunPipeline = async (force: boolean = false) => {
    if (!id) return
    if (!videoInfo.exists && !campaign?.schema?.source_video_url) {
      message.warning('Please attach source video footage before cutting clips')
      return
    }

    setRunning(true)
    try {
      // Optimistically update local campaign status immediately
      const targetStatus = campaign?.schema?.restrictions?.edit_mode === 'full_video_edit' ? 'editing' : 'cutting'
      setCampaign(prev => prev ? {
        ...prev,
        status: targetStatus as any,
        status_message: targetStatus === 'editing' ? 'Editing full video — removing dead air...' : 'Preparing to cut campaign clips...'
      } : prev)

      await campaignApi.run(id, force)
      message.success(force ? 'Pipeline forced to re-run!' : 'Campaign clipping started!')
      await loadDetails()
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || 'Failed to start pipeline')
      await loadDetails()
    } finally {
      setRunning(false)
    }
  }

  const handleResetStatus = async () => {
    if (!id) return
    setResetting(true)
    try {
      await campaignApi.reset(id)
      message.success('Campaign status reset to draft. You can now re-cut clips.')
      await loadDetails()
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || 'Failed to reset pipeline')
    } finally {
      setResetting(false)
    }
  }

  const handleUploadVideo = async (file: File) => {
    if (!id) return
    setUploadingVideo(true)
    try {
      await campaignApi.uploadVideo(id, file)
      message.success(`Uploaded ${file.name}!`)
      await loadVideoInfo()
      await loadDetails()
    } catch (err: any) {
      message.error('Video upload failed: ' + (err.message || 'Error'))
    } finally {
      setUploadingVideo(false)
    }
  }

  const handleSelectSource = async (filename: string) => {
    if (!id) return
    try {
      await campaignApi.selectSource(id, filename)
      message.success(`Switched active footage to ${filename}`)
      await loadVideoInfo()
    } catch (err: any) {
      message.error('Failed to switch footage: ' + (err.message || 'Error'))
    }
  }

  const handleImportUrl = async () => {
    if (!id || !urlInput.trim()) return
    setImportingUrl(true)
    try {
      await campaignApi.importUrl(id, urlInput.trim())
      message.success('Video download started!')
      setUrlInput('')
      await loadVideoInfo()
      await loadDetails()
    } catch (err: any) {
      message.error('URL import failed: ' + (err.message || 'Error'))
    } finally {
      setImportingUrl(false)
    }
  }

  const handleUploadLogo = async (file: File) => {
    if (!id) return
    setUploadingLogo(true)
    try {
      await campaignApi.uploadLogo(id, file)
      message.success('Watermark logo uploaded!')
      setHasLogo(true)
      await loadDetails()
    } catch (err: any) {
      message.error('Logo upload failed: ' + (err.message || 'Error'))
    } finally {
      setUploadingLogo(false)
    }
  }

  const handleDeleteLogo = async () => {
    if (!id) return
    try {
      await campaignApi.deleteLogo(id)
      message.success('Watermark removed. Clean native footage will be cut.')
      setHasLogo(false)
      await loadDetails()
    } catch (err: any) {
      message.error('Failed to remove watermark')
    }
  }

  const handleClipLimitChange = async (val: number | 'all') => {
    setMaxClipsLimit(val)
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        max_clips: val === 'all' ? null : val
      }
      await campaignApi.update(id, updatedSchema as any)
    } catch (err) {
      console.warn('Failed to update clip limit:', err)
    }
  }

  const handleSaveMoments = async () => {
    if (!id || !campaign) return
    try {
      const updatedSchema = {
        ...campaign.schema,
        priority_moments: momentsList
      }
      await campaignApi.update(id, updatedSchema as any)
      message.success('Moments updated!')
      setEditingMoments(false)
      loadDetails()
    } catch (err: any) {
      message.error('Failed to update moments: ' + (err.message || 'Error'))
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!campaign) {
    return (
      <div style={{ maxWidth: '800px', margin: '60px auto', textAlign: 'center' }}>
        <Title level={3}>Campaign Not Found</Title>
        <Button onClick={() => navigate('/campaigns')}>Back to Campaigns</Button>
      </div>
    )
  }

  const schema = (campaign.schema || {}) as CampaignSchema
  const isProcessing = ['downloading', 'transcribing', 'finding_moments', 'cutting', 'editing', 'active'].includes(campaign.status)

  const formatDuration = (sec?: number) => {
    if (!sec) return '0:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  const isShortVideo = videoInfo.exists && (videoInfo.duration || 0) <= (schema.clip_duration?.max_seconds || 60)

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '32px 36px' }}>
      {/* Top Header Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '28px',
          paddingBottom: '20px',
          borderBottom: '1px solid var(--ac-line, #303030)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Button
            type="text"
            icon={<ArrowLeft size={16} />}
            onClick={() => navigate('/campaigns')}
            style={{ borderRadius: '999px', color: 'var(--ac-sub)' }}
          >
            Campaigns
          </Button>

          <Divider type="vertical" style={{ margin: 0, borderColor: 'var(--ac-line)' }} />

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.6px',
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '999px',
                  background: 'var(--ac-line-2, rgba(255,255,255,0.06))',
                  color: 'var(--ac-ink)',
                  border: '1px solid var(--ac-line)'
                }}
              >
                {campaign.brand_name || schema.brand_name || 'BRAND'}
              </span>
              <Title level={4} style={{ margin: 0, fontWeight: 600, color: 'var(--ac-ink)' }}>
                {campaign.name}
              </Title>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <Space size={16} align="center">
          {/* Clips Quantity Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              Output:
            </Text>
            <Segmented
              size="small"
              value={maxClipsLimit}
              onChange={(v) => handleClipLimitChange(v as any)}
              options={[
                { label: '1 Clip', value: 1 },
                { label: '2 Clips', value: 2 },
                { label: '3 Clips', value: 3 },
                { label: 'All Moments', value: 'all' }
              ]}
            />
          </div>

          {campaign.clips && campaign.clips.length > 0 && (
            <Button
              icon={<RefreshCw size={14} />}
              onClick={loadDetails}
              style={{ borderRadius: '999px' }}
            >
              Refresh
            </Button>
          )}

          {/* Save as Template */}
          <Button
            icon={<Sparkles size={14} />}
            onClick={() => {
              setTemplateName(`${campaign.brand_name || campaign.name} Template`)
              setTemplateModalOpen(true)
            }}
            style={{ borderRadius: '999px' }}
          >
            Save Template
          </Button>

          {/* Export ZIP */}
          <Button
            icon={<Download size={14} />}
            href={campaignApi.getExportUrl(campaign.id)}
            target="_blank"
            disabled={!campaign.clips || campaign.clips.length === 0}
            style={{ borderRadius: '999px' }}
          >
            Export ZIP
          </Button>

          {isProcessing && (
            <Button
              icon={<RotateCcw size={14} />}
              onClick={handleResetStatus}
              loading={resetting}
              style={{
                borderRadius: '999px',
                height: '38px',
                borderColor: 'var(--ac-line, #444)',
                color: 'var(--ac-sub)'
              }}
            >
              Reset Status
            </Button>
          )}

          <Button
            type="primary"
            icon={<Scissors size={15} />}
            loading={running || isProcessing}
            onClick={() => handleRunPipeline(false)}
            disabled={!videoInfo.exists && !schema.source_video_url}
            style={{
              borderRadius: '999px',
              height: '38px',
              padding: '0 20px',
              background: 'var(--ac-cta-bg, #1A1A19)',
              color: 'var(--ac-cta-fg, #FFFFFF)',
              border: 'none',
              fontWeight: 500
            }}
          >
            {isProcessing ? 'Cutting Clips...' : campaign.clips && campaign.clips.length > 0 ? 'Re-cut Clips' : 'Cut Campaign Clips'}
          </Button>
        </Space>
      </div>

      {/* Main Studio 2-Column Workbench */}
      <Row gutter={[28, 28]}>
        {/* Left Column: Source Footage, Multiple Files, Moments, Rules (Width 420px) */}
        <Col xs={24} lg={9}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Source Video Panel */}
            <div
              style={{
                borderRadius: '16px',
                border: '1px solid var(--ac-line, #303030)',
                background: 'var(--ac-card)',
                padding: '20px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <Text strong style={{ fontSize: '13px', letterSpacing: '0.4px', textTransform: 'uppercase', color: 'var(--ac-sub)' }}>
                  Source Video Footage
                </Text>
                {videoInfo.exists && (
                  <span style={{ fontSize: '12px', color: '#5BB36A', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle2 size={13} /> Ready
                  </span>
                )}
              </div>

              {/* Multiple Video Files Selector if more than 1 file exists */}
              {sourcesList.length > 1 && (
                <div style={{ marginBottom: '14px' }}>
                  <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginBottom: '6px' }}>
                    SELECT ACTIVE VIDEO ({sourcesList.length} FILES AVAILABLE)
                  </Text>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {sourcesList.map((src) => (
                      <Button
                        key={src.filename}
                        size="small"
                        type={src.is_active ? 'primary' : 'default'}
                        onClick={() => handleSelectSource(src.filename)}
                        style={{
                          borderRadius: '6px',
                          fontSize: '11.5px',
                          background: src.is_active ? 'var(--ac-cta-bg, #1A1A19)' : undefined
                        }}
                      >
                        {src.filename.slice(0, 16)} ({formatDuration(src.duration)})
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {videoInfo.exists ? (
                <div>
                  <div
                    style={{
                      borderRadius: '10px',
                      overflow: 'hidden',
                      background: '#000',
                      marginBottom: '10px',
                      maxHeight: '220px'
                    }}
                  >
                    <video
                      ref={videoRef}
                      src={campaignApi.getSourceVideoUrl(campaign.id)}
                      controls
                      onTimeUpdate={() => {
                        if (videoRef.current) setCurrentTime(videoRef.current.currentTime)
                      }}
                      style={{ width: '100%', height: '100%', maxHeight: '220px', objectFit: 'contain' }}
                    />
                  </div>

                  {/* Visual Moment Timeline */}
                  {videoInfo.duration && videoInfo.duration > 0 && (
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <Text type="secondary" style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.3px', textTransform: 'uppercase' }}>
                          Moment Timeline
                        </Text>
                        <Text type="secondary" style={{ fontSize: '11px' }}>
                          {formatDuration(currentTime)} / {formatDuration(videoInfo.duration)}
                        </Text>
                      </div>

                      {/* Timeline bar */}
                      <div
                        onClick={(e) => {
                          if (!videoRef.current || !videoInfo.duration) return
                          const rect = e.currentTarget.getBoundingClientRect()
                          const clickPos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
                          videoRef.current.currentTime = clickPos * videoInfo.duration
                        }}
                        style={{
                          position: 'relative',
                          height: '24px',
                          width: '100%',
                          borderRadius: '6px',
                          background: 'var(--ac-line-2, rgba(255,255,255,0.06))',
                          border: '1px solid var(--ac-line, #303030)',
                          overflow: 'hidden',
                          cursor: 'pointer'
                        }}
                      >
                        {/* Moment Blocks */}
                        {campaign.clips && campaign.clips.map((c, i) => {
                          if (c.start_sec == null || c.end_sec == null) return null
                          const dur = videoInfo.duration || 1
                          const leftPct = Math.max(0, Math.min(100, (c.start_sec / dur) * 100))
                          const widthPct = Math.max(1.5, Math.min(100 - leftPct, ((c.end_sec - c.start_sec) / dur) * 100))
                          const color = MOMENT_COLORS[i % MOMENT_COLORS.length]

                          return (
                            <Tooltip
                              key={c.id || i}
                              title={`${c.moment_name} (${formatDuration(c.start_sec)} – ${formatDuration(c.end_sec)}) • Click to jump`}
                            >
                              <div
                                onClick={(e) => {
                                  e.stopPropagation()
                                  if (videoRef.current && c.start_sec != null) {
                                    videoRef.current.currentTime = c.start_sec
                                    videoRef.current.play()
                                  }
                                }}
                                style={{
                                  position: 'absolute',
                                  left: `${leftPct}%`,
                                  width: `${widthPct}%`,
                                  top: 0,
                                  bottom: 0,
                                  background: color,
                                  opacity: 0.85,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  color: '#fff',
                                  fontSize: '10px',
                                  fontWeight: 600,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  padding: '0 2px',
                                  zIndex: 2,
                                  cursor: 'pointer',
                                  borderLeft: '1px solid rgba(255,255,255,0.4)',
                                  borderRight: '1px solid rgba(255,255,255,0.4)',
                                  transition: 'opacity 0.15s'
                                }}
                                onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                                onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.85')}
                              >
                                {widthPct > 8 ? c.moment_name : ''}
                              </div>
                            </Tooltip>
                          )
                        })}

                        {/* Current Playhead */}
                        {videoInfo.duration > 0 && (
                          <div
                            style={{
                              position: 'absolute',
                              left: `${(currentTime / videoInfo.duration) * 100}%`,
                              top: 0,
                              bottom: 0,
                              width: '2px',
                              background: '#fff',
                              boxShadow: '0 0 4px rgba(0,0,0,0.8)',
                              zIndex: 5,
                              pointerEvents: 'none'
                            }}
                          />
                        )}
                      </div>
                    </div>
                  )}

                  {/* 56s or Short Video Indicator */}
                  {isShortVideo && (
                    <div
                      style={{
                        padding: '6px 10px',
                        borderRadius: '6px',
                        background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
                        border: '1px solid var(--ac-line, #303030)',
                        fontSize: '12px',
                        marginBottom: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Sparkles size={13} style={{ color: 'var(--ac-accent, #2D6BFF)' }} />
                      <Text style={{ fontSize: '12px', color: 'var(--ac-ink)' }}>
                        Short footage ({formatDuration(videoInfo.duration)}). The full clip can be formatted directly.
                      </Text>
                    </div>
                  )}

                  {/* Edit Mode Selector */}
                  {(videoInfo.duration == null || videoInfo.duration <= 120) && (
                    <div style={{ marginTop: '10px', marginBottom: '14px' }}>
                      <Text type="secondary" style={{
                        fontSize: '10px', letterSpacing: '0.4px',
                        textTransform: 'uppercase', display: 'block', marginBottom: '6px'
                      }}>
                        Edit Mode
                      </Text>
                      <Segmented
                        size="small"
                        value={editMode}
                        onChange={(v) => handleEditModeChange(v as string)}
                        options={[
                          {
                            label: (
                              <Tooltip title="Find specific moments in the video and cut N clips — for long videos">
                                Moment Clips
                              </Tooltip>
                            ),
                            value: 'moment_extraction'
                          },
                          {
                            label: (
                              <Tooltip title="Keep full video, remove dead air, add outro — best when this video IS the content">
                                Full Edit
                              </Tooltip>
                            ),
                            value: 'full_video_edit'
                          },
                        ]}
                        style={{ width: '100%' }}
                      />
                      <Text type="secondary" style={{ fontSize: '10.5px', marginTop: '5px', display: 'block' }}>
                        {editMode === 'moment_extraction' && '✦ Extract N clips from long video (interviews, podcasts)'}
                        {editMode === 'full_video_edit'   && '✦ Edit entire video as 1 clip — removes dead air, adds outro'}
                      </Text>

                      {/* Outro controls — only visible in Full Edit mode */}
                      {editMode === 'full_video_edit' && (
                        <div style={{ marginTop: '10px' }}>
                          <Text type="secondary" style={{
                            fontSize: '10px', letterSpacing: '0.4px',
                            textTransform: 'uppercase', display: 'block', marginBottom: '6px'
                          }}>
                            Outro Card
                          </Text>
                          <Segmented
                            size="small"
                            value={outroStyle}
                            onChange={(v) => handleOutroStyleChange(v as string)}
                            options={[
                              { label: 'None',          value: 'none'          },
                              { label: 'Follow Handle', value: 'follow_handle' },
                              { label: 'Link in Bio',   value: 'check_bio'     },
                              { label: 'Custom',        value: 'custom_text'   },
                            ]}
                            style={{ width: '100%' }}
                          />
                          {outroStyle === 'follow_handle' && (
                            <Input
                              size="small"
                              placeholder="@handle  (e.g. @frida)"
                              value={outroHandle}
                              onChange={e => setOutroHandle(e.target.value)}
                              onBlur={handleOutroHandleBlur}
                              style={{ marginTop: '6px', borderRadius: '6px', fontSize: '11.5px' }}
                            />
                          )}
                          {outroStyle === 'custom_text' && (
                            <Input
                              size="small"
                              placeholder="Outro text (e.g. Check bio for link)"
                              value={outroText}
                              onChange={e => setOutroText(e.target.value)}
                              onBlur={handleOutroTextBlur}
                              style={{ marginTop: '6px', borderRadius: '6px', fontSize: '11.5px' }}
                            />
                          )}
                          <Text type="secondary" style={{ fontSize: '10.5px', marginTop: '5px', display: 'block' }}>
                            {outroStyle === 'none'          && '✦ No outro card'}
                            {outroStyle === 'follow_handle' && '✦ Appends 2.5s "Follow @handle" end card'}
                            {outroStyle === 'check_bio'     && '✦ Appends 2.5s "Link in bio" end card'}
                            {outroStyle === 'custom_text'   && '✦ Appends 2.5s custom text end card'}
                          </Text>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 9:16 Format Selector */}
                  <div style={{ marginTop: '10px', marginBottom: '14px' }}>
                    <Text
                      type="secondary"
                      style={{ fontSize: '10px', letterSpacing: '0.4px', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}
                    >
                      Output Format
                    </Text>
                    <Segmented
                      size="small"
                      value={outputFormat}
                      onChange={(v) => handleFormatChange(v as string)}
                      options={[
                        {
                          label: (
                            <Tooltip title="Fills black/blurred sides — safest for any content">
                              Blur Pad
                            </Tooltip>
                          ),
                          value: 'blur_pad'
                        },
                        {
                          label: (
                            <Tooltip title="Crops the center column — best for centered talking-head shots">
                              Crop Center
                            </Tooltip>
                          ),
                          value: 'crop_center'
                        },
                        {
                          label: (
                            <Tooltip title="Keep original aspect ratio — use if source is already 9:16">
                              Original
                            </Tooltip>
                          ),
                          value: 'original'
                        },
                      ]}
                      style={{ width: '100%' }}
                    />
                    <Text type="secondary" style={{ fontSize: '10.5px', marginTop: '5px', display: 'block' }}>
                      {outputFormat === 'blur_pad'    && '✦ Blurred background fills vertical frame — recommended for Reels & Shorts'}
                      {outputFormat === 'crop_center' && '✦ Center-crops to 9:16 — use only if speaker is always centered'}
                      {outputFormat === 'original'    && '✦ No conversion — use only if source is already vertical (9:16)'}
                    </Text>
                  </div>

                  {/* Caption Mode & Style Selector */}
                  <div style={{ marginTop: '10px', marginBottom: '14px' }}>
                    <Text
                      type="secondary"
                      style={{ fontSize: '10px', letterSpacing: '0.4px', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}
                    >
                      Captions
                    </Text>
                    <Segmented
                      size="small"
                      value={subtitleMode}
                      onChange={(v) => handleCaptionModeChange(v as string)}
                      options={[
                        {
                          label: <Tooltip title="No burned captions — use platform's native subtitle tool after posting">Native</Tooltip>,
                          value: 'native_preferred'
                        },
                        {
                          label: <Tooltip title="Burn styled captions directly into video (Hormozi-style word highlights)">Styled</Tooltip>,
                          value: 'styled_burned'
                        },
                        {
                          label: <Tooltip title="Generate a clean .srt file alongside the clip, not burned in">SRT File</Tooltip>,
                          value: 'clean_srt_only'
                        },
                        {
                          label: <Tooltip title="No captions at all">None</Tooltip>,
                          value: 'none'
                        },
                      ]}
                      style={{ width: '100%' }}
                    />

                    {/* Caption style picker — only visible when styled_burned is selected */}
                    {subtitleMode === 'styled_burned' && (
                      <div style={{ marginTop: '8px' }}>
                        <Text
                          type="secondary"
                          style={{ fontSize: '10px', letterSpacing: '0.4px', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}
                        >
                          Caption Style
                        </Text>
                        <Segmented
                          size="small"
                          value={captionStyle}
                          onChange={(v) => handleCaptionStyleChange(v as string)}
                          options={[
                            { label: '🟡 Hormozi', value: 'hormozi_yellow' },
                            { label: '🟢 Neon',    value: 'neon_green'     },
                            { label: '🔵 Cyan',    value: 'neon_cyan'      },
                            { label: '⬜ Minimal', value: 'minimal_box'    },
                          ]}
                          style={{ width: '100%' }}
                        />
                      </div>
                    )}

                    <Text type="secondary" style={{ fontSize: '10.5px', marginTop: '5px', display: 'block' }}>
                      {subtitleMode === 'native_preferred' && '✦ No captions burned — add via TikTok/Reels native tools after posting'}
                      {subtitleMode === 'styled_burned'    && '✦ Word-highlight captions burned into video (check campaign rules first)'}
                      {subtitleMode === 'clean_srt_only'   && '✦ .srt file generated alongside clip for manual upload'}
                      {subtitleMode === 'none'             && '✦ No captions — clean visual only'}
                    </Text>

                    {/* On-Screen Text Hook Banner Toggle */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed var(--ac-line, #303030)' }}>
                      <div>
                        <Text style={{ fontSize: '12px', display: 'block' }}>
                          🎣 Burn On-Screen Text Hook
                        </Text>
                        <Text type="secondary" style={{ fontSize: '10.5px' }}>
                          Display headline banner in opening 4.5s
                        </Text>
                      </div>
                      <Switch
                        size="small"
                        checked={showHookBanner}
                        onChange={handleHookBannerChange}
                      />
                    </div>

                    {/* CTA Overlay */}
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed var(--ac-line, #303030)' }}>
                      <Text type="secondary" style={{
                        fontSize: '10px', letterSpacing: '0.4px',
                        textTransform: 'uppercase', display: 'block', marginBottom: '6px'
                      }}>
                        CTA Overlay
                      </Text>

                      {/* Style selector */}
                      <Segmented
                        size="small"
                        value={ctaStyle}
                        onChange={async (v) => {
                          const val = v as string
                          setCtaStyle(val)
                          await _saveRestrictions({ cta_style: val })
                        }}
                        options={[
                          { label: 'Off',       value: 'none'            },
                          { label: 'Follow 👆', value: 'follow_tap'       },
                          { label: 'Subscribe', value: 'subscribe_click'  },
                          { label: 'Pulse',     value: 'follow_pulse'     },
                        ]}
                        style={{ width: '100%' }}
                      />

                      {ctaStyle !== 'none' && (
                        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {/* Platform selector */}
                          <Select
                            size="small"
                            value={ctaPlatform}
                            onChange={async (v) => {
                              setCtaPlatform(v)
                              await _saveRestrictions({ cta_platform: v })
                            }}
                            style={{ width: '100%', fontSize: '11.5px' }}
                            options={[
                              { label: '🤖 Auto-detect from campaign', value: 'auto' },
                              { label: '🎵 TikTok',                   value: 'tiktok' },
                              { label: '📸 Instagram',                value: 'instagram' },
                              { label: '▶️ YouTube',                  value: 'youtube' },
                              { label: '📱 YouTube Shorts',           value: 'youtube_shorts' },
                              { label: '👍 Facebook',                 value: 'facebook' },
                            ]}
                          />

                          {/* Handle input */}
                          <Input
                            size="small"
                            placeholder="Handle (e.g. @frida)"
                            value={ctaHandle}
                            onChange={e => setCtaHandle(e.target.value)}
                            onBlur={() => _saveRestrictions({ cta_handle: ctaHandle })}
                            style={{ borderRadius: '6px', fontSize: '11.5px' }}
                          />

                          {/* Position selector */}
                          <Segmented
                            size="small"
                            value={ctaPosition}
                            onChange={async (v) => {
                              const val = v as string
                              setCtaPosition(val)
                              await _saveRestrictions({ cta_position: val })
                            }}
                            options={[
                              { label: '◀ Left',   value: 'bottom_left'   },
                              { label: '▬ Center', value: 'bottom_center'  },
                              { label: 'Right ▶',  value: 'bottom_right'   },
                            ]}
                            style={{ width: '100%' }}
                          />

                          <Text type="secondary" style={{ fontSize: '10.5px' }}>
                            {ctaStyle === 'follow_tap'      && '✦ Animated finger taps Follow button → "Following ✓"'}
                            {ctaStyle === 'subscribe_click' && '✦ Button clicks → flashes red → "Subscribed ✓"'}
                            {ctaStyle === 'follow_pulse'    && '✦ Pulsing glow Follow button slides in'}
                          </Text>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space size={10} wrap>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {formatDuration(videoInfo.duration)}
                      </Text>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {videoInfo.width || '?'}x{videoInfo.height || '?'}
                      </Text>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {videoInfo.size_mb} MB
                      </Text>
                    </Space>
                    <Upload
                      accept=".mp4,.mov,.mkv,.webm"
                      showUploadList={false}
                      beforeUpload={(file) => {
                        handleUploadVideo(file)
                        return false
                      }}
                    >
                      <Button size="small" type="text" style={{ fontSize: '12px', color: 'var(--ac-accent, #2D6BFF)' }}>
                        + Add / Replace Video
                      </Button>
                    </Upload>
                  </div>
                </div>
              ) : (
                <div>
                  <div
                    style={{
                      padding: '20px',
                      borderRadius: '12px',
                      border: '1px dashed var(--ac-line, #303030)',
                      textAlign: 'center',
                      background: 'var(--ac-line-2, rgba(255,255,255,0.02))',
                      marginBottom: '12px'
                    }}
                  >
                    <FileVideo size={28} style={{ color: 'var(--ac-sub)', marginBottom: '8px' }} />
                    <Paragraph type="secondary" style={{ fontSize: '12px', margin: '0 0 12px 0' }}>
                      Upload episode, raw clips, or paste YouTube link
                    </Paragraph>
                    <Upload
                      accept=".mp4,.mov,.mkv,.webm"
                      showUploadList={false}
                      beforeUpload={(file) => {
                        handleUploadVideo(file)
                        return false
                      }}
                    >
                      <Button icon={<UploadCloud size={13} />} size="small" loading={uploadingVideo}>
                        Upload Video File
                      </Button>
                    </Upload>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <Input
                      size="small"
                      placeholder="Or paste YouTube / Web URL..."
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      onPressEnter={handleImportUrl}
                    />
                    <Button size="small" loading={importingUrl} onClick={handleImportUrl}>
                      Fetch
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Mandated Moments Panel */}
            <div
              style={{
                borderRadius: '16px',
                border: '1px solid var(--ac-line, #303030)',
                background: 'var(--ac-card)',
                padding: '20px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <Text strong style={{ fontSize: '13px', letterSpacing: '0.4px', textTransform: 'uppercase', color: 'var(--ac-sub)' }}>
                  Target Moments ({momentsList.length})
                </Text>
                {editingMoments ? (
                  <Space size={6}>
                    <Button size="small" type="text" onClick={() => setEditingMoments(false)} style={{ fontSize: '12px' }}>
                      Cancel
                    </Button>
                    <Button size="small" type="primary" onClick={handleSaveMoments} style={{ fontSize: '12px', borderRadius: '6px' }}>
                      Save
                    </Button>
                  </Space>
                ) : (
                  <Button size="small" type="text" onClick={() => setEditingMoments(true)} style={{ fontSize: '12px', color: 'var(--ac-accent, #2D6BFF)' }}>
                    Edit Moments
                  </Button>
                )}
              </div>

              {editingMoments ? (
                <div>
                  {momentsList.map((m, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        gap: '6px',
                        marginBottom: '8px',
                        alignItems: 'center'
                      }}
                    >
                      <Input
                        size="small"
                        value={m.name}
                        onChange={(e) => {
                          const next = [...momentsList]
                          next[idx] = { ...next[idx], name: e.target.value }
                          setMomentsList(next)
                        }}
                        placeholder="Scene title"
                        style={{ width: '35%' }}
                      />
                      <Input
                        size="small"
                        value={m.start_line || ''}
                        onChange={(e) => {
                          const next = [...momentsList]
                          next[idx] = { ...next[idx], start_line: e.target.value }
                          setMomentsList(next)
                        }}
                        placeholder="Spoken quote to match"
                        style={{ width: '60%' }}
                      />
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<Trash2 size={12} />}
                        onClick={() => setMomentsList(momentsList.filter((_, i) => i !== idx))}
                      />
                    </div>
                  ))}
                  <Button
                    size="small"
                    type="dashed"
                    icon={<Plus size={12} />}
                    onClick={() =>
                      setMomentsList([
                        ...momentsList,
                        { name: `Moment ${momentsList.length + 1}`, start_line: '', description: '' }
                      ])
                    }
                    style={{ width: '100%', marginTop: '6px', borderRadius: '6px' }}
                  >
                    Add Target Moment
                  </Button>
                </div>
              ) : momentsList.length === 0 ? (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  No specific moments mandated. The pipeline will cut highlight clips according to duration constraints.
                </Text>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {momentsList.map((m, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
                        border: '1px solid var(--ac-line, #303030)'
                      }}
                    >
                      <Text strong style={{ fontSize: '13px', display: 'block', color: 'var(--ac-ink)' }}>
                        {idx + 1}. {m.name}
                      </Text>
                      {m.start_line && (
                        <Text italic type="secondary" style={{ fontSize: '12px', display: 'block', marginTop: '3px' }}>
                          "{m.start_line}"
                        </Text>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Rules & Watermark Section */}
            <div
              style={{
                borderRadius: '16px',
                border: '1px solid var(--ac-line, #303030)',
                background: 'var(--ac-card)',
                padding: '20px'
              }}
            >
              <Text strong style={{ fontSize: '13px', letterSpacing: '0.4px', textTransform: 'uppercase', color: 'var(--ac-sub)', display: 'block', marginBottom: '14px' }}>
                Watermark & Brand Rules
              </Text>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Logo Watermark Status */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12.5px' }}>
                  <div>
                    <Text strong style={{ display: 'block' }}>Logo Watermark</Text>
                    <Text type="secondary" style={{ fontSize: '11.5px' }}>
                      {hasLogo ? `Position: ${(schema.restrictions?.logo_position || 'top_right').replace('_', ' ')}` : 'No watermark required (clean native post)'}
                    </Text>
                  </div>
                  <Space size={6}>
                    {hasLogo ? (
                      <Button size="small" type="text" danger onClick={handleDeleteLogo} style={{ fontSize: '11.5px' }}>
                        Remove Logo
                      </Button>
                    ) : (
                      <Upload
                        accept="image/png,image/jpeg"
                        showUploadList={false}
                        beforeUpload={(file) => {
                          handleUploadLogo(file)
                          return false
                        }}
                      >
                        <Button size="small" type="text" loading={uploadingLogo} style={{ fontSize: '11.5px', color: 'var(--ac-accent, #2D6BFF)' }}>
                          + Add Logo (.png)
                        </Button>
                      </Upload>
                    )}
                  </Space>
                </div>

                <Divider style={{ margin: '4px 0', borderColor: 'var(--ac-line)' }} />

                {/* Duration */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12.5px' }}>
                  <Text type="secondary">Target Duration</Text>
                  <Text strong>
                    {(() => {
                      const minSec = Math.max(10, Number(schema.clip_duration?.min_seconds) || 15);
                      const rawMax = Number(schema.clip_duration?.max_seconds) || 90;
                      const maxSec = rawMax < 15 ? Math.max(60, minSec + 45) : rawMax;
                      const isMomentBased = Boolean(
                        schema.clip_duration?.is_moment_based ||
                        (schema.clip_duration?.min_seconds && schema.clip_duration.min_seconds <= 2)
                      );
                      return isMomentBased
                        ? `Moments (${minSec}s – ${maxSec}s)`
                        : `${minSec}s – ${maxSec}s`;
                    })()}
                  </Text>
                </div>

                {/* Hashtags */}
                {schema.platform_tags && Object.keys(schema.platform_tags).length > 0 && (
                  <div>
                    <Text type="secondary" style={{ fontSize: '12px', display: 'block', marginBottom: '4px' }}>
                      Mandated Hashtags
                    </Text>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {Array.from(new Set([
                        ...(schema.platform_tags.tiktok || []),
                        ...(schema.platform_tags.instagram || []),
                        ...(schema.platform_tags.youtube_shorts || [])
                      ])).map((t, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: '11px',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            background: 'var(--ac-line-2, rgba(255,255,255,0.05))',
                            color: 'var(--ac-sub)',
                            border: '1px solid var(--ac-line, #303030)'
                          }}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Col>

        {/* Right Column: Generated Clips & Production Station (Flexible width) */}
        <Col xs={24} lg={15}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <Title level={3} style={{ margin: 0, fontSize: '20px', fontWeight: 600, color: 'var(--ac-ink)' }}>
              Campaign Clips ({campaign.clips?.length || 0})
            </Title>
            {campaign.status_message && (
              <Text type="secondary" style={{ fontSize: '13px', color: 'var(--ac-sub)' }}>
                {campaign.status_message}
              </Text>
            )}
          </div>

          {/* Processing State */}
          {isProcessing ? (
            <div
              style={{
                textAlign: 'center',
                padding: '56px 32px',
                borderRadius: '16px',
                border: '1px solid var(--ac-line, #303030)',
                background: 'var(--ac-card)'
              }}
            >
              <Spin size="large" />
              <Title level={4} style={{ marginTop: '20px', marginBottom: '8px', color: 'var(--ac-ink)' }}>
                {campaign.status === 'editing' ? 'Editing Full Video' : 'Cutting Mandated Clips'}
              </Title>
              <Paragraph type="secondary" style={{ maxWidth: '460px', margin: '0 auto 20px auto', fontSize: '13px' }}>
                {campaign.status_message || 'Transcribing speech, aligning priority moments, and rendering vertical 9:16 cuts.'}
              </Paragraph>
              <Space size="middle">
                <Button
                  size="small"
                  icon={<RotateCcw size={13} />}
                  onClick={handleResetStatus}
                  loading={resetting}
                  style={{
                    borderRadius: '8px',
                    borderColor: 'var(--ac-line, #444)',
                    fontSize: '12px',
                    color: 'var(--ac-sub)'
                  }}
                >
                  Stop &amp; Reset Status
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<Scissors size={13} />}
                  onClick={() => handleRunPipeline(true)}
                  loading={running}
                  style={{
                    borderRadius: '8px',
                    fontSize: '12px',
                    background: 'var(--ac-accent, #6366f1)',
                    borderColor: 'transparent'
                  }}
                >
                  Force Re-cut
                </Button>
              </Space>
            </div>
          ) : !campaign.clips || campaign.clips.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '64px 32px',
                borderRadius: '16px',
                border: '1px dashed var(--ac-line, #303030)',
                background: 'var(--ac-card)'
              }}
            >
              <Sparkles size={32} style={{ color: 'var(--ac-sub)', marginBottom: '12px' }} />
              <Title level={4} style={{ margin: '0 0 6px 0', fontWeight: 500, color: 'var(--ac-ink)' }}>
                Ready to Generate Clips
              </Title>
              <Paragraph type="secondary" style={{ maxWidth: '460px', margin: '0 auto 18px auto', fontSize: '13px' }}>
                {videoInfo.exists
                  ? isShortVideo
                    ? `Your footage is ${formatDuration(videoInfo.duration)}. Click "Cut Campaign Clips" to produce your compliant 9:16 vertical short.`
                    : `Footage is attached. Target output: ${maxClipsLimit === 'all' ? (momentsList.length > 0 ? `all ${momentsList.length} moments` : 'all moments across footage') : `${maxClipsLimit} clip(s)`}. Click "Cut Campaign Clips" to begin.`
                  : 'Please attach source video footage on the left to begin cutting clips.'}
              </Paragraph>
              {videoInfo.exists && (
                <Button
                  type="primary"
                  icon={<Scissors size={14} />}
                  onClick={() => handleRunPipeline()}
                  loading={running}
                  style={{
                    borderRadius: '999px',
                    background: 'var(--ac-cta-bg, #1A1A19)',
                    color: 'var(--ac-cta-fg, #FFFFFF)',
                    border: 'none',
                    padding: '0 22px'
                  }}
                >
                  Cut Campaign Clips
                </Button>
              )}
            </div>
          ) : (
            <Row gutter={[20, 20]}>
              {campaign.clips.map((clip) => (
                <Col xs={24} xl={12} key={clip.id}>
                  <CampaignClipCard
                    clip={clip}
                    campaignId={campaign.id}
                    brandName={campaign.brand_name || schema.brand_name}
                  />
                </Col>
              ))}
            </Row>
          )}
        </Col>
      </Row>

      {/* Save as Template Modal */}
      <Modal
        title="Save as Reusable Template"
        open={templateModalOpen}
        onCancel={() => setTemplateModalOpen(false)}
        onOk={handleSaveTemplate}
        confirmLoading={savingTemplate}
        okText="Save Template"
        cancelText="Cancel"
      >
        <Paragraph type="secondary" style={{ fontSize: '13px', marginBottom: '12px' }}>
          This will save the brand guidelines, logo, duration settings, and compliance rules as a reusable template for future episodes.
        </Paragraph>
        <Input
          placeholder="Template name"
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          onPressEnter={handleSaveTemplate}
        />
      </Modal>
    </div>
  )
}

export default CampaignDetailPage
