import React, { useState, useEffect } from 'react'
import {
  Typography,
  Card,
  Row,
  Col,
  Button,
  Input,
  Select,
  Radio,
  Upload,
  Space,
  Tag,
  Divider,
  message,
  Spin,
  Alert,
  Tabs,
  Segmented,
  Switch
} from 'antd'
import {
  VideoCameraOutlined,
  UploadOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  FacebookOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  DeleteOutlined,
  CloudUploadOutlined
} from '@ant-design/icons'
import {
  affiliateApi,
  RecentAffiliateVideo,
  CandidateVideo,
  ProcessAffiliateResult
} from '../api/affiliate'

const { Title, Text, Paragraph } = Typography
const { Option } = Select

export const AffiliatePage: React.FC = () => {
  const [recentVideos, setRecentVideos] = useState<RecentAffiliateVideo[]>([])
  const [candidates, setCandidates] = useState<CandidateVideo[]>([])

  // Form state
  const [inputMode, setInputMode] = useState<'candidate' | 'path' | 'upload'>('candidate')
  const [selectedCandidatePath, setSelectedCandidatePath] = useState<string>('')
  const [manualPath, setManualPath] = useState<string>('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)

  const [language, setLanguage] = useState<string>('tl')
  const [engine, setEngine] = useState<string>('gemini')
  const [captionStyle, setCaptionStyle] = useState<string>('hormozi_yellow')
  const [fbHandle, setFbHandle] = useState<string>('@AffiliatePH')
  const [ctaStyle, setCtaStyle] = useState<string>('card')
  const [ctaPosition, setCtaPosition] = useState<string>('lower_middle')
  const [watermark, setWatermark] = useState<boolean>(true)

  // Transcription Slot state
  const [transcriptMode, setTranscriptMode] = useState<'slot' | 'ai'>('slot')
  const [transcriptInputType, setTranscriptInputType] = useState<'upload' | 'path' | 'text'>('upload')
  const [uploadedTranscriptFile, setUploadedTranscriptFile] = useState<File | null>(null)
  const [manualTranscriptPath, setManualTranscriptPath] = useState<string>('')
  const [transcriptText, setTranscriptText] = useState<string>('')

  // Processing state
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState<ProcessAffiliateResult | null>(null)
  const [activePreviewUrl, setActivePreviewUrl] = useState<string | null>(null)

  const loadData = async () => {
    try {
      const [recent, cand] = await Promise.all([
        affiliateApi.getRecentVideos().catch(() => []),
        affiliateApi.getCandidateVideos().catch(() => [])
      ])
      if (recent) setRecentVideos(recent)
      if (cand) {
        setCandidates(cand)
        if (cand.length > 0) {
          setSelectedCandidatePath(cand[0].path)
        }
      }
      // If there are recent videos, set the latest as active preview with cache-buster
      if (recent && recent.length > 0) {
        setActivePreviewUrl(`${recent[0].video_url}&t=${Date.now()}`)
      }
    } catch (err) {
      console.error('Failed to load affiliate page data:', err)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleProcess = async () => {
    let videoPathToProcess = ''
    if (inputMode === 'candidate') {
      videoPathToProcess = selectedCandidatePath
    } else if (inputMode === 'path') {
      videoPathToProcess = manualPath.trim()
    }

    if (inputMode !== 'upload' && !videoPathToProcess) {
      message.error('Please select or specify an input video.')
      return
    }

    if (inputMode === 'upload' && !uploadedFile) {
      message.error('Please upload a video file first.')
      return
    }

    setProcessing(true)
    setResult(null)

    try {
      let res: ProcessAffiliateResult
      if (inputMode === 'upload' && uploadedFile) {
        const formData = new FormData()
        formData.append('video_file', uploadedFile)
        formData.append('fb_handle', fbHandle)
        formData.append('caption_style', captionStyle)
        formData.append('cta_style', ctaStyle)
        formData.append('cta_position', ctaPosition)
        formData.append('watermark', String(watermark))
        formData.append('language', language)
        formData.append('engine', engine)
        if (transcriptMode === 'slot') {
          if (transcriptInputType === 'upload' && uploadedTranscriptFile) {
            formData.append('transcript_file', uploadedTranscriptFile)
          } else if (transcriptInputType === 'text' && transcriptText.trim()) {
            formData.append('transcript_text', transcriptText.trim())
          }
        }
        res = await affiliateApi.processByUpload(formData)
      } else {
        const payload: any = {
          video_path: videoPathToProcess,
          fb_handle: fbHandle,
          caption_style: captionStyle,
          cta_style: ctaStyle,
          cta_position: ctaPosition,
          watermark: watermark,
          language: language,
          engine: engine
        }
        if (transcriptMode === 'slot') {
          if (transcriptInputType === 'upload' && uploadedTranscriptFile) {
            payload.transcript_text = await uploadedTranscriptFile.text()
          } else if (transcriptInputType === 'path' && manualTranscriptPath.trim()) {
            payload.transcript_path = manualTranscriptPath.trim()
          } else if (transcriptInputType === 'text' && transcriptText.trim()) {
            payload.transcript_text = transcriptText.trim()
          }
        }
        res = await affiliateApi.processByPath(payload)
      }

      setResult(res)
      setActivePreviewUrl(`${res.video_url}&t=${Date.now()}`)
      message.success('Affiliate video created successfully!')
      // Refresh recent videos list
      const rec = await affiliateApi.getRecentVideos()
      setRecentVideos(rec)
    } catch (err: any) {
      console.error('Affiliate processing error:', err)
      message.error(err?.response?.data?.detail || err?.message || 'Failed to process video')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div style={{ maxWidth: '1240px', margin: '0 auto', padding: '32px 24px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '32px' }}>
        <Space direction="horizontal" align="center" style={{ marginBottom: '8px' }}>
          <Title level={2} style={{ margin: 0, color: 'var(--ac-ink)' }}>
            Affiliate Video Studio
          </Title>
          <Tag color="blue" icon={<FacebookOutlined />}>
            Facebook Follow CTA
          </Tag>
          <Tag color="gold">
            Filipino / Tagalog Captions
          </Tag>
        </Space>
        <Paragraph style={{ color: 'var(--ac-sub)', fontSize: '15px', margin: 0 }}>
          Create high-retention affiliate product review videos. Automatically transcribes Filipino/Tagalog speech with word-level highlights, burns stylized social captions, and overlays an animated Facebook Follow Call-to-Action.
        </Paragraph>
      </div>

      <Row gutter={[24, 24]}>
        {/* Left Column: Video Configuration & Input */}
        <Col xs={24} lg={14}>
          <Card
            title={
              <Space>
                <VideoCameraOutlined style={{ color: '#1877F2' }} />
                <span>Video Setup & Styling</span>
              </Space>
            }
            style={{
              background: 'var(--ac-card)',
              borderColor: 'var(--ac-line)',
              borderRadius: '12px'
            }}
          >
            {/* Step 1: Choose Video Input */}
            <div style={{ marginBottom: '24px' }}>
              <Text strong style={{ display: 'block', marginBottom: '8px' }}>
                1. Select Input Video
              </Text>

              <Tabs
                activeKey={inputMode}
                onChange={(k) => setInputMode(k as any)}
                items={[
                  {
                    key: 'candidate',
                    label: 'Attached / Downloads',
                    children: (
                      <div>
                        {candidates.length === 0 ? (
                          <Text type="secondary">No local videos found in Downloads or data.</Text>
                        ) : (
                          <Select
                            style={{ width: '100%' }}
                            value={selectedCandidatePath}
                            onChange={(val) => setSelectedCandidatePath(val)}
                            placeholder="Choose from detected affiliate videos"
                          >
                            {candidates.map((c) => (
                              <Option key={c.path} value={c.path}>
                                {c.filename} ({c.size_mb} MB)
                              </Option>
                            ))}
                          </Select>
                        )}
                        <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--ac-sub)' }}>
                          Detected recent videos from your Downloads & data folders.
                        </div>
                      </div>
                    )
                  },
                  {
                    key: 'path',
                    label: 'Local File Path',
                    children: (
                      <div>
                        <Input
                          value={manualPath}
                          onChange={(e) => setManualPath(e.target.value)}
                          placeholder="/absolute/path/to/video.mp4"
                        />
                        <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--ac-sub)' }}>
                          Provide full filesystem path to any vertical or standard MP4/MOV video.
                        </div>
                      </div>
                    )
                  },
                  {
                    key: 'upload',
                    label: 'Upload File',
                    children: (
                      <Upload.Dragger
                        maxCount={1}
                        beforeUpload={(file) => {
                          setUploadedFile(file)
                          return false
                        }}
                        onRemove={() => setUploadedFile(null)}
                        accept="video/*"
                      >
                        <p className="ant-upload-drag-icon">
                          <UploadOutlined style={{ fontSize: '32px', color: '#1877F2' }} />
                        </p>
                        <p className="ant-upload-text">Click or drag MP4 video to this area to upload</p>
                        <p className="ant-upload-hint">Supports vertical 9:16 mobile videos and product reviews</p>
                      </Upload.Dragger>
                    )
                  }
                ]}
              />
            </div>

            <Divider style={{ borderColor: 'var(--ac-line-2)' }} />

            {/* Step 2: Transcription Slot & Audio Alignment */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <Text strong style={{ margin: 0 }}>
                  2. Transcription Slot & Alignment
                </Text>
                <Segmented
                  size="small"
                  value={transcriptMode}
                  onChange={(v) => setTranscriptMode(v as 'slot' | 'ai')}
                  options={[
                    { label: '📄 Provide Transcript File', value: 'slot' },
                    { label: '🤖 Auto-Transcribe with AI', value: 'ai' }
                  ]}
                />
              </div>

              {transcriptMode === 'slot' ? (
                <div style={{
                  background: 'var(--ac-card-sub, rgba(255,255,255,0.03))',
                  padding: '16px',
                  borderRadius: '8px',
                  border: '1px solid var(--ac-line)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <Text style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
                      Select input method for your transcription:
                    </Text>
                    <Radio.Group
                      size="small"
                      value={transcriptInputType}
                      onChange={(e) => setTranscriptInputType(e.target.value)}
                    >
                      <Radio.Button value="upload">Upload File</Radio.Button>
                      <Radio.Button value="path">File Path</Radio.Button>
                      <Radio.Button value="text">Paste Script / SRT</Radio.Button>
                    </Radio.Group>
                  </div>

                  {transcriptInputType === 'upload' && (
                    <div>
                      {uploadedTranscriptFile ? (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '12px 16px',
                          background: 'rgba(24, 119, 242, 0.08)',
                          borderRadius: '8px',
                          border: '1px solid #1877F2'
                        }}>
                          <Space>
                            <FileTextOutlined style={{ color: '#1877F2', fontSize: '20px' }} />
                            <div>
                              <Text strong style={{ display: 'block', fontSize: '13px' }}>{uploadedTranscriptFile.name}</Text>
                              <Text style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>
                                {(uploadedTranscriptFile.size / 1024).toFixed(1)} KB • Ready to align & burn
                              </Text>
                            </div>
                          </Space>
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => setUploadedTranscriptFile(null)}
                          />
                        </div>
                      ) : (
                        <Upload.Dragger
                          accept=".srt,.vtt,.txt,.json"
                          maxCount={1}
                          beforeUpload={(file) => {
                            setUploadedTranscriptFile(file)
                            return false
                          }}
                          showUploadList={false}
                          style={{ padding: '16px 0', background: 'transparent' }}
                        >
                          <p className="ant-upload-drag-icon" style={{ marginBottom: '8px' }}>
                            <CloudUploadOutlined style={{ fontSize: '28px', color: '#1877F2' }} />
                          </p>
                          <p style={{ margin: 0, fontSize: '13px', fontWeight: 500 }}>
                            Click or drag transcribed file here (.srt, .vtt, .txt, .json)
                          </p>
                          <p style={{ margin: '4px 0 0', fontSize: '11px', color: 'var(--ac-sub)' }}>
                            Timed subtitles (.srt, .vtt) are formatted directly; plain text scripts (.txt) are automatically aligned to audio.
                          </p>
                        </Upload.Dragger>
                      )}
                    </div>
                  )}

                  {transcriptInputType === 'path' && (
                    <div>
                      <Input
                        placeholder="/path/to/transcript.srt or script.txt"
                        value={manualTranscriptPath}
                        onChange={(e) => setManualTranscriptPath(e.target.value)}
                        prefix={<FileTextOutlined style={{ color: 'var(--ac-sub)' }} />}
                      />
                      <Text style={{ fontSize: '11px', color: 'var(--ac-sub)', display: 'block', marginTop: '6px' }}>
                        Enter the absolute or relative path to your local .srt, .vtt, or text file.
                      </Text>
                    </div>
                  )}

                  {transcriptInputType === 'text' && (
                    <div>
                      <Input.TextArea
                        rows={4}
                        placeholder="Paste your SRT cues or Filipino transcript text here..."
                        value={transcriptText}
                        onChange={(e) => setTranscriptText(e.target.value)}
                        style={{ fontSize: '12px' }}
                      />
                      <Text style={{ fontSize: '11px', color: 'var(--ac-sub)', display: 'block', marginTop: '6px' }}>
                        If raw text without timestamps is pasted, audio alignment will synchronize each phrase to the spoken video.
                      </Text>
                    </div>
                  )}
                </div>
              ) : (
                <Row gutter={16}>
                  <Col span={12}>
                    <Text style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '4px' }}>
                      Spoken Language
                    </Text>
                    <Select
                      style={{ width: '100%' }}
                      value={language}
                      onChange={(v) => setLanguage(v)}
                    >
                      <Option value="tl">🇵🇭 Tagalog / Filipino</Option>
                      <Option value="en">🇺🇸 English</Option>
                    </Select>
                  </Col>

                  <Col span={12}>
                    <Text style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '4px' }}>
                      Transcription AI Model
                    </Text>
                    <Select
                      style={{ width: '100%' }}
                      value={engine}
                      onChange={(v) => setEngine(v)}
                    >
                      <Option value="gemini">🌟 Gemini 2.5 Flash (Ultra Accurate Filipino)</Option>
                      <Option value="whisper">⚡ Local Whisper (CTranslate2)</Option>
                    </Select>
                  </Col>
                </Row>
              )}
            </div>

            <Divider style={{ borderColor: 'var(--ac-line-2)' }} />

            {/* Step 3: Caption Visual Style */}
            <div style={{ marginBottom: '24px' }}>
              <Text strong style={{ display: 'block', marginBottom: '10px' }}>
                3. Caption Visual Style
              </Text>
              <Select
                style={{ width: '100%' }}
                value={captionStyle}
                onChange={(v) => setCaptionStyle(v)}
              >
                <Option value="hormozi_yellow">⚡ Hormozi Yellow (Electric Yellow Highlight)</Option>
                <Option value="neon_green">🟢 Neon Green (High Contrast)</Option>
                <Option value="neon_cyan">🔵 Neon Cyan (Modern Social)</Option>
                <Option value="minimal_box">⬛ Minimalist Box (Translucent Dark)</Option>
                <Option value="none">Clean Subtitles (No Highlight)</Option>
              </Select>
            </div>

            <Divider style={{ borderColor: 'var(--ac-line-2)' }} />
            {/* Step 4: Facebook Follow CTA & Anti-Theft Watermark */}
            <div style={{ marginBottom: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <Text strong style={{ fontSize: '14px' }}>
                  4. Facebook Follow CTA & Anti-Theft Watermark
                </Text>
                <Tag color={watermark ? 'blue' : 'default'} icon={<FacebookOutlined />}>
                  {watermark ? 'Facebook Watermark Active' : 'Watermark Disabled'}
                </Tag>
              </div>

              <Row gutter={16} style={{ marginBottom: '12px' }}>
                <Col span={14}>
                  <Text style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '4px' }}>
                    Facebook Handle / Page Name
                  </Text>
                  <Input
                    prefix={<FacebookOutlined style={{ color: '#1877F2' }} />}
                    value={fbHandle}
                    onChange={(e) => setFbHandle(e.target.value)}
                    placeholder="@YourPage or MyShopPH"
                  />
                </Col>

                <Col span={10}>
                  <Text style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '4px' }}>
                    CTA Format
                  </Text>
                  <Radio.Group
                    value={ctaStyle}
                    onChange={(e) => setCtaStyle(e.target.value)}
                  >
                    <Radio.Button value="pill">Pill Button</Radio.Button>
                    <Radio.Button value="card">Card Badge</Radio.Button>
                  </Radio.Group>
                </Col>
              </Row>

              <div style={{ marginBottom: '14px' }}>
                <Text style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '4px' }}>
                  Overlay Position
                </Text>
                <Radio.Group
                  value={ctaPosition}
                  onChange={(e) => setCtaPosition(e.target.value)}
                  size="small"
                >
                  <Radio.Button value="lower_middle">Lower Middle (Recommended)</Radio.Button>
                  <Radio.Button value="lower_center">Lower Center</Radio.Button>
                  <Radio.Button value="lower_third">Lower Third</Radio.Button>
                  <Radio.Button value="bottom_center">Bottom Center</Radio.Button>
                </Radio.Group>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                background: 'rgba(24, 119, 242, 0.06)',
                borderRadius: '8px',
                border: '1px solid rgba(24, 119, 242, 0.2)'
              }}>
                <div>
                  <Text strong style={{ fontSize: '13px', display: 'block' }}>
                    🛡️ Persistent Facebook Anti-Theft Watermark
                  </Text>
                  <Text style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>
                    Stamps your Facebook handle badge throughout the video in lower middle so no one can steal your clip, then plays an animated Follow CTA at the end.
                  </Text>
                </div>
                <Switch
                  checked={watermark}
                  onChange={(checked) => setWatermark(checked)}
                  style={{ background: watermark ? '#1877F2' : undefined }}
                />
              </div>
            </div>

            {/* Submit Action */}
            <Button
              type="primary"
              size="large"
              block
              icon={<ThunderboltOutlined />}
              onClick={handleProcess}
              loading={processing}
              style={{
                height: '48px',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 600,
                background: '#1877F2',
                borderColor: '#1877F2'
              }}
            >
              {processing ? 'Processing Video (Transcribing & Burning)...' : 'Burn Captions & Apply Facebook CTA'}
            </Button>
          </Card>
        </Col>

        {/* Right Column: Player & Output Results */}
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <PlayCircleOutlined style={{ color: '#52c41a' }} />
                <span>Video Preview & Output</span>
              </Space>
            }
            style={{
              background: 'var(--ac-card)',
              borderColor: 'var(--ac-line)',
              borderRadius: '12px'
            }}
          >
            {processing ? (
              <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                <Spin size="large" />
                <Title level={4} style={{ marginTop: '20px', color: 'var(--ac-ink)' }}>
                  Creating Affiliate Video...
                </Title>
                <Paragraph style={{ color: 'var(--ac-sub)' }}>
                  1. Transcribing Filipino speech with word timestamps<br />
                  2. Generating active-word highlighted ASS subtitles<br />
                  3. Burning captions via FFmpeg libass<br />
                  4. Overlaying Facebook Follow CTA
                </Paragraph>
              </div>
            ) : activePreviewUrl ? (
              <div>
                {/* HTML5 Video Player */}
                <div
                  style={{
                    width: '100%',
                    background: '#000',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    display: 'flex',
                    justifyContent: 'center',
                    marginBottom: '16px'
                  }}
                >
                  <video
                    key={activePreviewUrl}
                    controls
                    autoPlay
                    style={{
                      maxHeight: '440px',
                      maxWidth: '100%',
                      objectFit: 'contain'
                    }}
                    src={activePreviewUrl}
                  >
                    Your browser does not support video playback.
                  </video>
                </div>

                {/* Video Info Badges */}
                {result && (
                  <Alert
                    type="success"
                    showIcon
                    message="Video Ready for Posting!"
                    description={
                      <div style={{ fontSize: '13px', marginTop: '4px' }}>
                        <div>Source / Engine: <b>{result.transcript_provided ? 'Custom Transcribed File' : (result.model_used || 'Gemini 2.5 Flash')}</b></div>
                        <div>Subtitle Cues: <b>{result.segment_count} segments</b> ({result.word_count} words)</div>
                        <div>Duration: <b>{result.video_duration.toFixed(1)}s</b> ({result.video_width}x{result.video_height})</div>
                        <div>Render Time: <b>{result.processing_time_sec}s</b></div>
                        <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {result.cta_watermark && <Tag color="blue">🛡️ Facebook Watermark Active</Tag>}
                        </div>
                      </div>
                    }
                    style={{ marginBottom: '16px' }}
                  />
                )}

                {/* Actions */}
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Button
                    type="primary"
                    icon={<DownloadOutlined />}
                    href={activePreviewUrl}
                    download
                  >
                    Download Video (MP4)
                  </Button>
                </Space>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ac-sub)' }}>
                <VideoCameraOutlined style={{ fontSize: '48px', color: 'var(--ac-line-2)', marginBottom: '16px' }} />
                <Paragraph>
                  Select a video and click "Burn Captions & Apply Facebook CTA" to generate and preview your affiliate clip here.
                </Paragraph>
              </div>
            )}
          </Card>

          {/* Recent Videos Section */}
          <Card
            title={
              <Space>
                <CheckCircleOutlined style={{ color: '#1877F2' }} />
                <span>Generated Affiliate Videos</span>
              </Space>
            }
            style={{
              marginTop: '20px',
              background: 'var(--ac-card)',
              borderColor: 'var(--ac-line)',
              borderRadius: '12px'
            }}
          >
            {recentVideos.length === 0 ? (
              <Text type="secondary">No affiliate videos generated yet.</Text>
            ) : (
              <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
                {recentVideos.map((rv) => (
                  <div
                    key={rv.filename}
                    onClick={() => setActivePreviewUrl(`${rv.video_url}&t=${Date.now()}`)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      border: '1px solid var(--ac-line-2)',
                      marginBottom: '8px',
                      background: activePreviewUrl && activePreviewUrl.startsWith(rv.video_url) ? 'rgba(24, 119, 242, 0.08)' : 'transparent'
                    }}
                  >
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '8px' }}>
                      <Text strong style={{ fontSize: '13px', display: 'block' }}>
                        {rv.filename}
                      </Text>
                      <Text type="secondary" style={{ fontSize: '11px' }}>
                        {rv.size_mb} MB
                      </Text>
                    </div>

                    <Space>
                      <Button
                        size="small"
                        icon={<PlayCircleOutlined />}
                        onClick={(e) => {
                          e.stopPropagation()
                          setActivePreviewUrl(`${rv.video_url}&t=${Date.now()}`)
                        }}
                      >
                        Play
                      </Button>
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        href={rv.video_url}
                        download
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Space>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default AffiliatePage
