import React, { useState } from 'react'
import { Typography, Radio, Tabs, Button, message, Space, Divider, Input, Tag, Segmented } from 'antd'
import { Copy, Download, Check, ExternalLink, Edit2, RefreshCw } from 'lucide-react'
import { CampaignClip, campaignApi } from '../api/campaigns'
import ComplianceChecklist from './ComplianceChecklist'

const { Title, Text } = Typography

interface CampaignClipCardProps {
  clip: CampaignClip
  campaignId: string
  brandName?: string
}

export const CampaignClipCard: React.FC<CampaignClipCardProps> = ({
  clip,
  campaignId,
  brandName = 'Brand'
}) => {
  const [copiedTab, setCopiedTab] = useState<string | null>(null)

  // Active deliverable platform state (default: clip's cta_platform or 'tiktok')
  const defaultPlat = (clip.cta_platform && clip.cta_platform !== 'auto') ? clip.cta_platform : 'tiktok'
  const [activePlatform, setActivePlatform] = useState<string>(defaultPlat)

  // Choose initial caption from rank 1 if available
  const initialCaption =
    clip.caption_suggestions && clip.caption_suggestions.length > 0
      ? clip.caption_suggestions[0].text
      : ''
  const [chosenCaption, setChosenCaption] = useState<string>(initialCaption)

  // Text Hook & Platform Post Guide State
  const [clipHookText, setClipHookText] = useState<string>(clip.hook_text || '')
  const [isEditingHook, setIsEditingHook] = useState<boolean>(false)
  const [hookInput, setHookInput] = useState<string>(clip.hook_text || '')
  const [activeGuide, setActiveGuide] = useState<Record<string, any>>(clip.platform_post_guide || {})
  const [regenerating, setRegenerating] = useState<boolean>(false)
  const [savingCopy, setSavingCopy] = useState<boolean>(false)

  // Publish Log Tracker state per platform
  const [postUrlInputs, setPostUrlInputs] = useState<Record<string, string>>({})
  const [publishLog, setPublishLog] = useState<Array<{
    platform: string
    post_url: string
    published_at: string
    expires_at: string
  }>>(clip.publish_log || [])
  const [savingLogPlatform, setSavingLogPlatform] = useState<string | null>(null)

  const handleLogPost = async (platform: string) => {
    const url = (postUrlInputs[platform] || '').trim()
    if (!url) {
      message.warning('Please paste the URL of the published post')
      return
    }
    setSavingLogPlatform(platform)
    try {
      const res = await campaignApi.logPublish(campaignId, clip.id, {
        platform,
        post_url: url
      })
      if (res?.entry) {
        setPublishLog((prev) => {
          const filtered = prev.filter((e) => e.platform !== platform)
          return [...filtered, res.entry]
        })
        setPostUrlInputs((prev) => ({ ...prev, [platform]: '' }))
        message.success(`Logged published post on ${platform}!`)
      }
    } catch (err: any) {
      message.error(`Failed to log publish: ${err?.message || 'Error'}`)
    } finally {
      setSavingLogPlatform(null)
    }
  }

  const handleRemoveLog = async (platform: string) => {
    try {
      await campaignApi.removePublishLog(campaignId, clip.id, platform)
      setPublishLog((prev) => prev.filter((e) => e.platform !== platform))
      message.info(`Removed ${platform} post from tracker`)
    } catch (err: any) {
      message.error(`Failed to remove log: ${err?.message || 'Error'}`)
    }
  }

  const renderPublishTracker = (platform: string) => {
    const existing = publishLog.find((e) => e.platform === platform)

    if (existing) {
      const pubDate = existing.published_at ? new Date(existing.published_at).toLocaleDateString() : 'Recently'
      const expDate = existing.expires_at ? new Date(existing.expires_at).toLocaleDateString() : null
      const isExpired = existing.expires_at ? new Date() >= new Date(existing.expires_at) : false

      return (
        <div
          style={{
            marginTop: '12px',
            padding: '10px 14px',
            borderRadius: '8px',
            background: isExpired ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)',
            border: `1px solid ${isExpired ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            flexWrap: 'wrap'
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: isExpired ? '#ef4444' : '#10b981'
                }}
              >
                {isExpired ? 'Expired' : 'Live Post Logged'}
              </span>
              <a
                href={existing.post_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: '12px',
                  color: 'var(--ac-accent, #2D6BFF)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  textDecoration: 'underline'
                }}
              >
                View Post <ExternalLink size={11} />
              </a>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>
              Posted {pubDate} {expDate ? `· Must stay live until ${expDate}` : ''}
            </span>
          </div>

          <Button
            size="small"
            type="text"
            danger
            onClick={() => handleRemoveLog(platform)}
            style={{ fontSize: '11px', height: '24px', padding: '0 6px' }}
          >
            Remove
          </Button>
        </div>
      )
    }

    return (
      <div style={{ marginTop: '12px', display: 'flex', gap: '6px' }}>
        <Input
          size="small"
          placeholder={`Paste live ${platform} post URL to track compliance...`}
          value={postUrlInputs[platform] || ''}
          onChange={(e) =>
            setPostUrlInputs((prev) => ({ ...prev, [platform]: e.target.value }))
          }
          onPressEnter={() => handleLogPost(platform)}
          style={{ fontSize: '12px', borderRadius: '6px' }}
        />
        <Button
          size="small"
          type="default"
          onClick={() => handleLogPost(platform)}
          loading={savingLogPlatform === platform}
          style={{ borderRadius: '6px', fontSize: '12px', whiteSpace: 'nowrap' }}
        >
          Mark Posted
        </Button>
      </div>
    )
  }

  const videoUrl = campaignApi.videoUrl(campaignId, clip.id, activePlatform)

  const handleCopy = (text: string, tabKey: string) => {
    navigator.clipboard.writeText(text)
    setCopiedTab(tabKey)
    message.success('Copied to clipboard!')
    setTimeout(() => setCopiedTab(null), 2000)
  }

  const handleRegenerate = async () => {
    setRegenerating(true)
    try {
      const res = await campaignApi.regenerateClipCopy(campaignId, clip.id)
      if (res?.hook_text) {
        setClipHookText(res.hook_text)
        setHookInput(res.hook_text)
      }
      if (res?.platform_post_guide) {
        setActiveGuide(res.platform_post_guide)
      }
      message.success('Regenerated search-optimized copy & text hook!')
    } catch (err: any) {
      message.error(`Regeneration failed: ${err?.message || 'Error'}`)
    } finally {
      setRegenerating(false)
    }
  }

  const handleSaveHook = async () => {
    if (!hookInput.trim()) return
    setSavingCopy(true)
    try {
      const upper = hookInput.trim().toUpperCase()
      await campaignApi.updateClipCopy(campaignId, clip.id, { hook_text: upper })
      setClipHookText(upper)
      setIsEditingHook(false)
      message.success('Text hook updated!')
    } catch (err: any) {
      message.error(`Failed to update hook: ${err?.message || 'Error'}`)
    } finally {
      setSavingCopy(false)
    }
  }

  // Derive dynamic post guide based on selected caption or active guide
  const rawGuide = Object.keys(activeGuide).length > 0 ? activeGuide : (clip.platform_post_guide || {})
  const cleanBrand = brandName.toLowerCase().replace(/[^a-z0-9]/g, '')
  const fallbackTag = cleanBrand ? `#${cleanBrand}` : ''

  const tiktokTags = rawGuide.tiktok?.tags || fallbackTag
  const igTags = rawGuide.instagram?.tags || fallbackTag
  const ytTags = rawGuide.youtube_shorts?.tags || fallbackTag
  const fbTags = rawGuide.facebook?.tags || fallbackTag

  const currentTikTokPost = activeGuide.tiktok?.caption || (chosenCaption ? `${chosenCaption}\n\n${tiktokTags}`.trim() : rawGuide.tiktok?.caption || '')
  const currentIGPost = activeGuide.instagram?.caption || (chosenCaption ? `${chosenCaption}\n\n${igTags}`.trim() : rawGuide.instagram?.caption || '')
  const currentYTPost = activeGuide.youtube_shorts?.caption || (chosenCaption ? `${chosenCaption}\n\n${ytTags}`.trim() : rawGuide.youtube_shorts?.caption || '')
  const currentYTTitle = rawGuide.youtube_shorts?.title || clip.moment_name
  const currentFBPost = activeGuide.facebook?.caption || (chosenCaption ? `${chosenCaption}\n\n${fbTags}`.trim() : rawGuide.facebook?.caption || '')
  const currentFBTitle = rawGuide.facebook?.title || clip.moment_name

  const tabItems = [
    {
      key: 'tiktok',
      label: 'TikTok',
      children: (
        <div style={{ marginTop: '8px' }}>
          <div
            style={{
              background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
              padding: '12px 14px',
              borderRadius: '8px',
              border: '1px solid var(--ac-line, #303030)',
              whiteSpace: 'pre-wrap',
              fontSize: '12.5px',
              color: 'var(--ac-ink)',
              marginBottom: '10px',
              minHeight: '60px'
            }}
          >
            {currentTikTokPost || 'No caption generated'}
          </div>
          <Button
            size="small"
            icon={copiedTab === 'tiktok' ? <Check size={13} /> : <Copy size={13} />}
            onClick={() => handleCopy(currentTikTokPost, 'tiktok')}
            style={{ borderRadius: '6px', fontSize: '12px' }}
          >
            {copiedTab === 'tiktok' ? 'Copied' : 'Copy TikTok Post'}
          </Button>
          {renderPublishTracker('tiktok')}
        </div>
      )
    },
    {
      key: 'instagram',
      label: 'Instagram',
      children: (
        <div style={{ marginTop: '8px' }}>
          <div
            style={{
              background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
              padding: '12px 14px',
              borderRadius: '8px',
              border: '1px solid var(--ac-line, #303030)',
              whiteSpace: 'pre-wrap',
              fontSize: '12.5px',
              color: 'var(--ac-ink)',
              marginBottom: '10px',
              minHeight: '60px'
            }}
          >
            {currentIGPost || 'No caption generated'}
          </div>
          <Button
            size="small"
            icon={copiedTab === 'instagram' ? <Check size={13} /> : <Copy size={13} />}
            onClick={() => handleCopy(currentIGPost, 'instagram')}
            style={{ borderRadius: '6px', fontSize: '12px' }}
          >
            {copiedTab === 'instagram' ? 'Copied' : 'Copy Instagram Post'}
          </Button>
          {renderPublishTracker('instagram')}
        </div>
      )
    },
    {
      key: 'youtube_shorts',
      label: 'YouTube Shorts',
      children: (
        <div style={{ marginTop: '8px' }}>
          <Text strong style={{ fontSize: '12px', display: 'block', marginBottom: '4px', color: 'var(--ac-ink)' }}>
            Title: {currentYTTitle}
          </Text>
          <div
            style={{
              background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
              padding: '12px 14px',
              borderRadius: '8px',
              border: '1px solid var(--ac-line, #303030)',
              whiteSpace: 'pre-wrap',
              fontSize: '12.5px',
              color: 'var(--ac-ink)',
              marginBottom: '10px',
              minHeight: '50px'
            }}
          >
            {currentYTPost || 'No description'}
          </div>
          <Space size={8}>
            <Button
              size="small"
              icon={copiedTab === 'yt_title' ? <Check size={13} /> : <Copy size={13} />}
              onClick={() => handleCopy(currentYTTitle, 'yt_title')}
              style={{ borderRadius: '6px', fontSize: '12px' }}
            >
              {copiedTab === 'yt_title' ? 'Copied Title' : 'Copy Title'}
            </Button>
            <Button
              size="small"
              icon={copiedTab === 'youtube_shorts' ? <Check size={13} /> : <Copy size={13} />}
              onClick={() => handleCopy(currentYTPost, 'youtube_shorts')}
              style={{ borderRadius: '6px', fontSize: '12px' }}
            >
              {copiedTab === 'youtube_shorts' ? 'Copied Description' : 'Copy Description'}
            </Button>
          </Space>
          {renderPublishTracker('youtube_shorts')}
        </div>
      )
    },
    {
      key: 'facebook',
      label: 'Facebook',
      children: (
        <div style={{ marginTop: '8px' }}>
          <Text strong style={{ fontSize: '12px', display: 'block', marginBottom: '4px', color: 'var(--ac-ink)' }}>
            Title / Headline: {currentFBTitle}
          </Text>
          <div
            style={{
              background: 'var(--ac-line-2, rgba(255,255,255,0.03))',
              padding: '12px 14px',
              borderRadius: '8px',
              border: '1px solid var(--ac-line, #303030)',
              whiteSpace: 'pre-wrap',
              fontSize: '12.5px',
              color: 'var(--ac-ink)',
              marginBottom: '10px',
              minHeight: '60px'
            }}
          >
            {currentFBPost || 'No caption generated'}
          </div>
          <Space size={8}>
            <Button
              size="small"
              icon={copiedTab === 'fb_title' ? <Check size={13} /> : <Copy size={13} />}
              onClick={() => handleCopy(currentFBTitle, 'fb_title')}
              style={{ borderRadius: '6px', fontSize: '12px' }}
            >
              {copiedTab === 'fb_title' ? 'Copied Title' : 'Copy Title'}
            </Button>
            <Button
              size="small"
              icon={copiedTab === 'facebook' ? <Check size={13} /> : <Copy size={13} />}
              onClick={() => handleCopy(currentFBPost, 'facebook')}
              style={{ borderRadius: '6px', fontSize: '12px' }}
            >
              {copiedTab === 'facebook' ? 'Copied Post' : 'Copy Facebook Post'}
            </Button>
          </Space>
          {renderPublishTracker('facebook')}
        </div>
      )
    }
  ]

  return (
    <div
      style={{
        borderRadius: '16px',
        border: '1px solid var(--ac-line, #303030)',
        background: 'var(--ac-card)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          {clip.full_edit && (
            <span style={{
              fontSize: '10.5px', padding: '2px 8px', borderRadius: '999px',
              background: 'rgba(155,89,182,0.12)', color: '#9B59B6',
              border: '1px solid rgba(155,89,182,0.25)',
              display: 'inline-flex', alignItems: 'center', gap: '4px', marginBottom: '8px'
            }}>
              ✂️ Full Edit
              {clip.edited_duration && clip.original_duration && (
                <span style={{ opacity: 0.7, fontSize: '10px' }}>
                  {` · ${clip.original_duration.toFixed(0)}s → ${clip.edited_duration.toFixed(0)}s`}
                </span>
              )}
            </span>
          )}
          {clip.cta_style && clip.cta_style !== 'none' && (
            <span style={{
              fontSize: '10.5px', padding: '2px 8px', borderRadius: '999px',
              background: 'rgba(255,107,45,0.12)', color: '#FF6B2D',
              border: '1px solid rgba(255,107,45,0.25)',
              display: 'inline-flex', alignItems: 'center', gap: '4px', marginBottom: '8px',
              marginLeft: clip.full_edit ? '6px' : undefined
            }}>
              {clip.cta_platform === 'youtube' || clip.cta_platform === 'youtube_shorts'
                ? '🔔 Subscribe CTA'
                : '👆 Follow CTA'}
              {clip.cta_platform && ` · ${clip.cta_platform}`}
            </span>
          )}
          <Title level={4} style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--ac-ink)' }}>
            {clip.moment_name}
          </Title>
          {clip.matched_text && (
            <Text type="secondary" italic style={{ fontSize: '12px', display: 'block', marginTop: '2px', color: 'var(--ac-sub)' }}>
              "{clip.matched_text.slice(0, 80)}..."
            </Text>
          )}
        </div>
        <Space size={6}>
          {clip.duration_seconds && (
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: '999px',
                background: 'var(--ac-line-2, rgba(255,255,255,0.06))',
                border: '1px solid var(--ac-line, #303030)',
                color: 'var(--ac-ink)'
              }}
            >
              {clip.duration_seconds.toFixed(0)}s
            </span>
          )}
        </Space>
      </div>

      {/* On-Screen Text Hook Banner Pill */}
      <div
        style={{
          background: 'rgba(255, 184, 0, 0.08)',
          border: '1px solid rgba(255, 184, 0, 0.25)',
          borderRadius: '10px',
          padding: '10px 14px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '10px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: '16px' }}>🎣</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Text style={{ fontSize: '10.5px', color: '#FFB800', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                On-Screen Text Hook (Opening Banner)
              </Text>
              <span style={{ fontSize: '10px', color: 'var(--ac-sub)', opacity: 0.8 }}>· 0s - 4.5s</span>
            </div>
            {isEditingHook ? (
              <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                <Input
                  size="small"
                  value={hookInput}
                  onChange={(e) => setHookInput(e.target.value)}
                  onPressEnter={handleSaveHook}
                  style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}
                />
                <Button size="small" type="primary" onClick={handleSaveHook} loading={savingCopy}>Save</Button>
                <Button size="small" onClick={() => setIsEditingHook(false)}>Cancel</Button>
              </div>
            ) : (
              <Text strong style={{ fontSize: '13px', color: 'var(--ac-ink)', textTransform: 'uppercase', letterSpacing: '0.3px', display: 'block', marginTop: '2px' }}>
                {clipHookText || 'No hook generated'}
              </Text>
            )}
          </div>
        </div>
        {!isEditingHook && (
          <Space size={6}>
            <Button
              size="small"
              icon={copiedTab === 'hook' ? <Check size={12} /> : <Copy size={12} />}
              onClick={() => handleCopy(clipHookText, 'hook')}
              style={{ borderRadius: '6px', fontSize: '11px', height: '24px', padding: '0 8px' }}
            >
              {copiedTab === 'hook' ? 'Copied' : 'Copy'}
            </Button>
            <Button
              size="small"
              icon={<Edit2 size={12} />}
              onClick={() => { setHookInput(clipHookText); setIsEditingHook(true); }}
              style={{ borderRadius: '6px', fontSize: '11px', height: '24px', padding: '0 8px' }}
            >
              Edit
            </Button>
          </Space>
        )}
      </div>

      {/* Platform Deliverables Switcher */}
      <div style={{ maxWidth: '320px', margin: '0 auto 8px auto', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <Text strong style={{ fontSize: '11px', color: 'var(--ac-sub)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Platform Deliverable
          </Text>
          {clip.cta_style && clip.cta_style !== 'none' && (
            <span style={{ fontSize: '10.5px', color: '#22c55e', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              ✓ Platform CTA
            </span>
          )}
        </div>
        <Segmented
          value={activePlatform}
          onChange={(val) => {
            const p = String(val)
            setActivePlatform(p)
          }}
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

      {/* 9:16 Video Player Container */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '320px',
          margin: '0 auto',
          borderRadius: '12px',
          overflow: 'hidden',
          background: '#000',
          aspectRatio: '9/16'
        }}
      >
        <video
          key={videoUrl}
          controls
          playsInline
          preload="metadata"
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        >
          <source src={videoUrl} type="video/mp4" />
          Your browser does not support HTML5 video.
        </video>
      </div>

      {/* Badges and Actions Row */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {clip.output_format && clip.output_format !== 'original' && (
          <span
            style={{
              fontSize: '10.5px',
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'rgba(45,107,255,0.12)',
              color: '#2D6BFF',
              border: '1px solid rgba(45,107,255,0.25)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            📱 {clip.output_format === 'blur_pad' ? '9:16 Blur Pad' : '9:16 Crop Center'}
          </span>
        )}

        {/* Caption mode badge */}
        {clip.subtitle_mode && clip.subtitle_mode !== 'native_preferred' && (
          <span
            style={{
              fontSize: '10.5px',
              padding: '2px 8px',
              borderRadius: '999px',
              background: clip.subtitle_mode === 'styled_burned' ? 'rgba(255,184,0,0.12)' : 'rgba(91,179,106,0.12)',
              color: clip.subtitle_mode === 'styled_burned' ? '#FFB800' : '#5BB36A',
              border: `1px solid ${clip.subtitle_mode === 'styled_burned' ? 'rgba(255,184,0,0.25)' : 'rgba(91,179,106,0.25)'}`,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {clip.subtitle_mode === 'styled_burned'  && '💬 Styled Captions Burned'}
            {clip.subtitle_mode === 'clean_srt_only' && '📄 SRT File Available'}
            {clip.subtitle_mode === 'none'           && '🔇 No Captions'}
          </span>
        )}

        {/* SRT Download button */}
        {clip.srt_file && (
          <Button
            size="small"
            icon={<Download size={12} />}
            onClick={() => window.open(campaignApi.getClipSrtUrl(campaignId, clip.id), '_blank')}
            style={{ borderRadius: '999px', fontSize: '11px', height: '22px', padding: '0 8px' }}
          >
            Download SRT
          </Button>
        )}
      </div>

      {/* Caption Suggestions */}
      {clip.caption_suggestions && clip.caption_suggestions.length > 0 && (
        <div>
          <Text strong style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '6px' }}>
            CAPTION OPTIONS
          </Text>
          <Radio.Group
            value={chosenCaption}
            onChange={(e) => setChosenCaption(e.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: '6px', width: '100%' }}
          >
            {clip.caption_suggestions.map((s, idx) => (
              <Radio key={idx} value={s.text} style={{ alignItems: 'flex-start' }}>
                <Text style={{ fontSize: '12.5px', color: 'var(--ac-ink)' }}>
                  {s.text}
                </Text>
              </Radio>
            ))}
          </Radio.Group>
        </div>
      )}

      <Divider style={{ margin: '6px 0', borderColor: 'var(--ac-line)' }} />

      {/* Platform Post Guide */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text strong style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
              POSTING COPY & TAGS
            </Text>
            <Tag color="cyan" style={{ fontSize: '10.5px', borderRadius: '4px', margin: 0 }}>
              🔍 Optimized for Search
            </Tag>
          </div>
          <Button
            size="small"
            icon={<RefreshCw size={12} />}
            onClick={handleRegenerate}
            loading={regenerating}
            style={{ borderRadius: '6px', fontSize: '11px', height: '24px', padding: '0 8px' }}
          >
            Regenerate Copy & Hook
          </Button>
        </div>
        <Tabs activeKey={activePlatform} onChange={(k) => setActivePlatform(k)} items={tabItems} size="small" />
      </div>

      <Divider style={{ margin: '6px 0', borderColor: 'var(--ac-line)' }} />

      {/* Compliance Checklist */}
      <div>
        <Text strong style={{ fontSize: '12px', color: 'var(--ac-sub)', display: 'block', marginBottom: '8px' }}>
          COMPLIANCE VERIFICATION
        </Text>
        <ComplianceChecklist items={clip.compliance_checklist || []} publishLog={publishLog} />
      </div>

      {/* Download Button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {clip.cta_platforms && Object.keys(clip.cta_platforms).length > 0 && (
            <Tag color="purple" style={{ borderRadius: '999px', fontSize: '11px', margin: 0 }}>
              4 Platforms Ready
            </Tag>
          )}
        </div>
        <Button
          icon={<Download size={14} />}
          href={videoUrl}
          download={`campaign_${clip.moment_name || clip.id}_${activePlatform}.mp4`}
          target="_blank"
          type="primary"
          style={{
            borderRadius: '999px',
            background: 'var(--ac-cta-bg, #1A1A19)',
            color: 'var(--ac-cta-fg, #FFFFFF)',
            border: 'none',
            fontSize: '13px'
          }}
        >
          Download for {activePlatform === 'youtube_shorts' ? 'YouTube Shorts' : activePlatform.charAt(0).toUpperCase() + activePlatform.slice(1)}
        </Button>
      </div>
    </div>
  )
}

export default CampaignClipCard
