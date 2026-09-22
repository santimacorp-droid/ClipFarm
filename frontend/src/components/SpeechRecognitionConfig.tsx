import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert, Button, Card, Progress, Tag, Space, Typography, message, List, Popconfirm, Spin, Tooltip,
} from 'antd'
import {
  DownloadOutlined, DeleteOutlined, CheckCircleFilled, ReloadOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { speechApi, WhisperRuntimeStatus, WhisperModel } from '../services/api'

const { Text, Paragraph } = Typography

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

const accuracyColor: Record<string, string> = {
  Highest: 'green', High: 'green', Good: 'blue', Medium: 'gold', Low: 'default',
}

const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  const [runtime, setRuntime] = useState<WhisperRuntimeStatus | null>(null)
  const [models, setModels] = useState<WhisperModel[]>([])
  const [loading, setLoading] = useState(true)
  const timer = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [rt, ms] = await Promise.all([speechApi.getRuntimeStatus(), speechApi.getModels()])
      setRuntime(rt)
      setModels(Array.isArray(ms) ? ms : [])
    } catch (e) {
      // Backend may not be ready yet - silently retry
    } finally {
      setLoading(false)
    }
  }, [])

  // Installation or model download in progress - speed up polling
  const needsFastPoll = (rt: WhisperRuntimeStatus | null, ms: WhisperModel[]) =>
    rt?.status === 'installing' || ms.some((m) => m.status === 'downloading')

  useEffect(() => {
    refresh()
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [refresh])

  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current)
    const interval = needsFastPoll(runtime, models) ? 2000 : 15000
    timer.current = window.setInterval(refresh, interval)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [runtime, models, refresh])

  const handleInstall = async () => {
    try {
      const r = await speechApi.installRuntime()
      message.info(r.message || 'Installation started')
      setRuntime((p) => (p ? { ...p, status: 'installing', progress: 5 } : p))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Installation failed')
    }
  }

  const handleUninstall = async () => {
    try {
      const r = await speechApi.uninstallRuntime()
      message.success(r.message || 'Uninstalled')
      refresh()
    } catch (e: any) {
      message.error('Uninstall failed')
    }
  }

  const handleDownload = async (model: string) => {
    try {
      await speechApi.downloadModel(model)
      message.info(`Started downloading model ${model}`)
      setModels((prev) => prev.map((m) => (m.name === model ? { ...m, status: 'downloading' } : m)))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Download failed')
    }
  }

  const handleDelete = async (model: string) => {
    try {
      await speechApi.deleteModel(model)
      message.success(`Deleted model ${model}`)
      refresh()
    } catch (e) {
      message.error('Delete failed')
    }
  }

  if (loading) return <Spin />

  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const supported = runtime?.platform_supported !== false

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="When is Whisper needed?"
        description="When imported videos already contain subtitles or captions, ClipFarm uses them directly. Local Whisper is only needed when a video has no existing subtitles to automatically transcribe audio."
      />

      {!supported && (
        <Alert type="warning" showIcon message="Platform Not Supported"
          description="mlx-whisper is only supported on Apple Silicon (M-series) Macs." />
      )}

      {/* Runtime */}
      <Card size="small" title={<Space><ThunderboltOutlined />Whisper Runtime</Space>}>
        {installed && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <CheckCircleFilled style={{ color: '#52c41a' }} />
              <Text strong>Installed</Text>
              <Text type="secondary">({(runtime?.packages || []).join(', ')})</Text>
            </Space>
            <Popconfirm title="Uninstall Whisper runtime? Downloaded models will be kept." onConfirm={handleUninstall} okText="Uninstall" cancelText="Cancel">
              <Button danger size="small" icon={<DeleteOutlined />}>Uninstall Runtime</Button>
            </Popconfirm>
          </Space>
        )}

        {installing && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>Installing… {runtime?.message}</Text>
            <Progress percent={runtime?.progress ?? 5} status="active" />
            {runtime?.log_tail && (
              <pre style={{ maxHeight: 120, overflow: 'auto', background: '#1a1a1a', color: '#bbb', padding: 8, fontSize: 11, borderRadius: 4, margin: 0 }}>
                {runtime.log_tail}
              </pre>
            )}
          </Space>
        )}

        {runtime?.status === 'not_installed' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph type="secondary" style={{ marginBottom: 8 }}>
              Not installed. Installation will download the faster-whisper runtime (~200–400MB). Once installed, select and download a model below to transcribe videos offline.
            </Paragraph>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleInstall} disabled={!supported}>
              Install Whisper
            </Button>
          </Space>
        )}

        {runtime?.status === 'error' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert type="error" showIcon message="Installation Error" description={runtime?.message} />
            <Button icon={<ReloadOutlined />} onClick={handleInstall} disabled={!supported}>Retry Installation</Button>
          </Space>
        )}
      </Card>

      {/* Model */}
      <Card size="small" title="Whisper Models">
        {!installed && (
          <Text type="secondary">Please install the Whisper runtime first, then download models here.</Text>
        )}
        {installed && (
          <List
            dataSource={models}
            renderItem={(m) => {
              const downloaded = m.status === 'downloaded'
              const downloading = m.status === 'downloading'
              return (
                <List.Item
                  actions={[
                    downloaded ? (
                      <Popconfirm title={`Delete model ${m.name}?`} onConfirm={() => handleDelete(m.name)} okText="Delete" cancelText="Cancel">
                        <Button size="small" danger icon={<DeleteOutlined />}>Delete</Button>
                      </Popconfirm>
                    ) : downloading ? (
                      <Button size="small" loading disabled>Downloading</Button>
                    ) : (
                      <Button size="small" type="primary" icon={<DownloadOutlined />} onClick={() => handleDownload(m.name)}>
                        Download
                      </Button>
                    ),
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{m.name}</Text>
                        <Text type="secondary">{m.size}</Text>
                        {downloaded && <Tag color="green">Downloaded</Tag>}
                        <Tag color={accuracyColor[m.accuracy] || 'default'}>Accuracy: {m.accuracy}</Tag>
                        <Tooltip title="Speed"><Tag>{m.speed}</Tag></Tooltip>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Text type="secondary">{m.description}</Text>
                        {downloading && <Progress percent={m.downloadProgress ?? undefined} status="active" />}
                        {m.status === 'error' && m.errorMessage && <Text type="danger">{m.errorMessage}</Text>}
                      </Space>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </Card>
    </Space>
  )
}

export default SpeechRecognitionConfig
