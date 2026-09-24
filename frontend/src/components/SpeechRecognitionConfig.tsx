import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Progress,
  Tag,
  Space,
  Typography,
  message,
  List,
  Popconfirm,
  Spin,
  Tooltip,
  Radio,
  Input,
  Select,
  Switch,
  Divider,
  Row,
  Col
} from 'antd'
import {
  DownloadOutlined,
  DeleteOutlined,
  CheckCircleFilled,
  ReloadOutlined,
  ThunderboltOutlined,
  CloudServerOutlined,
  SettingOutlined,
  KeyOutlined,
  GlobalOutlined,
  SaveOutlined,
  CheckOutlined,
  RocketOutlined,
  ApiOutlined
} from '@ant-design/icons'
import {
  speechApi,
  WhisperRuntimeStatus,
  WhisperModel,
  SpeechConfigData
} from '../services/api'

const { Text, Paragraph } = Typography
const { Option } = Select

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

const accuracyColor: Record<string, string> = {
  Highest: 'green',
  High: 'green',
  Good: 'blue',
  Medium: 'gold',
  Low: 'default',
}

const COMMON_LANGUAGES = [
  { value: 'auto', label: '🌐 Auto-Detect Language' },
  { value: 'en', label: '🇺🇸 English (en)' },
  { value: 'es', label: '🇪🇸 Spanish (es)' },
  { value: 'zh', label: '🇨🇳 Chinese (zh)' },
  { value: 'ja', label: '🇯🇵 Japanese (ja)' },
  { value: 'fr', label: '🇫🇷 French (fr)' },
  { value: 'de', label: '🇩🇪 German (de)' },
  { value: 'pt', label: '🇧🇷 Portuguese (pt)' },
  { value: 'it', label: '🇮🇹 Italian (it)' },
  { value: 'ru', label: '🇷🇺 Russian (ru)' },
  { value: 'ko', label: '🇰🇷 Korean (ko)' },
  { value: 'ar', label: '🇸🇦 Arabic (ar)' },
]

