import React, { useState, useEffect, useRef } from 'react'
import {
  Modal,
  Input,
  Button,
  Space,
  Typography,
  Select,
  message,
  Upload,
  Segmented,
  Divider
} from 'antd'
import {
  UploadCloud,
  Link2,
  FileVideo,
  Image as ImageIcon,
  Sparkles,
  X
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { campaignApi, CampaignSchema } from '../api/campaigns'

const { TextArea } = Input
const { Title, Text } = Typography

interface BriefPasteDialogProps {
  open: boolean
  onClose: () => void
  onCreated?: (campaignId: string) => void
}

export const BriefPasteDialog: React.FC<BriefPasteDialogProps> = ({
  open,
  onClose,
  onCreated
}) => {
  const navigate = useNavigate()
  const [campaignName, setCampaignName] = useState('')
  const [rawBrief, setRawBrief] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submittingStatus, setSubmittingStatus] = useState('')

  // Video source
  const [sourceType, setSourceType] = useState<'url' | 'file'>('url')
  const [videoUrl, setVideoUrl] = useState('')
  const [videoFile, setVideoFile] = useState<File | null>(null)

  // Watermark
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPosition, setLogoPosition] = useState<string>('top_right')

  // Auto-parsed preview state
  const [parsedPreview, setParsedPreview] = useState<Partial<CampaignSchema> | null>(null)
  const [isParsing, setIsParsing] = useState(false)
  const parseDebounceTimer = useRef<any>(null)

  // Reusable templates state
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; brand_name?: string }>>([])

  // Reset when dialog opens & load templates
  useEffect(() => {
    if (open) {
      setCampaignName('')
      setRawBrief('')
      setVideoUrl('')
      setVideoFile(null)
      setLogoFile(null)
      setLogoPosition('top_right')
      setParsedPreview(null)
      setSubmitting(false)
      setSubmittingStatus('')

      campaignApi.listTemplates()
        .then((res) => setTemplates(res || []))
        .catch((err) => console.warn('Failed to load templates:', err))
    }
  }, [open])

  const handleUseTemplate = async (templateId: string) => {
    setSubmitting(true)
    setSubmittingStatus('Creating from template...')
    try {
      const created = await campaignApi.createFromTemplate(templateId)
      message.success('Campaign created from template!')
      onClose()
      if (onCreated) {
        onCreated(created.id)
      } else {
        navigate(`/campaigns/${created.id}`)
      }
    } catch (err: any) {
      message.error(err.message || 'Failed to create from template')
    } finally {
      setSubmitting(false)
      setSubmittingStatus('')
    }
  }

  // Auto-parse brief whenever user pastes or edits text
  const handleBriefChange = (val: string) => {
    setRawBrief(val)
    if (parseDebounceTimer.current) clearTimeout(parseDebounceTimer.current)

    if (!val.trim()) {
      setParsedPreview(null)
      return
    }

    parseDebounceTimer.current = setTimeout(async () => {
      try {
        setIsParsing(true)
        const parsed = await campaignApi.parseBrief(val, false)
        setParsedPreview(parsed)

        // If campaign name is empty, auto-populate
        if (!campaignName && (parsed.campaign_name || parsed.brand_name)) {
          setCampaignName(parsed.campaign_name || `${parsed.brand_name} Campaign`)
        }

        // If video URL detected inside brief and user hasn't set one yet
        if (parsed.source_video_url && !videoUrl && !videoFile) {
          setVideoUrl(parsed.source_video_url)
          setSourceType('url')
        }

        // If logo position detected
        if (parsed.restrictions?.logo_position) {
          setLogoPosition(parsed.restrictions.logo_position)
        }
      } catch (e) {
        // Silent heuristic fallback
      } finally {
        setIsParsing(false)
      }
    }, 300)
  }

  const handleCreate = async () => {
    const finalName = campaignName.trim() || (parsedPreview?.brand_name ? `${parsedPreview.brand_name} Campaign` : 'New Brand Campaign')

    setSubmitting(true)
    try {
      setSubmittingStatus('Creating campaign draft...')
      const finalSchema = {
        ...(parsedPreview || {}),
        raw_brief: rawBrief,
        campaign_name: finalName,
        restrictions: {
          ...(parsedPreview?.restrictions || {}),
          logo_position: logoPosition
        }
      }

      const created = await campaignApi.create({
        name: finalName,
        brand_name: parsedPreview?.brand_name || '',
        schema_json: finalSchema as CampaignSchema
      })

      const newId = created.id

      // Upload local video file if provided
      if (sourceType === 'file' && videoFile) {
        setSubmittingStatus(`Uploading video footage (${(videoFile.size / (1024 * 1024)).toFixed(1)} MB)...`)
        await campaignApi.uploadVideo(newId, videoFile)
      } else if (sourceType === 'url' && videoUrl.trim()) {
        setSubmittingStatus('Queueing video download...')
        try {
          await campaignApi.importUrl(newId, videoUrl.trim())
        } catch (downloadErr) {
          console.warn('URL download queue note:', downloadErr)
        }
      }

      // Upload logo if provided
      if (logoFile) {
        setSubmittingStatus('Attaching watermark logo...')
        await campaignApi.uploadLogo(newId, logoFile)
      }

      message.success('Campaign studio ready!')
      onClose()
      if (onCreated) {
        onCreated(newId)
      } else {
        navigate(`/campaigns/${newId}`)
      }
    } catch (err: any) {
      console.error('Failed to create campaign:', err)
      message.error('Failed to create campaign: ' + (err.message || 'Error'))
    } finally {
      setSubmitting(false)
      setSubmittingStatus('')
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
      destroyOnHidden
      centered
      styles={{ body: { padding: '28px 32px' } }}
      style={{ borderRadius: '16px' }}
    >
      {/* Header */}
      <div style={{ marginBottom: '22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={18} style={{ color: 'var(--ac-accent, #2D6BFF)' }} />
          <Title level={4} style={{ margin: 0, fontWeight: 600, color: 'var(--ac-ink)' }}>
            New Brand Campaign
          </Title>
        </div>
        <Text type="secondary" style={{ fontSize: '13px', color: 'var(--ac-sub)' }}>
          Paste your campaign brief or brand guidelines. The system will parse the mandated moments, rules, and prepare your studio.
        </Text>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Reusable Templates Chips */}
        {templates.length > 0 && (
          <div>
            <Text strong style={{ fontSize: '11px', letterSpacing: '0.4px', textTransform: 'uppercase', display: 'block', marginBottom: '6px', color: 'var(--ac-sub)' }}>
              Or Start from Brand Template
            </Text>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {templates.map((t) => (
                <Button
                  key={t.id}
                  size="small"
                  onClick={() => handleUseTemplate(t.id)}
                  disabled={submitting}
                  style={{
                    borderRadius: '6px',
                    fontSize: '12px',
                    background: 'var(--ac-line-2, rgba(255,255,255,0.04))',
                    border: '1px solid var(--ac-line, #303030)'
                  }}
                >
                  ⚡ {t.brand_name || t.name}
                </Button>
              ))}
            </div>
            <Divider style={{ margin: '14px 0 6px 0', borderColor: 'var(--ac-line)' }} />
          </div>
        )}

        {/* Campaign Name */}
        <div>
          <Text strong style={{ fontSize: '12px', display: 'block', marginBottom: '6px', color: 'var(--ac-sub)' }}>
            CAMPAIGN TITLE
          </Text>
          <Input
            placeholder="e.g. Frida - Dr. Rosen Ep 1"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            style={{ borderRadius: '8px', height: '38px' }}
          />
        </div>

        {/* Brief Text Area */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <Text strong style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
              PASTE CAMPAIGN BRIEF
            </Text>
            {isParsing && (
              <Text type="secondary" style={{ fontSize: '11px' }}>
                Detecting rules...
              </Text>
            )}
          </div>
          <TextArea
            rows={5}
            placeholder={`Paste brief here. For example:
Brand: Frida
Duration: 30-60s
Moments to clip:
- "The moment she talks about sleep training"
- "When Dr. Rosen explains the fever threshold"
Watermark: Top right
Tags: #frida #parenting #pediatrics`}
            value={rawBrief}
            onChange={(e) => handleBriefChange(e.target.value)}
            style={{
              fontFamily: 'var(--ac-font-mono, monospace)',
              fontSize: '12.5px',
              borderRadius: '8px',
              resize: 'vertical'
            }}
          />

          {/* Quick detection preview chip */}
          {parsedPreview && (
            <div
              style={{
                marginTop: '8px',
                padding: '8px 12px',
                borderRadius: '6px',
                background: 'var(--ac-line-2, rgba(255,255,255,0.04))',
                border: '1px solid var(--ac-line, rgba(255,255,255,0.08))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '8px'
              }}
            >
              <Space size={12} wrap>
                {parsedPreview.brand_name && (
                  <Text style={{ fontSize: '12px', fontWeight: 600 }}>
                    🏷️ {parsedPreview.brand_name}
                  </Text>
                )}
                {parsedPreview.clip_duration && (
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    ⏱️ {(() => {
                      const minSec = Math.max(10, Number(parsedPreview.clip_duration.min_seconds) || 15);
                      const rawMax = Number(parsedPreview.clip_duration.max_seconds) || 90;
                      const maxSec = rawMax < 15 ? Math.max(60, minSec + 45) : rawMax;
                      const isMomentBased = Boolean(
                        parsedPreview.clip_duration.is_moment_based ||
                        (parsedPreview.clip_duration.min_seconds && parsedPreview.clip_duration.min_seconds <= 2)
                      );
                      return isMomentBased
                        ? `Moments (${minSec}-${maxSec}s)`
                        : `${minSec}-${maxSec}s`;
                    })()}
                  </Text>
                )}
                {parsedPreview.priority_moments && parsedPreview.priority_moments.length > 0 && (
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    🎬 {parsedPreview.priority_moments.length} moments detected
                  </Text>
                )}
              </Space>
              <Text style={{ fontSize: '11px', color: 'var(--ac-accent, #2D6BFF)' }}>
                ✓ Rules parsed
              </Text>
            </div>
          )}
        </div>

        {/* Source Footage Section */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <Text strong style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
              SOURCE FOOTAGE
            </Text>
            <Segmented
              size="small"
              options={[
                { label: 'YouTube / Web URL', value: 'url' },
                { label: 'Local File', value: 'file' }
              ]}
              value={sourceType}
              onChange={(v) => setSourceType(v as any)}
            />
          </div>

          {sourceType === 'url' ? (
            <Input
              prefix={<Link2 size={14} style={{ color: 'var(--ac-sub)', marginRight: '4px' }} />}
              placeholder="https://www.youtube.com/watch?v=... or direct video link"
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              style={{ borderRadius: '8px', height: '38px' }}
            />
          ) : (
            <div>
              {videoFile ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--ac-line, #303030)',
                    background: 'var(--ac-card)'
                  }}
                >
                  <Space size={8}>
                    <FileVideo size={16} style={{ color: 'var(--ac-accent, #2D6BFF)' }} />
                    <Text style={{ fontSize: '13px', fontWeight: 500 }}>{videoFile.name}</Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      ({(videoFile.size / (1024 * 1024)).toFixed(1)} MB)
                    </Text>
                  </Space>
                  <Button
                    type="text"
                    size="small"
                    icon={<X size={14} />}
                    onClick={() => setVideoFile(null)}
                  />
                </div>
              ) : (
                <Upload
                  accept=".mp4,.mov,.mkv,.webm"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    setVideoFile(file)
                    return false
                  }}
                >
                  <Button
                    icon={<UploadCloud size={14} />}
                    style={{ width: '100%', borderRadius: '8px', height: '38px' }}
                  >
                    Select Local Video File (.mp4 / .mov)
                  </Button>
                </Upload>
              )}
            </div>
          )}
        </div>

        {/* Watermark Section (Optional) */}
        <div>
          <Text strong style={{ fontSize: '12px', display: 'block', marginBottom: '8px', color: 'var(--ac-sub)' }}>
            BRAND WATERMARK (OPTIONAL)
          </Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: '10px' }}>
            {logoFile ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--ac-line, #303030)',
                  background: 'var(--ac-card)'
                }}
              >
                <Space size={8}>
                  <ImageIcon size={14} style={{ color: 'var(--ac-accent, #2D6BFF)' }} />
                  <Text style={{ fontSize: '12px' }}>{logoFile.name}</Text>
                </Space>
                <Button
                  type="text"
                  size="small"
                  icon={<X size={14} />}
                  onClick={() => setLogoFile(null)}
                />
              </div>
            ) : (
              <Upload
                accept="image/png,image/jpeg"
                showUploadList={false}
                beforeUpload={(file) => {
                  setLogoFile(file)
                  return false
                }}
              >
                <Button
                  icon={<UploadCloud size={14} />}
                  style={{ width: '100%', borderRadius: '8px', height: '38px' }}
                >
                  Attach Logo (.png)
                </Button>
              </Upload>
            )}

            <Select
              value={logoPosition}
              onChange={setLogoPosition}
              style={{ width: '100%', height: '38px' }}
              options={[
                { label: 'Top Right', value: 'top_right' },
                { label: 'Top Left', value: 'top_left' },
                { label: 'Bottom Right', value: 'bottom_right' },
                { label: 'Bottom Left', value: 'bottom_left' }
              ]}
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
          <Button onClick={onClose} disabled={submitting} style={{ borderRadius: '8px', height: '38px' }}>
            Cancel
          </Button>
          <Button
            type="primary"
            onClick={handleCreate}
            loading={submitting}
            style={{
              borderRadius: '8px',
              height: '38px',
              padding: '0 20px',
              background: 'var(--ac-cta-bg, #1A1A19)',
              color: 'var(--ac-cta-fg, #FFFFFF)',
              border: 'none',
              fontWeight: 500
            }}
          >
            {submitting ? submittingStatus || 'Creating Studio...' : 'Create & Open Studio'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default BriefPasteDialog
