import React, { useState, useEffect } from 'react'
import {
  Typography,
  Button,
  Space,
  Empty,
  Spin,
  message,
  Popconfirm,
  Row,
  Col
} from 'antd'
import { Plus, Play, Trash2, ArrowUpRight, Video, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { campaignApi, Campaign } from '../api/campaigns'
import BriefPasteDialog from '../components/BriefPasteDialog'

const { Title, Text, Paragraph } = Typography

export const CampaignsPage: React.FC = () => {
  const navigate = useNavigate()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)

  const loadCampaigns = async () => {
    try {
      const data = await campaignApi.list()
      setCampaigns(data || [])
    } catch (err: any) {
      console.error('Failed to load campaigns:', err)
      message.error('Failed to load campaigns')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCampaigns()
  }, [])

  // Poll every 4s if any campaign is active
  useEffect(() => {
    const isAnyActive = campaigns.some((c) =>
      ['downloading', 'transcribing', 'finding_moments', 'cutting', 'editing', 'active'].includes(c.status)
    )
    if (!isAnyActive) return

    const timer = setInterval(() => {
      loadCampaigns()
    }, 4000)

    return () => clearInterval(timer)
  }, [campaigns])

  const handleRunPipeline = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setRunningId(id)
    try {
      await campaignApi.run(id)
      message.success('Campaign pipeline started!')
      loadCampaigns()
    } catch (err: any) {
      message.error('Failed to run pipeline: ' + (err.message || 'Error'))
    } finally {
      setRunningId(null)
    }
  }

  const handleDeleteCampaign = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    try {
      await campaignApi.delete(id)
      message.success('Campaign deleted')
      loadCampaigns()
    } catch (err: any) {
      message.error('Delete failed: ' + (err.message || 'Error'))
    }
  }

  const renderStatusDot = (status: string) => {
    switch (status) {
      case 'done':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#5BB36A', fontWeight: 500 }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#5BB36A' }} />
            Ready
          </span>
        )
      case 'failed':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#E66A5C', fontWeight: 500 }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#E66A5C' }} />
            Failed
          </span>
        )
      case 'downloading':
      case 'transcribing':
      case 'finding_moments':
      case 'cutting':
      case 'editing':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--ac-accent, #2D6BFF)', fontWeight: 500 }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--ac-accent, #2D6BFF)' }} />
            Processing
          </span>
        )
      case 'draft':
      default:
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--ac-muted, #8c8c8c)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--ac-muted, #8c8c8c)' }} />
            Draft
          </span>
        )
    }
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 32px' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '36px'
        }}
      >
        <div>
          <Title
            level={2}
            style={{
              margin: 0,
              fontFamily: 'var(--ac-font-serif, Georgia, serif)',
              fontWeight: 400,
              fontSize: '32px',
              color: 'var(--ac-ink)'
            }}
          >
            Brand Campaigns
          </Title>
          <Paragraph type="secondary" style={{ marginTop: '8px', marginBottom: 0, fontSize: '14px', color: 'var(--ac-sub)' }}>
            Dedicated clipping engine for creator & brand briefs. Enforces mandated quotes, 9:16 vertical cuts, and watermark rules.
          </Paragraph>
        </div>
        <Button
          type="primary"
          icon={<Plus size={16} />}
          onClick={() => setDialogOpen(true)}
          style={{
            borderRadius: '999px',
            height: '40px',
            padding: '0 20px',
            background: 'var(--ac-cta-bg, #1A1A19)',
            color: 'var(--ac-cta-fg, #FFFFFF)',
            border: 'none',
            fontWeight: 500
          }}
        >
          New Campaign
        </Button>
      </div>

      {/* Campaigns Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Spin size="large" />
        </div>
      ) : campaigns.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '64px 24px',
            borderRadius: '16px',
            border: '1px dashed var(--ac-line, #303030)',
            background: 'var(--ac-card)'
          }}
        >
          <Empty
            description={
              <span style={{ color: 'var(--ac-sub)', fontSize: '14px' }}>
                No campaigns yet. Paste a brief from your brand sponsor or campaign guidelines to get started.
              </span>
            }
          >
            <Button
              type="primary"
              icon={<Sparkles size={15} />}
              onClick={() => setDialogOpen(true)}
              style={{
                borderRadius: '999px',
                marginTop: '12px',
                background: 'var(--ac-cta-bg, #1A1A19)',
                color: 'var(--ac-cta-fg, #FFFFFF)',
                border: 'none'
              }}
            >
              Paste Campaign Brief
            </Button>
          </Empty>
        </div>
      ) : (
        <Row gutter={[24, 24]}>
          {campaigns.map((camp) => (
            <Col xs={24} sm={12} lg={8} key={camp.id}>
              <div
                onClick={() => navigate(`/campaigns/${camp.id}`)}
                style={{
                  borderRadius: '16px',
                  border: '1px solid var(--ac-line, #303030)',
                  background: 'var(--ac-card)',
                  padding: '20px 22px',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  minHeight: '160px',
                  transition: 'border-color 0.2s, transform 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--ac-accent, #2D6BFF)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--ac-line, #303030)'
                }}
              >
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '10px'
                    }}
                  >
                    <span
                      style={{
                        fontSize: '11px',
                        letterSpacing: '0.6px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: '999px',
                        background: 'var(--ac-line-2, rgba(255,255,255,0.05))',
                        color: 'var(--ac-ink)',
                        border: '1px solid var(--ac-line, #303030)'
                      }}
                    >
                      {camp.brand_name || 'BRAND'}
                    </span>
                    {renderStatusDot(camp.status)}
                  </div>

                  <Text
                    strong
                    style={{
                      fontSize: '15px',
                      lineHeight: '1.4',
                      display: 'block',
                      color: 'var(--ac-ink)',
                      marginBottom: '8px'
                    }}
                  >
                    {camp.name}
                  </Text>

                  {camp.status_message && (
                    <Text
                      type="secondary"
                      style={{ fontSize: '12px', display: 'block', color: 'var(--ac-sub)', marginBottom: '12px' }}
                    >
                      {camp.status_message}
                    </Text>
                  )}
                </div>

                <div
                  style={{
                    borderTop: '1px solid var(--ac-line, rgba(255,255,255,0.06))',
                    paddingTop: '12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <Space size={6}>
                    <Video size={13} style={{ color: 'var(--ac-sub)' }} />
                    <Text type="secondary" style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
                      {camp.clips_count || 0} clips
                    </Text>
                  </Space>

                  <Space size={8} onClick={(e) => e.stopPropagation()}>
                    {(camp.status === 'draft' || camp.status === 'failed') && (
                      <Button
                        size="small"
                        icon={<Play size={11} />}
                        loading={runningId === camp.id}
                        onClick={(e) => handleRunPipeline(camp.id, e)}
                        style={{ borderRadius: '6px', fontSize: '12px' }}
                      >
                        Run
                      </Button>
                    )}
                    <Button
                      size="small"
                      type="link"
                      icon={<ArrowUpRight size={13} />}
                      onClick={() => navigate(`/campaigns/${camp.id}`)}
                      style={{ color: 'var(--ac-accent, #2D6BFF)', padding: '0 4px', fontSize: '12px' }}
                    >
                      Open Studio
                    </Button>
                    <Popconfirm
                      title="Delete Campaign"
                      description="Delete this campaign and all cut clips?"
                      onConfirm={() => handleDeleteCampaign(camp.id)}
                      okText="Delete"
                      okType="danger"
                      cancelText="Cancel"
                    >
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<Trash2 size={13} />}
                        onClick={(e) => e.stopPropagation()}
                        style={{ width: '26px', height: '26px', padding: 0 }}
                      />
                    </Popconfirm>
                  </Space>
                </div>
              </div>
            </Col>
          ))}
        </Row>
      )}

      {/* Brief Paste Dialog */}
      <BriefPasteDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false)
          loadCampaigns()
        }}
        onCreated={(id) => {
          setDialogOpen(false)
          navigate(`/campaigns/${id}`)
        }}
      />
    </div>
  )
}

export default CampaignsPage