export const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  const [runtime, setRuntime] = useState<WhisperRuntimeStatus | null>(null)
  const [models, setModels] = useState<WhisperModel[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const timer = useRef<number | null>(null)

  // Speech settings state
  const [provider, setProvider] = useState<string>('whisper_local')
  const [activeLocalModel, setActiveLocalModel] = useState<string>('base')
  const [selectedLanguage, setSelectedLanguage] = useState<string>('auto')
  const [enableFallback, setEnableFallback] = useState<boolean>(true)

  // API configurations
  const [openaiKey, setOpenaiKey] = useState<string>('')
  const [openaiModel, setOpenaiModel] = useState<string>('whisper-1')

  const [groqKey, setGroqKey] = useState<string>('')
  const [groqModel, setGroqModel] = useState<string>('whisper-large-v3')

  const [customEndpoint, setCustomEndpoint] = useState<string>('')
  const [customKey, setCustomKey] = useState<string>('')
  const [customModel, setCustomModel] = useState<string>('whisper-large-v3')

  const [dashscopeKey, setDashscopeKey] = useState<string>('')

  // Load initial settings and runtime
  const refresh = useCallback(async () => {
    try {
      const [rt, ms, cfg] = await Promise.all([
        speechApi.getRuntimeStatus().catch(() => null),
        speechApi.getModels().catch(() => []),
        speechApi.getConfig().catch(() => null)
      ])
      if (rt) setRuntime(rt)
      if (ms) setModels(Array.isArray(ms) ? ms : [])

      if (cfg) {
        // Detect if custom_api is being used for Groq
        if (cfg.method === 'custom_api' && cfg.custom_api_config?.endpoint?.includes('groq.com')) {
          setProvider('groq')
          setGroqKey(cfg.custom_api_config.api_key || '')
          setGroqModel(cfg.custom_api_config.model_name || 'whisper-large-v3')
        } else {
          setProvider(cfg.method || 'whisper_local')
        }

        if (cfg.whisper_config?.model_name) {
          setActiveLocalModel(cfg.whisper_config.model_name)
        }
        if (cfg.whisper_config?.language) {
          setSelectedLanguage(cfg.whisper_config.language)
        }
        if (cfg.openai_config?.api_key) {
          setOpenaiKey(cfg.openai_config.api_key)
        }
        if (cfg.openai_config?.model_name) {
          setOpenaiModel(cfg.openai_config.model_name)
        }
        if (cfg.custom_api_config?.endpoint && !cfg.custom_api_config.endpoint.includes('groq.com')) {
          setCustomEndpoint(cfg.custom_api_config.endpoint)
          setCustomKey(cfg.custom_api_config.api_key || '')
          setCustomModel(cfg.custom_api_config.model_name || 'whisper-large-v3')
        }
        if (cfg.aliyun_config?.api_key) {
          setDashscopeKey(cfg.aliyun_config.api_key)
        }
        if (typeof cfg.enable_fallback === 'boolean') {
          setEnableFallback(cfg.enable_fallback)
        }
      }
    } catch (e) {
      console.error('Failed to load speech recognition status:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // Fast poll during download/install
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

  const handleCancelDownload = async (model: string) => {
    try {
      await speechApi.cancelDownload(model)
      message.info(`Cancelled download of model ${model}`)
      refresh()
    } catch (e) {
      message.error('Failed to cancel download')
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

  const handleSetActiveModel = async (modelName: string) => {
    setActiveLocalModel(modelName)
    try {
      await speechApi.updateConfig({
        method: 'whisper_local',
        whisper_config: {
          model_name: modelName,
          language: selectedLanguage
        }
      })
      message.success(`Active local Whisper model set to ${modelName}`)
    } catch (e) {
      message.error('Failed to update active model')
    }
  }

  const handleSaveAllSettings = async () => {
    setSaving(true)
    try {
      let backendMethod = provider
      let customApiData = undefined

      if (provider === 'groq') {
        backendMethod = 'custom_api'
        customApiData = {
          endpoint: 'https://api.groq.com/openai/v1',
          api_key: groqKey.trim(),
          model_name: groqModel,
          language: selectedLanguage
        }
      } else if (provider === 'custom_api') {
        customApiData = {
          endpoint: customEndpoint.trim(),
          api_key: customKey.trim(),
          model_name: customModel.trim() || 'whisper-large-v3',
          language: selectedLanguage
        }
      }

      const payload: Partial<SpeechConfigData> = {
        method: backendMethod,
        whisper_config: {
          model_name: activeLocalModel,
          language: selectedLanguage
        },
        openai_config: {
          api_key: openaiKey.trim(),
          model_name: openaiModel,
          language: selectedLanguage
        },
        custom_api_config: customApiData,
        aliyun_config: {
          api_key: dashscopeKey.trim(),
          language: selectedLanguage
        },
        enable_fallback: enableFallback,
        fallback_method: 'whisper_local'
      }

      await speechApi.updateConfig(payload)
      message.success('Speech recognition settings saved successfully!')
    } catch (err: any) {
      console.error('Failed to save speech config:', err)
      message.error(err?.response?.data?.detail || 'Failed to save speech settings')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />

  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const supported = runtime?.platform_supported !== false

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Overview Alert */}
      <Alert
        type="info"
        showIcon
        message="Speech Recognition & Captioning Service"
        description="Choose between offline Local Whisper (faster-whisper) or high-performance Cloud APIs (OpenAI, Groq, DashScope). When imported videos already have subtitles, ClipFarm uses them directly; speech recognition automatically transcribes videos that have no captions."
      />

      {/* Provider Selector Card */}
      <Card
        size="small"
        title={<Space><SettingOutlined />Speech Recognition Method / Engine</Space>}
        extra={
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSaveAllSettings}
            style={{ fontWeight: 600 }}
          >
            Save Settings
          </Button>
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          Select the primary speech-to-text service used to transcribe audio clips:
        </Paragraph>

        <Radio.Group
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          style={{ width: '100%', marginBottom: 16 }}
        >
          <Row gutter={[12, 12]}>
            <Col xs={24} sm={12} md={8}>
              <Card
                hoverable
                size="small"
                onClick={() => setProvider('whisper_local')}
                style={{
                  borderColor: provider === 'whisper_local' ? '#1890ff' : 'var(--ac-line)',
                  background: provider === 'whisper_local' ? 'rgba(24, 144, 255, 0.08)' : undefined,
                  cursor: 'pointer'
                }}
              >
                <Radio value="whisper_local">
                  <Text strong>💻 Local Whisper</Text>
                </Radio>
                <div style={{ paddingLeft: 24, fontSize: 12, color: 'var(--ac-sub)', marginTop: 4 }}>
                  100% offline & private. Runs locally on your machine via faster-whisper.
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8}>
              <Card
                hoverable
                size="small"
                onClick={() => setProvider('openai_api')}
                style={{
                  borderColor: provider === 'openai_api' ? '#1890ff' : 'var(--ac-line)',
                  background: provider === 'openai_api' ? 'rgba(24, 144, 255, 0.08)' : undefined,
                  cursor: 'pointer'
                }}
              >
                <Radio value="openai_api">
                  <Text strong>⚡ OpenAI Whisper API</Text>
                </Radio>
                <div style={{ paddingLeft: 24, fontSize: 12, color: 'var(--ac-sub)', marginTop: 4 }}>
                  Official OpenAI cloud transcription. High accuracy, requires OpenAI key.
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8}>
              <Card
                hoverable
                size="small"
                onClick={() => setProvider('groq')}
                style={{
                  borderColor: provider === 'groq' ? '#1890ff' : 'var(--ac-line)',
                  background: provider === 'groq' ? 'rgba(24, 144, 255, 0.08)' : undefined,
                  cursor: 'pointer'
                }}
              >
                <Radio value="groq">
                  <Text strong>🚀 Groq Cloud Whisper</Text>
                </Radio>
                <div style={{ paddingLeft: 24, fontSize: 12, color: 'var(--ac-sub)', marginTop: 4 }}>
                  Ultra-fast LPU inference (5-10x faster). Requires Groq API key.
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8}>
              <Card
                hoverable
                size="small"
                onClick={() => setProvider('aliyun_speech')}
                style={{
                  borderColor: provider === 'aliyun_speech' ? '#1890ff' : 'var(--ac-line)',
                  background: provider === 'aliyun_speech' ? 'rgba(24, 144, 255, 0.08)' : undefined,
                  cursor: 'pointer'
                }}
              >
                <Radio value="aliyun_speech">
                  <Text strong>☁️ DashScope / Qwen ASR</Text>
                </Radio>
                <div style={{ paddingLeft: 24, fontSize: 12, color: 'var(--ac-sub)', marginTop: 4 }}>
                  Alibaba DashScope Qwen3 ASR for Chinese and multilingual audio.
                </div>
              </Card>
            </Col>

            <Col xs={24} sm={12} md={8}>
              <Card
                hoverable
                size="small"
                onClick={() => setProvider('custom_api')}
                style={{
                  borderColor: provider === 'custom_api' ? '#1890ff' : 'var(--ac-line)',
                  background: provider === 'custom_api' ? 'rgba(24, 144, 255, 0.08)' : undefined,
                  cursor: 'pointer'
                }}
              >
                <Radio value="custom_api">
                  <Text strong>🔌 Custom API Endpoint</Text>
                </Radio>
                <div style={{ paddingLeft: 24, fontSize: 12, color: 'var(--ac-sub)', marginTop: 4 }}>
                  Self-hosted server or any OpenAI-compatible transcription service.
                </div>
              </Card>
            </Col>
          </Row>
        </Radio.Group>

        <Divider style={{ margin: '12px 0' }} />

        {/* Global Language and Fallback Options */}
        <Row gutter={16} align="middle">
          <Col xs={24} sm={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong><GlobalOutlined /> Default Audio Language:</Text>
              <Select
                value={selectedLanguage}
                onChange={(val) => setSelectedLanguage(val)}
                style={{ width: '100%' }}
                options={COMMON_LANGUAGES}
              />
            </Space>
          </Col>
          <Col xs={24} sm={12}>
            <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
              <Text strong>Automatic Fallback:</Text>
              <Space>
                <Switch
                  checked={enableFallback}
                  onChange={(checked) => setEnableFallback(checked)}
                />
                <Text type="secondary">
                  If Cloud API is unreachable or fails, auto-fallback to Local Whisper
                </Text>
              </Space>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Cloud Provider Specific Configurations */}
      {provider === 'openai_api' && (
        <Card size="small" title={<Space><KeyOutlined />OpenAI Whisper Configuration</Space>}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>OpenAI API Key:</Text>
              <Input.Password
                placeholder="sk-proj-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                style={{ marginTop: 4 }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                Used for calling official OpenAI Audio Transcriptions endpoint.
              </Text>
            </div>

            <Row gutter={16}>
              <Col span={12}>
                <Text strong>Whisper Model:</Text>
                <Select
                  value={openaiModel}
                  onChange={(val) => setOpenaiModel(val)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="whisper-1">whisper-1 (Recommended)</Option>
                </Select>
              </Col>
            </Row>
          </Space>
        </Card>
      )}

      {provider === 'groq' && (
        <Card size="small" title={<Space><RocketOutlined />Groq Whisper Cloud Configuration</Space>}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              type="success"
              showIcon
              message="Groq LPUs deliver near-instant Whisper transcription"
              description="Transcribe full episodes in just seconds with Groq's high-speed inference."
            />
            <div>
              <Text strong>Groq API Key:</Text>
              <Input.Password
                placeholder="gsk_..."
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                style={{ marginTop: 4 }}
              />
            </div>

            <Row gutter={16}>
              <Col span={12}>
                <Text strong>Groq Model:</Text>
                <Select
                  value={groqModel}
                  onChange={(val) => setGroqModel(val)}
                  style={{ width: '100%', marginTop: 4 }}
                >
                  <Option value="whisper-large-v3">whisper-large-v3 (Highest Accuracy)</Option>
                  <Option value="whisper-large-v3-turbo">whisper-large-v3-turbo (Ultra-Fast)</Option>
                  <Option value="distil-whisper-large-v3-en">distil-whisper-large-v3-en (English Only)</Option>
                </Select>
              </Col>
            </Row>
          </Space>
        </Card>
      )}

      {provider === 'aliyun_speech' && (
        <Card size="small" title={<Space><CloudServerOutlined />DashScope / Qwen ASR Configuration</Space>}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>DashScope API Key:</Text>
              <Input.Password
                placeholder="sk-..."
                value={dashscopeKey}
                onChange={(e) => setDashscopeKey(e.target.value)}
                style={{ marginTop: 4 }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                Used for calling Alibaba Cloud DashScope Qwen3 ASR speech-to-text service.
              </Text>
            </div>
          </Space>
        </Card>
      )}

      {provider === 'custom_api' && (
        <Card size="small" title={<Space><ApiOutlined />Custom OpenAI-Compatible API Configuration</Space>}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>API Base URL:</Text>
              <Input
                placeholder="https://api.yourdomain.com/v1"
                value={customEndpoint}
                onChange={(e) => setCustomEndpoint(e.target.value)}
                style={{ marginTop: 4 }}
              />
            </div>

            <Row gutter={16}>
              <Col span={12}>
                <Text strong>API Key:</Text>
                <Input.Password
                  placeholder="Bearer token or API key"
                  value={customKey}
                  onChange={(e) => setCustomKey(e.target.value)}
                  style={{ marginTop: 4 }}
                />
              </Col>
              <Col span={12}>
                <Text strong>Model Name:</Text>
                <Input
                  placeholder="e.g. whisper-large-v3"
                  value={customModel}
                  onChange={(e) => setCustomModel(e.target.value)}
                  style={{ marginTop: 4 }}
                />
              </Col>
            </Row>
          </Space>
        </Card>
      )}

      {/* Local Whisper Runtime Card */}
      <Card size="small" title={<Space><ThunderboltOutlined />Local Whisper Runtime</Space>}>
        {installed && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <CheckCircleFilled style={{ color: '#52c41a' }} />
              <Text strong>Installed</Text>
              <Text type="secondary">({(runtime?.packages || []).join(', ')})</Text>
            </Space>
            <Popconfirm
              title="Uninstall Whisper runtime? Downloaded models will be kept."
              onConfirm={handleUninstall}
              okText="Uninstall"
              cancelText="Cancel"
            >
              <Button danger size="small" icon={<DeleteOutlined />}>
                Uninstall Runtime
              </Button>
            </Popconfirm>
          </Space>
        )}

        {installing && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>Installing… {runtime?.message}</Text>
            <Progress percent={runtime?.progress ?? 5} status="active" />
            {runtime?.log_tail && (
              <pre
                style={{
                  maxHeight: 120,
                  overflow: 'auto',
                  background: '#1a1a1a',
                  color: '#bbb',
                  padding: 8,
                  fontSize: 11,
                  borderRadius: 4,
                  margin: 0
                }}
              >
                {runtime.log_tail}
              </pre>
            )}
          </Space>
        )}

        {runtime?.status === 'not_installed' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph type="secondary" style={{ marginBottom: 8 }}>
              Not installed. Installation will configure the local faster-whisper engine (~200–400MB). Once installed, select and download a model below to transcribe videos offline.
            </Paragraph>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleInstall}
              disabled={!supported}
            >
              Install Whisper Runtime
            </Button>
          </Space>
        )}

        {runtime?.status === 'error' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert type="error" showIcon message="Installation Error" description={runtime?.message} />
            <Button icon={<ReloadOutlined />} onClick={handleInstall} disabled={!supported}>
              Retry Installation
            </Button>
          </Space>
        )}
      </Card>

      {/* Local Whisper Models Card */}
      <Card
        size="small"
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Local Whisper Models</span>
            {installed && (
              <Tag color="cyan">
                Active Default Model: <strong>{activeLocalModel}</strong>
              </Tag>
            )}
          </div>
        }
      >
        {!installed && (
          <Text type="secondary">
            Please install the Whisper runtime first, then download models here.
          </Text>
        )}

        {installed && (
          <List
            dataSource={models}
            renderItem={(m) => {
              const downloaded = m.status === 'downloaded'
              const downloading = m.status === 'downloading'
              const isActive = activeLocalModel === m.name

              return (
                <List.Item
                  actions={[
                    downloaded ? (
                      <Space key="downloaded-actions">
                        {isActive ? (
                          <Tag color="success" icon={<CheckOutlined />}>
                            Active
                          </Tag>
                        ) : (
                          <Button
                            size="small"
                            type="dashed"
                            onClick={() => handleSetActiveModel(m.name)}
                          >
                            Set Active
                          </Button>
                        )}
                        <Popconfirm
                          title={`Delete model ${m.name}?`}
                          onConfirm={() => handleDelete(m.name)}
                          okText="Delete"
                          cancelText="Cancel"
                        >
                          <Button size="small" danger icon={<DeleteOutlined />}>
                            Delete
                          </Button>
                        </Popconfirm>
                      </Space>
                    ) : downloading ? (
                      <Space key="downloading-actions">
                        <Button size="small" loading disabled>
                          Downloading
                        </Button>
                        <Button
                          size="small"
                          danger
                          onClick={() => handleCancelDownload(m.name)}
                        >
                          Cancel
                        </Button>
                      </Space>
                    ) : (
                      <Button
                        key="download-btn"
                        size="small"
                        type="primary"
                        icon={<DownloadOutlined />}
                        onClick={() => handleDownload(m.name)}
                      >
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
                        {isActive && <Tag color="blue">Active Choice</Tag>}
                        <Tag color={accuracyColor[m.accuracy] || 'default'}>
                          Accuracy: {m.accuracy}
                        </Tag>
                        <Tooltip title="Inference Speed">
                          <Tag>{m.speed}</Tag>
                        </Tooltip>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Text type="secondary">{m.description}</Text>
                        {downloading && (
                          <Progress
                            percent={m.downloadProgress ?? undefined}
                            status="active"
                          />
                        )}
                        {m.status === 'error' && m.errorMessage && (
                          <Text type="danger">{m.errorMessage}</Text>
                        )}
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
