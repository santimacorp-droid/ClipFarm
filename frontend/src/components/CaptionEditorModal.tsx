import React, { useState, useEffect, useRef } from 'react'
import { 
  Modal, 
  Typography, 
  Button, 
  Space, 
  Input, 
  Select, 
  Switch, 
  Tooltip, 
  message, 
  Spin, 
  Empty, 
  Tag,
  Upload,
  Slider
} from 'antd'
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  DownloadOutlined, 
  SaveOutlined, 
  PlusOutlined, 
  DeleteOutlined, 
  SearchOutlined, 
  ScissorOutlined, 
  MergeCellsOutlined, 
  UndoOutlined, 
  ClockCircleOutlined,
  CloseOutlined,
  UploadOutlined,
  CheckCircleOutlined
} from '@ant-design/icons'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import { subtitleApi, SubtitleSegment, projectApi } from '../services/api'

const { Text, Title } = Typography
const { TextArea } = Input

interface CaptionEditorModalProps {
  visible: boolean
  clip: Clip | null
  projectId: string
  onClose: () => void
  onSubtitleUpdated?: () => void
}

const CAPTION_STYLES = [
  { value: 'hormozi_yellow', label: 'Hormozi Yellow (Active Word)' },
  { value: 'neon_green', label: 'Neon Green (Pop Accent)' },
  { value: 'neon_cyan', label: 'Neon Cyan (Modern Cool)' },
  { value: 'minimal_box', label: 'Clean Minimalist (Translucent Box)' },
  { value: 'none', label: 'Clean Subtitles (No Animation)' }
]

const formatSecondsToTimecode = (seconds: number): string => {
  if (seconds === undefined || seconds === null || isNaN(seconds) || seconds < 0) {
    return '00:00.00'
  }
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const cs = Math.floor((seconds % 1) * 100)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${cs.toString().padStart(2, '0')}`
}

export const CaptionEditorModal: React.FC<CaptionEditorModalProps> = ({
  visible,
  clip,
  projectId,
  onClose,
  onSubtitleUpdated
}) => {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [segments, setSegments] = useState<SubtitleSegment[]>([])
  const [originalSegments, setOriginalSegments] = useState<SubtitleSegment[]>([])
  const [searchText, setSearchText] = useState('')
  const [captionStyle, setCaptionStyle] = useState('hormozi_yellow')
  const [aspectRatio, setAspectRatio] = useState('9:16')
  const [dynamicZoom, setDynamicZoom] = useState(false)
  const [bgmTrack, setBgmTrack] = useState('none')
  const [customBgmPath, setCustomBgmPath] = useState<string | null>(null)
  const [bgmTracksList, setBgmTracksList] = useState<Array<{ id: string; name: string; description: string; default_volume: number; is_custom?: boolean; path?: string }>>([])
  const [bgmVolume, setBgmVolume] = useState(0.18)
  const [sfxEnabled, setSfxEnabled] = useState(false)
  const [reburnVideo, setReburnVideo] = useState(true)
  const [showHookBanner, setShowHookBanner] = useState(false)
  
  // Player state
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playbackRate, setPlaybackRate] = useState(1.0)
  const [autoScroll, setAutoScroll] = useState(true)
  const [videoVersion, setVideoVersion] = useState<number>(() => Date.now())

  const playerRef = useRef<ReactPlayer>(null)
  const segmentRefs = useRef<{ [key: number]: HTMLDivElement | null }>({})
  const listContainerRef = useRef<HTMLDivElement>(null)

  const clipId = clip?.id
  useEffect(() => {
    if (visible && clipId && projectId) {
      loadSubtitles()
      loadBgmTracks()
    } else if (!visible) {
      setSegments([])
      setOriginalSegments([])
      setPlaying(false)
      setCurrentTime(0)
    }
  }, [visible, clipId, projectId])

  const loadBgmTracks = async () => {
    try {
      const res = await subtitleApi.getBgmTracks()
      if (res?.tracks) {
        setBgmTracksList(res.tracks)
      }
    } catch (e) {
      console.warn('Failed to load BGM tracks list:', e)
    }
  }

  const loadSubtitles = async () => {
    if (!clipId || !projectId) return
    setLoading(true)
    try {
      const data = await subtitleApi.getClipSubtitles(projectId, clipId)
      const segs = (data?.segments || []).map((seg, idx) => ({
        ...seg,
        id: seg.id || `seg_${idx}_${Date.now()}`
      }))
      
      const draftKey = `caption_draft_${projectId}_${clipId}`
      const savedDraft = localStorage.getItem(draftKey)
      if (savedDraft) {
        try {
          const parsed = JSON.parse(savedDraft)
          if (Array.isArray(parsed) && parsed.length > 0) {
            setSegments(parsed)
            setOriginalSegments(JSON.parse(JSON.stringify(segs)))
            message.info('Restored unsaved caption draft')
            return
          }
        } catch {
          // Ignore draft parse failure
        }
      }
      
      setSegments(segs)
      setOriginalSegments(JSON.parse(JSON.stringify(segs)))
    } catch (error: any) {
      console.error('Failed to load subtitles:', error)
      message.error(`Failed to load subtitles: ${error?.message || 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  // Auto-save draft changes to localStorage
  useEffect(() => {
    if (segments && segments.length > 0 && clipId && projectId) {
      const draftKey = `caption_draft_${projectId}_${clipId}`
      localStorage.setItem(draftKey, JSON.stringify(segments))
    }
  }, [segments, clipId, projectId])

  // Active segment detection
  const activeSegmentIndex = segments.findIndex(
    (seg) => currentTime >= seg.startTime && currentTime <= seg.endTime
  )

  // Auto-scroll to active segment
  useEffect(() => {
    if (autoScroll && activeSegmentIndex !== -1 && segmentRefs.current[activeSegmentIndex]) {
      segmentRefs.current[activeSegmentIndex]?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest'
      })
    }
  }, [activeSegmentIndex, autoScroll])

  const handleSeek = (time: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(time, 'seconds')
      setCurrentTime(time)
    }
  }

  const handleTextChange = (index: number, newText: string) => {
    setSegments((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], text: newText }
      return updated
    })
  }

  const handleAddSegment = (index?: number) => {
    setSegments((prev) => {
      const updated = [...prev]
      let newStart = 0
      let newEnd = 2.0
      
      if (index !== undefined && index >= 0 && index < updated.length) {
        const current = updated[index]
        newStart = current.endTime
        newEnd = current.endTime + 2.0
        updated.splice(index + 1, 0, {
          id: `seg_${Date.now()}`,
          startTime: newStart,
          endTime: newEnd,
          text: 'New subtitle cue'
        })
      } else if (updated.length > 0) {
        const last = updated[updated.length - 1]
        newStart = last.endTime
        newEnd = last.endTime + 2.0
        updated.push({
          id: `seg_${Date.now()}`,
          startTime: newStart,
          endTime: newEnd,
          text: 'New subtitle cue'
        })
      } else {
        updated.push({
          id: `seg_${Date.now()}`,
          startTime: 0,
          endTime: 2.0,
          text: 'New subtitle cue'
        })
      }
      return updated
    })
  }

  const handleDeleteSegment = (index: number) => {
    setSegments((prev) => prev.filter((_, idx) => idx !== index))
  }

  const handleMergeNext = (index: number) => {
    if (index >= segments.length - 1) return
    setSegments((prev) => {
      const updated = [...prev]
      const current = updated[index]
      const next = updated[index + 1]
      updated[index] = {
        ...current,
        endTime: next.endTime,
        text: `${current.text} ${next.text}`.trim()
      }
      updated.splice(index + 1, 1)
      return updated
    })
  }

  const handleSplitSegment = (index: number) => {
    const target = segments[index]
    if (!target) return
    const midTime = target.startTime + (target.endTime - target.startTime) / 2
    const words = target.text.trim().split(/\s+/)
    let text1 = target.text
    let text2 = ''
    if (words.length > 1) {
      const midWord = Math.ceil(words.length / 2)
      text1 = words.slice(0, midWord).join(' ')
      text2 = words.slice(midWord).join(' ')
    } else if (target.text.length > 2) {
      const midChar = Math.ceil(target.text.length / 2)
      text1 = target.text.slice(0, midChar)
      text2 = target.text.slice(midChar)
    }

    setSegments((prev) => {
      const updated = [...prev]
      updated[index] = {
        ...target,
        endTime: midTime,
        text: text1
      }
      updated.splice(index + 1, 0, {
        id: `seg_${Date.now()}`,
        startTime: midTime,
        endTime: target.endTime,
        text: text2
      })
      return updated
    })
  }

  const handleAutoFixOverlaps = () => {
    setSegments((prev) => {
      const sorted = [...prev].sort((a, b) => a.startTime - b.startTime)
      const resolved: SubtitleSegment[] = []
      for (let i = 0; i < sorted.length; i++) {
        const st = Math.max(0, sorted[i].startTime)
        let et = Math.max(st + 0.1, sorted[i].endTime)
        if (i < sorted.length - 1) {
          const nextSt = sorted[i + 1].startTime
          if (et > nextSt && nextSt > st) {
            et = nextSt
          }
        }
        resolved.push({
          ...sorted[i],
          startTime: Number(st.toFixed(2)),
          endTime: Number(et.toFixed(2))
        })
      }
      return resolved
    })
    message.success('Auto-resolved all subtitle overlaps!')
  }

  const handleInsertAtCurrentTime = () => {
    const insertTime = Number(currentTime.toFixed(2))
    setSegments((prev) => {
      const updated = [...prev]
      const newCue: SubtitleSegment = {
        id: `seg_${Date.now()}`,
        startTime: insertTime,
        endTime: Number((insertTime + 2.0).toFixed(2)),
        text: 'New subtitle cue'
      }
      updated.push(newCue)
      updated.sort((a, b) => a.startTime - b.startTime)
      return updated
    })
    message.info(`Inserted subtitle at ${formatSecondsToTimecode(currentTime)}`)
  }

  const handleUploadBgm = async (file: File) => {
    message.loading({ content: 'Uploading custom BGM audio...', key: 'bgm_upload' })
    try {
      const res = await subtitleApi.uploadCustomBgm(file)
      if (res?.success && res.track) {
        setBgmTrack(res.track.id)
        setCustomBgmPath(res.track.path)
        message.success({ content: `Uploaded "${res.track.name}" successfully!`, key: 'bgm_upload' })
        loadBgmTracks()
      }
    } catch (err: any) {
      message.error({ content: `Upload failed: ${err?.message || 'Error'}`, key: 'bgm_upload' })
    }
    return false
  }

  const handleReset = () => {
    setSegments(JSON.parse(JSON.stringify(originalSegments)))
    message.info('Reverted to original captions')
  }

  const handleSave = async () => {
    if (!clip || !projectId) return
    setSaving(true)
    const hide = message.loading({ content: reburnVideo ? 'Saving captions and rendering video...' : 'Saving captions...', key: 'save_caps', duration: 0 })
    try {
      const res = await subtitleApi.updateClipSubtitles(projectId, clip.id, {
        segments,
        caption_style: captionStyle,
        reburn_video: reburnVideo,
        hook_title: clip.title || clip.generated_title || 'Highlight',
        show_hook_banner: showHookBanner,
        aspect_ratio: aspectRatio,
        dynamic_zoom: dynamicZoom,
        bgm_track: bgmTrack !== 'none' ? bgmTrack : undefined,
        bgm_volume: bgmVolume,
        sfx_enabled: sfxEnabled,
        custom_bgm_path: customBgmPath || undefined
      })
      
      setOriginalSegments(JSON.parse(JSON.stringify(segments)))
      localStorage.removeItem(`caption_draft_${projectId}_${clip.id}`)
      if (res.reburned) {
        setVideoVersion(Date.now())
      }
      message.success({ content: res.message || 'Captions saved successfully!', key: 'save_caps' })
      onSubtitleUpdated?.()
    } catch (error: any) {
      console.error('Failed to save subtitles:', error)
      message.error({ content: `Save failed: ${error?.message || 'Unknown error'}`, key: 'save_caps' })
    } finally {
      hide()
      setSaving(false)
    }
  }

  const handleDownloadSrt = () => {
    if (!clip || !projectId) return
    const srtLines: string[] = []
    segments.forEach((seg, idx) => {
      const s = formatSecondsToTimecode(seg.startTime).replace('.', ',')
      const e = formatSecondsToTimecode(seg.endTime).replace('.', ',')
      srtLines.push(`${idx + 1}\n00:${s}0 --> 00:${e}0\n${seg.text}\n`)
    })
    const blob = new Blob([srtLines.join('\n')], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${clip.title || clip.id}_captions.srt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredSegments = segments.map((seg, originalIndex) => ({ seg, originalIndex })).filter(({ seg }) => {
    if (!searchText) return true
    return seg.text.toLowerCase().includes(searchText.toLowerCase())
  })

  const rawVideoUrl = clip ? projectApi.getClipVideoUrl(projectId, clip.id, clip.title || clip.generated_title) : ''
  const videoUrl = rawVideoUrl ? `${rawVideoUrl}?v=${videoVersion}` : ''

  if (!clip) return null

  return (
    <Modal
      open={visible}
      onCancel={() => {
        setPlaying(false)
        onClose()
      }}
      footer={null}
      width={1100}
      centered
      destroyOnHidden
      styles={{
        body: {
          padding: 0,
          background: 'var(--ac-card, #211F22)',
          borderRadius: '16px',
          overflow: 'hidden'
        }
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '85vh', maxHeight: '820px' }}>
        {/* Header */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--ac-line, #2C2A2D)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--ac-card, #211F22)'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Title level={4} style={{ margin: 0, color: 'var(--ac-ink, #ECEAE6)', fontSize: '18px', fontWeight: 600 }}>
                Caption & Subtitle Editor
              </Title>
              <Tag style={{
                borderRadius: '999px',
                background: 'rgba(45, 107, 255, 0.12)',
                color: 'var(--ac-accent, #5A8BFF)',
                border: '1px solid rgba(45, 107, 255, 0.25)',
                fontSize: '11px',
                padding: '1px 8px'
              }}>
                {segments.length} cues
              </Tag>
            </div>
            <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '13px' }}>
              {clip.title || clip.generated_title || 'Untitled Clip'}
            </Text>
          </div>

          <Space size="middle">
            <Button
              type="text"
              icon={<UndoOutlined />}
              onClick={handleReset}
              disabled={loading || saving}
              style={{
                color: 'var(--ac-sub, #A6A29B)',
                borderRadius: '999px',
                border: '1px solid var(--ac-line, #2C2A2D)'
              }}
            >
              Reset
            </Button>
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={handleDownloadSrt}
              style={{
                color: 'var(--ac-sub, #A6A29B)',
                borderRadius: '999px',
                border: '1px solid var(--ac-line, #2C2A2D)'
              }}
            >
              Export SRT
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSave}
              style={{
                background: 'var(--ac-cta-bg, #ECEAE6)',
                color: 'var(--ac-cta-fg, #19181A)',
                borderRadius: '999px',
                fontWeight: 500,
                border: 'none',
                padding: '0 20px'
              }}
            >
              Save Captions
            </Button>
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={() => {
                setPlaying(false)
                onClose()
              }}
              style={{ color: 'var(--ac-sub, #A6A29B)' }}
            />
          </Space>
        </div>

        {/* Main Content Area */}
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          {/* Left Column: Video Player & Settings */}
          <div style={{
            width: '45%',
            borderRight: '1px solid var(--ac-line, #2C2A2D)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            overflowY: 'auto'
          }}>
            {/* Player Container */}
            <div style={{
              background: '#000',
              borderRadius: '12px',
              overflow: 'hidden',
              position: 'relative',
              boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '340px'
            }}>
              <ReactPlayer
                ref={playerRef}
                url={videoUrl}
                width="100%"
                height="340px"
                playing={playing}
                playbackRate={playbackRate}
                controls={false}
                style={{ objectFit: 'contain' }}
                onProgress={({ playedSeconds }) => setCurrentTime(playedSeconds)}
                onDuration={(dur) => setDuration(dur)}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
              />

              {/* Active Subtitle Overlay */}
              {activeSegmentIndex !== -1 && (
                <div style={{
                  position: 'absolute',
                  bottom: '12px',
                  left: '12px',
                  right: '12px',
                  background: 'rgba(0, 0, 0, 0.75)',
                  backdropFilter: 'blur(8px)',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  color: '#FFD700',
                  fontSize: '14px',
                  fontWeight: 600,
                  textAlign: 'center',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  pointerEvents: 'none'
                }}>
                  {segments[activeSegmentIndex]?.text}
                </div>
              )}
            </div>

            {/* Playback Controls Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'var(--ac-bg, #19181A)',
              padding: '10px 14px',
              borderRadius: '10px',
              border: '1px solid var(--ac-line, #2C2A2D)'
            }}>
              <Space size="middle">
                <Button
                  type="text"
                  icon={playing ? <PauseCircleOutlined style={{ fontSize: '24px', color: '#2D6BFF' }} /> : <PlayCircleOutlined style={{ fontSize: '24px', color: '#2D6BFF' }} />}
                  onClick={() => setPlaying(!playing)}
                  style={{ padding: 0, width: '32px', height: '32px' }}
                />
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', fontWeight: 600, fontFamily: 'monospace' }}>
                    {formatSecondsToTimecode(currentTime)}
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px', margin: '0 4px' }}>/</Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px', fontFamily: 'monospace' }}>
                    {formatSecondsToTimecode(duration)}
                  </Text>
                </div>
              </Space>

              {/* Speed Selector */}
              <Select
                size="small"
                value={playbackRate}
                onChange={setPlaybackRate}
                style={{ width: '80px' }}
                options={[
                  { value: 0.5, label: '0.5x' },
                  { value: 0.75, label: '0.75x' },
                  { value: 1.0, label: '1.0x' },
                  { value: 1.25, label: '1.25x' },
                  { value: 1.5, label: '1.5x' },
                  { value: 2.0, label: '2.0x' }
                ]}
              />
            </div>

            {/* Styling & Burn Settings */}
            <div style={{
              background: 'var(--ac-bg, #19181A)',
              borderRadius: '12px',
              padding: '16px',
              border: '1px solid var(--ac-line, #2C2A2D)',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px'
            }}>
              <Title level={5} style={{ margin: 0, color: 'var(--ac-ink, #ECEAE6)', fontSize: '14px' }}>
                Clip & Caption Styling
              </Title>

              <div>
                <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px', display: 'block', marginBottom: '6px' }}>
                  Caption Animation Style
                </Text>
                <Select
                  value={captionStyle}
                  onChange={setCaptionStyle}
                  style={{ width: '100%' }}
                  options={CAPTION_STYLES}
                />
              </div>

              <div>
                <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px', display: 'block', marginBottom: '6px' }}>
                  Video Format
                </Text>
                <Select
                  value={aspectRatio}
                  onChange={setAspectRatio}
                  style={{ width: '100%' }}
                  options={[
                    { value: '9:16', label: '📱 9:16 Vertical Blur (Shorts / Reels / TikTok)' },
                    { value: '9:16_crop', label: '📱 9:16 Fullscreen Fill (Cropped)' },
                    { value: 'original', label: '🖥️ Original / Landscape' }
                  ]}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px' }}>
                    Background Music (BGM)
                  </Text>
                  <Upload beforeUpload={handleUploadBgm} showUploadList={false} accept="audio/*">
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<UploadOutlined />} 
                      style={{ padding: 0, fontSize: '11px', color: '#2D6BFF' }}
                    >
                      Upload MP3/WAV
                    </Button>
                  </Upload>
                </div>
                <Select
                  value={bgmTrack}
                  onChange={(val) => {
                    setBgmTrack(val)
                    if (val.startsWith('custom:')) {
                      const found = bgmTracksList.find(t => t.id === val)
                      if (found?.path) setCustomBgmPath(found.path)
                    } else {
                      setCustomBgmPath(null)
                    }
                  }}
                  style={{ width: '100%' }}
                  options={
                    bgmTracksList.length > 0
                      ? bgmTracksList.map(t => ({
                          value: t.id,
                          label: t.name
                        }))
                      : [
                          { value: 'none', label: '🔇 None (Original Audio Only)' },
                          { value: 'suspense', label: '🎬 Suspense & Drama' },
                          { value: 'lofi', label: '☕ Lofi Chill' },
                          { value: 'upbeat', label: '⚡ Upbeat Pulse' }
                        ]
                  }
                />
              </div>

              {bgmTrack !== 'none' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '12px' }}>
                      BGM Volume
                    </Text>
                    <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '11px', fontWeight: 600 }}>
                      {Math.round(bgmVolume * 100)}%
                    </Text>
                  </div>
                  <Slider 
                    min={2} 
                    max={50} 
                    value={Math.round(bgmVolume * 100)} 
                    onChange={(val) => setBgmVolume(val / 100)} 
                    tooltip={{ formatter: (v) => `${v}%` }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', display: 'block' }}>
                    Dynamic Punch-in Zoom
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '11px' }}>
                    1.18x punch-in cuts on transitions
                  </Text>
                </div>
                <Switch checked={dynamicZoom} onChange={setDynamicZoom} size="small" />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', display: 'block' }}>
                    Sound Effects (SFX)
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '11px' }}>
                    Pop SFX on hook & transitions
                  </Text>
                </div>
                <Switch checked={sfxEnabled} onChange={setSfxEnabled} size="small" />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', display: 'block' }}>
                    Re-render Video
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '11px' }}>
                    Burn updated captions & effects directly into clip MP4
                  </Text>
                </div>
                <Switch checked={reburnVideo} onChange={setReburnVideo} size="small" />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', display: 'block' }}>
                    Hook Title Banner
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '11px' }}>
                    Show title banner at top
                  </Text>
                </div>
                <Switch checked={showHookBanner} onChange={setShowHookBanner} size="small" />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text style={{ color: 'var(--ac-ink, #ECEAE6)', fontSize: '13px', display: 'block' }}>
                    Auto-Scroll Subtitles
                  </Text>
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '11px' }}>
                    Follow timeline during playback
                  </Text>
                </div>
                <Switch checked={autoScroll} onChange={setAutoScroll} size="small" />
              </div>
            </div>
          </div>

          {/* Right Column: Editable Subtitle Timeline */}
          <div style={{
            width: '55%',
            display: 'flex',
            flexDirection: 'column',
            padding: '20px',
            background: 'var(--ac-card, #211F22)'
          }}>
            {/* Search & Actions Bar */}
            <div style={{
              display: 'flex',
              gap: '8px',
              marginBottom: '16px',
              alignItems: 'center',
              flexWrap: 'wrap'
            }}>
              <Input
                placeholder="Search caption text..."
                prefix={<SearchOutlined style={{ color: 'var(--ac-sub, #A6A29B)' }} />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
                style={{
                  borderRadius: '999px',
                  background: 'var(--ac-bg, #19181A)',
                  borderColor: 'var(--ac-line, #2C2A2D)',
                  color: 'var(--ac-ink, #ECEAE6)',
                  flex: 1,
                  minWidth: '140px'
                }}
              />
              <Tooltip title="Insert a new subtitle line at current playback position">
                <Button
                  type="default"
                  icon={<ClockCircleOutlined />}
                  onClick={handleInsertAtCurrentTime}
                  style={{
                    borderRadius: '999px',
                    borderColor: 'var(--ac-line, #2C2A2D)',
                    color: '#2D6BFF',
                    fontSize: '12px'
                  }}
                >
                  Insert @ Playhead
                </Button>
              </Tooltip>
              <Tooltip title="Automatically remove all cue time collisions and overlaps">
                <Button
                  type="default"
                  icon={<CheckCircleOutlined />}
                  onClick={handleAutoFixOverlaps}
                  style={{
                    borderRadius: '999px',
                    borderColor: 'var(--ac-line, #2C2A2D)',
                    color: '#52c41a',
                    fontSize: '12px'
                  }}
                >
                  Auto-Fix Overlaps
                </Button>
              </Tooltip>
              <Button
                type="dashed"
                icon={<PlusOutlined />}
                onClick={() => handleAddSegment()}
                style={{
                  borderRadius: '999px',
                  borderColor: 'var(--ac-line, #2C2A2D)',
                  color: 'var(--ac-ink, #ECEAE6)',
                  fontSize: '12px'
                }}
              >
                Add Cue
              </Button>
            </div>

            {/* Subtitle List */}
            <div
              ref={listContainerRef}
              style={{
                flex: 1,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                paddingRight: '6px'
              }}
            >
              {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '200px', gap: '12px' }}>
                  <Spin size="large" />
                  <Text style={{ color: 'var(--ac-sub, #A6A29B)', fontSize: '13px' }}>Loading captions...</Text>
                </div>
              ) : filteredSegments.length === 0 ? (
                <Empty
                  description={<span style={{ color: 'var(--ac-sub, #A6A29B)' }}>No captions found. Click "Add Cue" to create one.</span>}
                  style={{ margin: 'auto' }}
                />
              ) : (
                filteredSegments.map(({ seg, originalIndex }) => {
                  const isActive = originalIndex === activeSegmentIndex
                  return (
                    <div
                      key={seg.id || originalIndex}
                      ref={(el) => (segmentRefs.current[originalIndex] = el)}
                      style={{
                        background: isActive ? 'rgba(45, 107, 255, 0.08)' : 'var(--ac-bg, #19181A)',
                        borderRadius: '10px',
                        padding: '12px',
                        border: isActive
                          ? '1px solid var(--ac-accent, #5A8BFF)'
                          : '1px solid var(--ac-line, #2C2A2D)',
                        transition: 'all 0.15s ease',
                        boxShadow: isActive ? '0 0 12px rgba(90, 139, 255, 0.15)' : 'none'
                      }}
                    >
                      {/* Segment Header */}
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '8px'
                      }}>
                        {/* Timecode Badge / Click to seek */}
                        <Tooltip title="Click to jump player to this time">
                          <button
                            type="button"
                            onClick={() => handleSeek(seg.startTime)}
                            className="ac-mono"
                            style={{
                              background: isActive ? 'var(--ac-accent, #5A8BFF)' : 'rgba(255, 255, 255, 0.06)',
                              color: isActive ? '#FFFFFF' : 'var(--ac-ink, #ECEAE6)',
                              border: 'none',
                              borderRadius: '999px',
                              padding: '2px 10px',
                              fontSize: '11.5px',
                              fontWeight: 500,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px'
                            }}
                          >
                            <ClockCircleOutlined style={{ fontSize: '10px' }} />
                            {formatSecondsToTimecode(seg.startTime)} → {formatSecondsToTimecode(seg.endTime)}
                          </button>
                        </Tooltip>

                        {/* Quick Actions */}
                        <Space size={4}>
                          <Tooltip title="Add cue after">
                            <Button
                              type="text"
                              size="small"
                              icon={<PlusOutlined style={{ fontSize: '12px' }} />}
                              onClick={() => handleAddSegment(originalIndex)}
                              style={{ color: 'var(--ac-sub, #A6A29B)' }}
                            />
                          </Tooltip>
                          <Tooltip title="Split cue in half">
                            <Button
                              type="text"
                              size="small"
                              icon={<ScissorOutlined style={{ fontSize: '12px' }} />}
                              onClick={() => handleSplitSegment(originalIndex)}
                              style={{ color: 'var(--ac-sub, #A6A29B)' }}
                            />
                          </Tooltip>
                          {originalIndex < segments.length - 1 && (
                            <Tooltip title="Merge with next cue">
                              <Button
                                type="text"
                                size="small"
                                icon={<MergeCellsOutlined style={{ fontSize: '12px' }} />}
                                onClick={() => handleMergeNext(originalIndex)}
                                style={{ color: 'var(--ac-sub, #A6A29B)' }}
                              />
                            </Tooltip>
                          )}
                          <Tooltip title="Delete cue">
                            <Button
                              type="text"
                              size="small"
                              danger
                              icon={<DeleteOutlined style={{ fontSize: '12px' }} />}
                              onClick={() => handleDeleteSegment(originalIndex)}
                            />
                          </Tooltip>
                        </Space>
                      </div>

                      {/* Editable Text Area */}
                      <TextArea
                        value={seg.text}
                        onChange={(e) => handleTextChange(originalIndex, e.target.value)}
                        autoSize={{ minRows: 1, maxRows: 4 }}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--ac-ink, #ECEAE6)',
                          fontSize: '14px',
                          lineHeight: '1.5',
                          padding: '0 2px',
                          resize: 'none'
                        }}
                      />
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}

export default CaptionEditorModal
