import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Card, 
  Form, 
  Input, 
  Button, 
  Typography, 
  Space, 
  Alert, 
  Divider, 
  Row, 
  Col, 
  Tabs, 
  message, 
  Select, 
  Tag, 
  Switch,
  Statistic,
  Table,
  Popconfirm
} from 'antd'
import { 
  KeyOutlined, 
  SaveOutlined, 
  ApiOutlined, 
  SettingOutlined, 
  InfoCircleOutlined, 
  RobotOutlined, 
  SoundOutlined, 
  PoweroffOutlined,
  DollarOutlined,
  ReloadOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  PictureOutlined,
  CoffeeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons'
import { settingsApi } from '../services/api'
import SpeechRecognitionConfig from '../components/SpeechRecognitionConfig'
import WatermarkManager from '../components/WatermarkManager'
import { isDesktopMode } from '../utils/desktopMode'
import { trackApiKeyConfigured } from '../appEvents/events'
import { isAnalyticsEnabled, setAnalyticsEnabled } from '../appEvents/client'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [currentProvider, setCurrentProvider] = useState<any>({})
  const [selectedProvider, setSelectedProvider] = useState('dashscope')
  const [activeModelName, setActiveModelName] = useState<string>('qwen-plus-character')
  const [tokenStats, setTokenStats] = useState<any>(null)
  const [loadingTokenStats, setLoadingTokenStats] = useState(false)
  const [analyticsOn, setAnalyticsOn] = useState(isAnalyticsEnabled())
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [customSearchModel, setCustomSearchModel] = useState('')
  const [localAIStatus, setLocalAIStatus] = useState<{
    ollama?: { available: boolean; base_url: string; models: string[]; message: string }
    lmstudio?: { available: boolean; base_url: string; models: string[]; message: string }
  }>({})
  const [checkingLocalAI, setCheckingLocalAI] = useState(false)

  // Provider configuration
  const providerConfig = {
    ollama: {
      name: 'Ollama (Local)',
      icon: <ThunderboltOutlined />,
      color: '#13c2c2',
      description: '100% Free & Local',
      apiKeyField: 'ollama_api_key',
      placeholder: 'Optional for local models (leave blank)',
      hasBaseUrl: true,
      defaultBaseUrl: 'http://localhost:11434/v1',
      baseUrlPlaceholder: 'http://localhost:11434/v1',
      defaultModel: 'llama3.2'
    },
    lmstudio: {
      name: 'LM Studio (Local)',
      icon: <ThunderboltOutlined />,
      color: '#52c41a',
      description: 'Local GGUF Models',
      apiKeyField: 'lmstudio_api_key',
      placeholder: 'Optional (leave blank or enter dummy key)',
      hasBaseUrl: true,
      defaultBaseUrl: 'http://localhost:1234/v1',
      baseUrlPlaceholder: 'http://localhost:1234/v1',
      defaultModel: 'local-model'
    },
    deepseek: {
      name: 'DeepSeek Direct',
      icon: <RobotOutlined />,
      color: '#2f54eb',
      description: 'DeepSeek V3 & R1 Direct',
      apiKeyField: 'deepseek_api_key',
      placeholder: 'Enter DeepSeek API key (sk-...)',
      hasBaseUrl: true,
      defaultBaseUrl: 'https://api.deepseek.com/v1',
      baseUrlPlaceholder: 'https://api.deepseek.com/v1',
      defaultModel: 'deepseek-chat'
    },
    openrouter: {
      name: 'OpenRouter',
      icon: <ApiOutlined />,
      color: '#722ed1',
      description: 'Claude, Llama, DeepSeek Gateway',
      apiKeyField: 'openrouter_api_key',
      placeholder: 'Enter OpenRouter API key (sk-or-...)',
      hasBaseUrl: true,
      defaultBaseUrl: 'https://openrouter.ai/api/v1',
      baseUrlPlaceholder: 'https://openrouter.ai/api/v1',
      defaultModel: 'anthropic/claude-3.5-sonnet'
    },
    groq: {
      name: 'Groq (Ultra-Fast)',
      icon: <ThunderboltOutlined />,
      color: '#f5222d',
      description: 'Instant Llama 3.3 / Qwen 2.5',
      apiKeyField: 'groq_api_key',
      placeholder: 'Enter Groq API key (gsk_...)',
      hasBaseUrl: true,
      defaultBaseUrl: 'https://api.groq.com/openai/v1',
      baseUrlPlaceholder: 'https://api.groq.com/openai/v1',
      defaultModel: 'llama-3.3-70b-versatile'
    },
    anthropic: {
      name: 'Anthropic Claude',
      icon: <RobotOutlined />,
      color: '#d46b08',
      description: 'Claude 3.5 Sonnet & Haiku',
      apiKeyField: 'anthropic_api_key',
      placeholder: 'Enter Anthropic API key (sk-ant-...)',
      hasBaseUrl: false,
      defaultBaseUrl: 'https://api.anthropic.com/v1',
      baseUrlPlaceholder: '',
      defaultModel: 'claude-3-5-sonnet-20241022'
    },
    openai: {
      name: 'OpenAI',
      icon: <RobotOutlined />,
      color: '#1890ff',
      description: 'GPT-4o & GPT-4o-mini',
      apiKeyField: 'openai_api_key',
      placeholder: 'Enter OpenAI API key (sk-...)',
      hasBaseUrl: true,
      defaultBaseUrl: 'https://api.openai.com/v1',
      baseUrlPlaceholder: 'https://api.openai.com/v1 (optional proxy)',
      defaultModel: 'gpt-4o-mini'
    },
    gemini: {
      name: 'Google Gemini',
      icon: <RobotOutlined />,
      color: '#faad14',
      description: 'Gemini 2.0 Flash & 1.5 Pro',
      apiKeyField: 'gemini_api_key',
      placeholder: 'Enter Gemini API key',
      hasBaseUrl: false,
      defaultBaseUrl: '',
      baseUrlPlaceholder: '',
      defaultModel: 'gemini-2.5-flash'
    },
    dashscope: {
      name: 'Alibaba Qwen (DashScope)',
      icon: <RobotOutlined />,
      color: '#108ee9',
      description: 'Alibaba Cloud Qwen Models',
      apiKeyField: 'dashscope_api_key',
      placeholder: 'Enter DashScope API key (sk-...)',
      hasBaseUrl: false,
      defaultBaseUrl: '',
      baseUrlPlaceholder: '',
      defaultModel: 'qwen-plus-character'
    },
    siliconflow: {
      name: 'SiliconFlow',
      icon: <RobotOutlined />,
      color: '#9254de',
      description: 'SiliconFlow Model Service',
      apiKeyField: 'siliconflow_api_key',
      placeholder: 'Enter SiliconFlow API key (sk-...)',
      hasBaseUrl: false,
      defaultBaseUrl: '',
      baseUrlPlaceholder: '',
      defaultModel: 'Qwen/Qwen2.5-7B-Instruct'
    },
    custom: {
      name: 'Custom (OpenAI-Compatible)',
      icon: <ApiOutlined />,
      color: '#eb2f96',
      description: 'Any OpenAI-compatible Endpoint',
      apiKeyField: 'custom_api_key',
      placeholder: 'Enter API key for custom endpoint',
      hasBaseUrl: true,
      defaultBaseUrl: 'http://localhost:8000/v1',
      baseUrlPlaceholder: 'e.g. http://localhost:8000/v1 or https://api.together.xyz/v1',
      defaultModel: 'custom-model'
    }
  }

  // Auto-probe local AI engines (Ollama & LM Studio)
  const checkLocalAI = async (autoSelect = false, targetProvider?: string) => {
    try {
      setCheckingLocalAI(true)
      const res = await settingsApi.getLocalAIStatus()
      if (res && res.success && res.data) {
        setLocalAIStatus(res.data)
        const prov = targetProvider || selectedProvider
        if (prov === 'ollama' && res.data.ollama?.available && res.data.ollama.models?.length > 0) {
          setDiscoveredModels(res.data.ollama.models)
          const curModel = form.getFieldValue('model_name')
          if (autoSelect || !curModel || curModel === 'llama3.2' || curModel.startsWith('qwen')) {
            form.setFieldsValue({ model_name: res.data.ollama.models[0] })
            setActiveModelName(res.data.ollama.models[0])
          }
        } else if (prov === 'lmstudio' && res.data.lmstudio?.available && res.data.lmstudio.models?.length > 0) {
          setDiscoveredModels(res.data.lmstudio.models)
          const curModel = form.getFieldValue('model_name')
          if (autoSelect || !curModel || curModel === 'local-model' || curModel.startsWith('qwen')) {
            form.setFieldsValue({ model_name: res.data.lmstudio.models[0] })
            setActiveModelName(res.data.lmstudio.models[0])
          }
        }
      }
    } catch (err) {
      console.warn('Failed to query local AI status:', err)
    } finally {
      setCheckingLocalAI(false)
    }
  }

  // Load data
  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [settings, , provider, tokenStatsRes] = await Promise.allSettled([
        settingsApi.getSettings(),
        settingsApi.getAvailableModels(),
        settingsApi.getCurrentProvider(),
        settingsApi.getTokenStats()
      ])
      
      const settingsData = settings.status === 'fulfilled' ? settings.value : {}
      const providerData = provider.status === 'fulfilled'
        ? provider.value
        : { available: true, provider: 'dashscope', display_name: 'Alibaba Qwen', model: 'qwen-plus-character' }
      
      if (tokenStatsRes.status === 'fulfilled') {
        setTokenStats(tokenStatsRes.value)
      }

      const providerName = providerData.provider || 'dashscope'
      setCurrentProvider(providerData)
      
      const modelName = settingsData.api?.api_model || providerData.model || 'qwen-plus-character'
      setActiveModelName(modelName)

      // Convert nested settings structure to flat structure
      const flatSettings = {
        llm_provider: providerName,
        dashscope_api_key: settingsData.api?.api_keys?.dashscope || '',
        openai_api_key: settingsData.api?.api_keys?.openai || '',
        gemini_api_key: settingsData.api?.api_keys?.gemini || '',
        anthropic_api_key: settingsData.api?.api_keys?.anthropic || '',
        deepseek_api_key: settingsData.api?.api_keys?.deepseek || '',
        openrouter_api_key: settingsData.api?.api_keys?.openrouter || '',
        groq_api_key: settingsData.api?.api_keys?.groq || '',
        siliconflow_api_key: settingsData.api?.api_keys?.siliconflow || '',
        custom_api_key: settingsData.api?.api_keys?.custom || '',
        ollama_api_key: settingsData.api?.api_keys?.ollama || '',
        lmstudio_api_key: settingsData.api?.api_keys?.lmstudio || '',
        custom_base_url: settingsData.api?.custom_base_url || '',
        jimeng_access_key: settingsData.api?.api_keys?.jimeng_access || '',
        jimeng_secret_key: settingsData.api?.api_keys?.jimeng_secret || '',
        model_name: modelName,
        chunk_size: settingsData.processing?.processing_chunk_size || 5000,
        min_score_threshold: settingsData.processing?.processing_min_score || 0.7,
        max_clips_per_collection: settingsData.processing?.processing_max_clips || 5
      }
      
      setSelectedProvider(providerName)
      form.setFieldsValue(flatSettings)
      checkLocalAI(false, providerName)
    } catch (error) {
      console.error('Failed to load settings data:', error)
    }
  }

  const handleRefreshTokenStats = async () => {
    setLoadingTokenStats(true)
    try {
      const stats = await settingsApi.getTokenStats()
      setTokenStats(stats)
      message.success('Token statistics refreshed')
    } catch (e) {
      message.error('Failed to refresh token stats')
    } finally {
      setLoadingTokenStats(false)
    }
  }

  const handleResetTokenStats = async () => {
    try {
      await settingsApi.resetTokenStats()
      message.success('Token usage counters reset successfully')
      handleRefreshTokenStats()
    } catch (e) {
      message.error('Failed to reset token stats')
    }
  }

  // Save configuration
  const handleSave = async (values: any) => {
    try {
      setLoading(true)
      
      // First get existing configuration to avoid clearing any existing onesAPI key
      let existingSettings = null
      try {
        existingSettings = await settingsApi.getSettings()
      } catch (error) {
        console.warn('Failed to get existing configuration, default configuration will be used:', error)
      }
      
      // Get existingAPI keys, Only update fields with values
      const existingApiKeys = existingSettings?.api?.api_keys || {}
      
      // Convert flat data to nested structure expected by backend
      const backendSettings = {
        basic: {
          app_name: "ClipFarm Desktop",
          app_version: "1.0.0",
          debug_mode: false,
          auto_start: true
        },
        service: {
          host: "127.0.0.1",
          port: 8000,
          max_memory_usage: 2048
        },
          api: {
            api_keys: {
              dashscope: values.dashscope_api_key || existingApiKeys.dashscope || "",
              openai: values.openai_api_key || existingApiKeys.openai || "",
              gemini: values.gemini_api_key || existingApiKeys.gemini || "",
              anthropic: values.anthropic_api_key || existingApiKeys.anthropic || "",
              deepseek: values.deepseek_api_key || existingApiKeys.deepseek || "",
              openrouter: values.openrouter_api_key || existingApiKeys.openrouter || "",
              groq: values.groq_api_key || existingApiKeys.groq || "",
              siliconflow: values.siliconflow_api_key || existingApiKeys.siliconflow || "",
              custom: values.custom_api_key || existingApiKeys.custom || "",
              ollama: values.ollama_api_key || existingApiKeys.ollama || "",
              lmstudio: values.lmstudio_api_key || existingApiKeys.lmstudio || "",
              jimeng_access: values.jimeng_access_key || existingApiKeys.jimeng_access || "",
              jimeng_secret: values.jimeng_secret_key || existingApiKeys.jimeng_secret || ""
            },
            api_model: values.model_name || "qwen-plus",
            custom_base_url: values.custom_base_url || "",
            llm_provider: selectedProvider,
            api_max_tokens: 4096,
            api_timeout: 30
          },
          processing: {
            processing_chunk_size: values.chunk_size || 5000,
            processing_min_score: values.min_score_threshold || 0.7,
            processing_max_clips: values.max_clips_per_collection || 5,
            processing_max_retries: 3
          },
          logs: {
            log_level: "INFO",
            log_retention_days: 7
          },
          paths: existingSettings?.paths || {
            data_directory: "",
            cache_directory: "",
            temp_directory: ""
          }
        }
        
        await settingsApi.updateSettings(backendSettings)
        message.success('Settings saved successfully!')

        // Tracked point: records which one was configured provider 's key(Not passed key Plaintext)
        const apiKeyField = providerConfig[selectedProvider as keyof typeof providerConfig]?.apiKeyField
        if (apiKeyField) {
          trackApiKeyConfigured({
            provider: selectedProvider,
            hasKey: !!values[apiKeyField],
          })
        }

        await loadData() // Reload data
      } catch (error: any) {
        message.error('Save failed: ' + (error.message || 'Unknown error'))
      } finally {
        setLoading(false)
      }
    }

    // Test API Connectivity
    const handleTestApiKey = async () => {
      const config = providerConfig[selectedProvider as keyof typeof providerConfig]
      const apiKey = form.getFieldValue(config.apiKeyField) || ''
      const baseUrl = form.getFieldValue('custom_base_url') || ''
      
      if (selectedProvider !== 'ollama' && (!apiKey || apiKey.trim() === '')) {
        message.error('Please enter an API key first')
        return
      }

      try {
        setLoading(true)
        const modelName = form.getFieldValue('model_name')
        const result = await settingsApi.testApiKey(selectedProvider, apiKey, modelName, baseUrl)
        if (result.success) {
          message.success(result.message || 'API connection test succeeded!')
        } else {
          message.error('API connection test failed: ' + (result.error || 'Unknown error'))
        }
      } catch (error: any) {
        message.error('Test failed: ' + (error.message || 'Unknown error'))
      } finally {
        setLoading(false)
      }
    }

    // Dynamically fetch models from local Ollama or custom endpoint
    const handleFetchRemoteModels = async () => {
      const config = providerConfig[selectedProvider as keyof typeof providerConfig]
      const apiKey = form.getFieldValue(config.apiKeyField) || ''
      const baseUrl = form.getFieldValue('custom_base_url') || config.defaultBaseUrl || ''

      try {
        setFetchingModels(true)
        const res = await settingsApi.fetchRemoteModels(selectedProvider, apiKey, baseUrl)
        if (res.success && res.models && res.models.length > 0) {
          setDiscoveredModels(res.models)
          message.success(`Found ${res.models.length} model(s) from ${selectedProvider}!`)
          if (!form.getFieldValue('model_name') || form.getFieldValue('model_name') === 'qwen-plus') {
            form.setFieldsValue({ model_name: res.models[0] })
            setActiveModelName(res.models[0])
          }
        } else {
          message.warning('No models found: ' + (res.error || 'Verify server is running at ' + baseUrl))
        }
      } catch (e: any) {
        message.error('Failed to fetch models: ' + (e.message || 'Unknown error'))
      } finally {
        setFetchingModels(false)
      }
    }

    // Provider switch
    const handleProviderChange = (provider: string) => {
      setSelectedProvider(provider)
      const conf = providerConfig[provider as keyof typeof providerConfig]
      const currentBaseUrl = (form.getFieldValue('custom_base_url') || '').trim()
      
      const patch: any = { llm_provider: provider }
      const knownDefaults = [
        'http://localhost:11434/v1',
        'http://localhost:11434',
        'http://localhost:1234/v1',
        'http://localhost:1234',
        'https://api.deepseek.com/v1',
        'https://openrouter.ai/api/v1',
        'https://api.groq.com/openai/v1',
        'https://api.openai.com/v1'
      ]

      if (conf?.hasBaseUrl) {
        if (!currentBaseUrl || knownDefaults.includes(currentBaseUrl)) {
          patch.custom_base_url = conf.defaultBaseUrl
        }
      }

      const curModel = form.getFieldValue('model_name')
      const knownDefaultModels = [
        'qwen-plus-character',
        'qwen-plus',
        'qwen-turbo',
        'qwen-max',
        'llama3.2',
        'local-model',
        'custom-model',
        'deepseek-chat',
        'anthropic/claude-3.5-sonnet',
        'llama-3.3-70b-versatile',
        'gpt-4o'
      ]

      if (conf?.defaultModel && (!curModel || knownDefaultModels.includes(curModel) || curModel.startsWith('qwen'))) {
        patch.model_name = conf.defaultModel
        setActiveModelName(conf.defaultModel)
      }
      form.setFieldsValue(patch)

      // Auto-detect available models if switching to Ollama or LM Studio
      if (provider === 'ollama' || provider === 'lmstudio') {
        checkLocalAI(true, provider)
      }
    }

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> Settings
        </Title>
        
        <Tabs defaultActiveKey="api" className="settings-tabs">
          <TabPane 
            tab={
              <span>
                <RobotOutlined />
                AI Models
              </span>
            } 
            key="api"
          >
            <Card title="AI Model Configuration" className="settings-card">
              <Alert
                message="ClipFarm Multi-Model Engine"
                description="ClipFarm supports local offline models (Ollama, LM Studio) and top cloud AI providers (OpenAI, Anthropic Claude, DeepSeek, Groq, OpenRouter, Gemini). Select your preferred provider below."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <Form
                form={form}
                layout="vertical"
                className="settings-form"
                onFinish={handleSave}
                onValuesChange={(changedValues) => {
                  if (changedValues.model_name) {
                    setActiveModelName(Array.isArray(changedValues.model_name) ? changedValues.model_name[0] : changedValues.model_name)
                  }
                }}
                initialValues={{
                  llm_provider: 'dashscope',
                  model_name: 'qwen-plus-character',
                  chunk_size: 5000,
                  min_score_threshold: 0.7,
                  max_clips_per_collection: 5
                }}
              >
                {/* Active Provider & Model Status */}
                {currentProvider.available && (
                  <Alert
                    message={`Active: ${currentProvider.display_name || 'Alibaba Qwen'} — Model: ${currentProvider.model || activeModelName}`}
                    type="success"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}

                {/* Local AI Engines Quick Status Toolbar */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 8,
                  padding: '10px 16px',
                  marginBottom: 20,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 12
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <Text strong style={{ fontSize: 13, color: '#e6f7ff' }}>
                      <ThunderboltOutlined style={{ marginRight: 6, color: '#13c2c2' }} />
                      Local AI Runtimes:
                    </Text>

                    <Space size={6}>
                      <Tag
                        color={localAIStatus.ollama?.available ? 'success' : 'default'}
                        style={{ cursor: 'pointer', padding: '2px 8px', borderRadius: 4 }}
                        onClick={() => handleProviderChange('ollama')}
                      >
                        Ollama: {localAIStatus.ollama?.available ? `🟢 Online (${localAIStatus.ollama.models?.length || 0})` : '⚪ Offline'}
                      </Tag>
                      {localAIStatus.ollama?.available && selectedProvider !== 'ollama' && (
                        <Button size="small" type="link" style={{ padding: 0 }} onClick={() => handleProviderChange('ollama')}>
                          Select Ollama
                        </Button>
                      )}
                    </Space>

                    <Space size={6}>
                      <Tag
                        color={localAIStatus.lmstudio?.available ? 'success' : 'default'}
                        style={{ cursor: 'pointer', padding: '2px 8px', borderRadius: 4 }}
                        onClick={() => handleProviderChange('lmstudio')}
                      >
                        LM Studio: {localAIStatus.lmstudio?.available ? `🟢 Online (${localAIStatus.lmstudio.models?.length || 0})` : '⚪ Offline'}
                      </Tag>
                      {localAIStatus.lmstudio?.available && selectedProvider !== 'lmstudio' && (
                        <Button size="small" type="link" style={{ padding: 0 }} onClick={() => handleProviderChange('lmstudio')}>
                          Select LM Studio
                        </Button>
                      )}
                    </Space>
                  </div>

                  <Button
                    size="small"
                    icon={<ReloadOutlined spin={checkingLocalAI} />}
                    onClick={() => checkLocalAI(false)}
                    loading={checkingLocalAI}
                  >
                    Probe Local AI
                  </Button>
                </div>

                {/* Local Ollama Live Detection Alert */}
                {selectedProvider === 'ollama' && (
                  <div style={{ marginBottom: 16 }}>
                    {localAIStatus.ollama?.available ? (
                      <Alert
                        type="success"
                        showIcon
                        icon={<CheckCircleOutlined />}
                        message="Ollama Local Engine Online"
                        description={
                          <div>
                            <div>Found <strong>{localAIStatus.ollama.models?.length || 0}</strong> model(s) installed on this machine. Processing runs 100% private with $0 API costs.</div>
                            {localAIStatus.ollama.models && localAIStatus.ollama.models.length > 0 && (
                              <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                                <Text type="secondary" style={{ fontSize: 12 }}>Detected models:</Text>
                                {localAIStatus.ollama.models.map(m => (
                                  <Tag
                                    key={m}
                                    color={activeModelName === m ? 'processing' : undefined}
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => {
                                      form.setFieldsValue({ model_name: m })
                                      setActiveModelName(m)
                                    }}
                                  >
                                    {m}
                                  </Tag>
                                ))}
                              </div>
                            )}
                          </div>
                        }
                      />
                    ) : (
                      <Alert
                        type="warning"
                        showIcon
                        icon={<CloseCircleOutlined />}
                        message="Ollama Service Not Detected at http://localhost:11434"
                        description={
                          <div>
                            <div>Ollama is not running. To process videos 100% locally with $0 API costs:</div>
                            <div style={{
                              marginTop: 8,
                              marginBottom: 8,
                              fontFamily: 'monospace',
                              background: 'rgba(0, 0, 0, 0.35)',
                              border: '1px solid rgba(255, 255, 255, 0.08)',
                              padding: '8px 12px',
                              borderRadius: 6,
                              fontSize: 12,
                              userSelect: 'all'
                            }}>
                              curl -fsSL https://ollama.com/install.sh | sh<br />
                              ollama run llama3.2
                            </div>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                              <Text type="secondary" style={{ fontSize: 12 }}>Once started:</Text>
                              <Button size="small" type="primary" ghost icon={<ReloadOutlined spin={checkingLocalAI} />} onClick={() => checkLocalAI(false)}>
                                Probe Local AI
                              </Button>
                            </div>
                          </div>
                        }
                      />
                    )}
                  </div>
                )}

                {/* Local LM Studio Live Detection Alert */}
                {selectedProvider === 'lmstudio' && (
                  <div style={{ marginBottom: 16 }}>
                    {localAIStatus.lmstudio?.available ? (
                      <Alert
                        type="success"
                        showIcon
                        icon={<CheckCircleOutlined />}
                        message="LM Studio Local Engine Online"
                        description={
                          <div>
                            <div>Found <strong>{localAIStatus.lmstudio.models?.length || 0}</strong> active model(s) loaded. Processing runs 100% private with $0 API costs.</div>
                            {localAIStatus.lmstudio.models && localAIStatus.lmstudio.models.length > 0 && (
                              <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                                <Text type="secondary" style={{ fontSize: 12 }}>Loaded models:</Text>
                                {localAIStatus.lmstudio.models.map(m => (
                                  <Tag
                                    key={m}
                                    color={activeModelName === m ? 'processing' : undefined}
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => {
                                      form.setFieldsValue({ model_name: m })
                                      setActiveModelName(m)
                                    }}
                                  >
                                    {m}
                                  </Tag>
                                ))}
                              </div>
                            )}
                          </div>
                        }
                      />
                    ) : (
                      <Alert
                        type="warning"
                        showIcon
                        icon={<CloseCircleOutlined />}
                        message="LM Studio Local Server Not Detected at http://localhost:1234"
                        description="LM Studio is not responding. Launch LM Studio desktop app, download a model, and click 'Start Server' on the Local Server tab (port 1234) to process videos offline."
                      />
                    )}
                  </div>
                )}

                {/* Provider Selection */}
                <Form.Item
                  label="Select AI Provider"
                  name="llm_provider"
                  className="form-item"
                  rules={[{ required: true, message: 'Please select an AI provider' }]}
                >
                  <Select
                    value={selectedProvider}
                    onChange={handleProviderChange}
                    className="settings-input"
                    placeholder="Please select an AI provider"
                  >
                    {Object.entries(providerConfig).map(([key, config]) => (
                      <Select.Option key={key} value={key}>
                        <Space>
                          <span style={{ color: config.color }}>{config.icon}</span>
                          <span>{config.name}</span>
                          <Tag color={config.color}>{config.description}</Tag>
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                {/* Base URL (for Local Ollama / LM Studio or Custom OpenAI-compatible endpoints) */}
                {providerConfig[selectedProvider as keyof typeof providerConfig]?.hasBaseUrl && (
                  <div style={{ marginBottom: 16 }}>
                    <Form.Item
                      label="API Base URL"
                      name="custom_base_url"
                      className="form-item"
                      style={{ marginBottom: 6 }}
                      extra="OpenAI-compatible /v1 endpoint (e.g. http://localhost:11434/v1 for Ollama, http://localhost:1234/v1 for LM Studio)"
                      rules={[
                        { required: selectedProvider === 'custom', message: 'Please enter the API Base URL' }
                      ]}
                    >
                      <Input
                        placeholder={providerConfig[selectedProvider as keyof typeof providerConfig].baseUrlPlaceholder}
                        className="settings-input"
                      />
                    </Form.Item>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>Quick Presets:</Text>
                      <Button
                        size="small"
                        type="dashed"
                        style={{ fontSize: 11, height: 22, padding: '0 6px' }}
                        onClick={() => form.setFieldsValue({ custom_base_url: 'http://localhost:11434/v1' })}
                      >
                        Ollama (11434)
                      </Button>
                      <Button
                        size="small"
                        type="dashed"
                        style={{ fontSize: 11, height: 22, padding: '0 6px' }}
                        onClick={() => form.setFieldsValue({ custom_base_url: 'http://localhost:1234/v1' })}
                      >
                        LM Studio (1234)
                      </Button>
                    </div>
                  </div>
                )}

                {/* Dynamic API Key Input */}
                <Form.Item
                  label={`${providerConfig[selectedProvider as keyof typeof providerConfig].name} API Key`}
                  name={providerConfig[selectedProvider as keyof typeof providerConfig].apiKeyField}
                  className="form-item"
                  rules={selectedProvider === 'ollama' || selectedProvider === 'lmstudio' ? [] : [
                    { required: true, message: 'Please enter API key' }
                  ]}
                  extra={selectedProvider === 'ollama' || selectedProvider === 'lmstudio' ? 'Optional for local models (leave blank if running default local server)' : undefined}
                >
                  <Input.Password
                    placeholder={providerConfig[selectedProvider as keyof typeof providerConfig].placeholder}
                    prefix={<KeyOutlined />}
                    className="settings-input"
                  />
                </Form.Item>

                {/* Optional Model Auto-Discovery from Local Server */}
                {providerConfig[selectedProvider as keyof typeof providerConfig]?.hasBaseUrl && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, marginTop: -8 }}>
                    <Button
                      type="link"
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={fetchingModels}
                      onClick={handleFetchRemoteModels}
                    >
                      Fetch available models from endpoint
                    </Button>
                  </div>
                )}

                {/* Model Selection */}
                <Form.Item
                  label="Model"
                  name="model_name"
                  className="form-item"
                  rules={[{ required: true, message: 'Please enter or select a model name' }]}
                  extra="Choose a model or type any custom model identifier"
                >
                  <Select
                    className="settings-input"
                    placeholder="Enter or select model name"
                    showSearch
                    allowClear
                    onSearch={(val) => setCustomSearchModel(val)}
                    dropdownRender={(menu) => (
                      <div>
                        {menu}
                        <Divider style={{ margin: '8px 0' }} />
                        <div style={{ padding: '0 8px 4px' }}>
                          <Text type="secondary" style={{ fontSize: '12px' }}>
                            Type any custom model name to use it directly
                          </Text>
                        </div>
                      </div>
                    )}
                  >
                    {/* User typed custom model option */}
                    {customSearchModel && (
                      <Select.Option key={`custom-search-${customSearchModel}`} value={customSearchModel}>
                        ➕ Use custom model: <strong>{customSearchModel}</strong>
                      </Select.Option>
                    )}

                    {/* Discovered models from remote/local endpoint */}
                    {discoveredModels.length > 0 && (
                      <Select.OptGroup label={`Discovered on ${providerConfig[selectedProvider as keyof typeof providerConfig]?.name || 'Endpoint'}`}>
                        {discoveredModels.map((m) => (
                          <Select.Option key={`discovered-${m}`} value={m}>
                            {m} (Available)
                          </Select.Option>
                        ))}
                      </Select.OptGroup>
                    )}

                    {/* Local Models (Ollama / LM Studio) */}
                    <Select.OptGroup label="Local Offline Models (Ollama / LM Studio)">
                      <Select.Option value="llama3.2">llama3.2 (Meta Llama 3.2 3B/1B)</Select.Option>
                      <Select.Option value="llama3.1:8b">llama3.1:8b (Llama 3.1 8B)</Select.Option>
                      <Select.Option value="qwen2.5:7b">qwen2.5:7b (Qwen 2.5 7B)</Select.Option>
                      <Select.Option value="mistral:7b">mistral:7b (Mistral 7B)</Select.Option>
                      <Select.Option value="deepseek-r1:8b">deepseek-r1:8b (DeepSeek R1 Distill)</Select.Option>
                      <Select.Option value="gemma2:9b">gemma2:9b (Google Gemma 2 9B)</Select.Option>
                      <Select.Option value="phi4">phi4 (Microsoft Phi-4 14B)</Select.Option>
                      <Select.Option value="local-model">local-model (LM Studio Active)</Select.Option>
                    </Select.OptGroup>

                    {/* DeepSeek Direct */}
                    <Select.OptGroup label="DeepSeek Direct (api.deepseek.com)">
                      <Select.Option value="deepseek-chat">deepseek-chat (DeepSeek V3)</Select.Option>
                      <Select.Option value="deepseek-reasoner">deepseek-reasoner (DeepSeek R1)</Select.Option>
                    </Select.OptGroup>

                    {/* Anthropic Claude */}
                    <Select.OptGroup label="Anthropic Claude">
                      <Select.Option value="claude-3-5-sonnet-20241022">claude-3-5-sonnet-20241022 (Sonnet 3.5)</Select.Option>
                      <Select.Option value="claude-3-5-haiku-20241022">claude-3-5-haiku-20241022 (Haiku 3.5)</Select.Option>
                      <Select.Option value="claude-3-opus-20240229">claude-3-opus-20240229 (Opus 3)</Select.Option>
                    </Select.OptGroup>

                    {/* Groq Ultra-Fast */}
                    <Select.OptGroup label="Groq (Ultra-Fast Inference)">
                      <Select.Option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Llama 3.3 70B)</Select.Option>
                      <Select.Option value="llama-3.1-8b-instant">llama-3.1-8b-instant (Llama 3.1 8B)</Select.Option>
                      <Select.Option value="qwen-2.5-32b">qwen-2.5-32b (Qwen 2.5 32B)</Select.Option>
                      <Select.Option value="deepseek-r1-distill-llama-70b">deepseek-r1-distill-llama-70b</Select.Option>
                    </Select.OptGroup>

                    {/* OpenRouter Multi-Model Gateway */}
                    <Select.OptGroup label="OpenRouter Gateway (200+ Models)">
                      <Select.Option value="anthropic/claude-3.5-sonnet">anthropic/claude-3.5-sonnet</Select.Option>
                      <Select.Option value="deepseek/deepseek-r1">deepseek/deepseek-r1</Select.Option>
                      <Select.Option value="meta-llama/llama-3.3-70b-instruct">meta-llama/llama-3.3-70b-instruct</Select.Option>
                      <Select.Option value="mistralai/mistral-large-2411">mistralai/mistral-large-2411</Select.Option>
                    </Select.OptGroup>

                    {/* Alibaba Qwen */}
                    <Select.OptGroup label="Alibaba Qwen (DashScope)">
                      <Select.Option value="qwen3.8-max-0902">qwen3.8-max-0902 · $2.80/1M in · $8.40/1M out (Flagship 32k)</Select.Option>
                      <Select.Option value="qwen-plus-character">qwen-plus-character · $0.40/1M in · $1.20/1M out (8k)</Select.Option>
                      <Select.Option value="qwen-flash-character">qwen-flash-character · $0.10/1M in · $0.20/1M out (Fast 8k)</Select.Option>
                      <Select.Option value="qwen-plus">qwen-plus · $0.40/1M in · $1.20/1M out (8k)</Select.Option>
                      <Select.Option value="qwen-turbo">qwen-turbo · $0.10/1M in · $0.20/1M out (8k)</Select.Option>
                      <Select.Option value="qwen-max">qwen-max · $2.80/1M in · $8.40/1M out (8k)</Select.Option>
                      <Select.Option value="qwen-long">qwen-long · $0.07/1M in · $0.28/1M out (100k)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* OpenAI */}
                    <Select.OptGroup label="OpenAI">
                      <Select.Option value="gpt-4o">gpt-4o · $2.50/1M in · $10.00/1M out (128k)</Select.Option>
                      <Select.Option value="gpt-4o-mini">gpt-4o-mini · $0.15/1M in · $0.60/1M out (128k)</Select.Option>
                      <Select.Option value="gpt-4-turbo">gpt-4-turbo · $10.00/1M in · $30.00/1M out (128k)</Select.Option>
                      <Select.Option value="gpt-3.5-turbo">gpt-3.5-turbo · $0.50/1M in · $1.50/1M out (16k)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* Google Gemini */}
                    <Select.OptGroup label="Google Gemini">
                      <Select.Option value="gemini-2.5-flash">gemini-2.5-flash · $0.075/1M in · $0.30/1M out (Fast 1M)</Select.Option>
                      <Select.Option value="gemini-1.5-flash">gemini-1.5-flash · $0.075/1M in · $0.30/1M out (1M)</Select.Option>
                      <Select.Option value="gemini-1.5-pro">gemini-1.5-pro · $1.25/1M in · $5.00/1M out (2M)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* SiliconFlow */}
                    <Select.OptGroup label="SiliconFlow">
                      <Select.Option value="deepseek-chat">deepseek-chat (V3) · $0.14/1M in · $0.28/1M out (32k)</Select.Option>
                      <Select.Option value="deepseek-coder">deepseek-coder · $0.14/1M in · $0.28/1M out (16k)</Select.Option>
                    </Select.OptGroup>
                  </Select>
                </Form.Item>

                {/* Active Model Rates Banner */}
                {tokenStats?.model_rates && (
                  (() => {
                    const cleanModel = (activeModelName || 'qwen-plus-character').replace(/ · .*$/, '')
                    const rate = tokenStats.model_rates[cleanModel] || tokenStats.model_rates['qwen-plus-character']
                    if (!rate) return null
                    return (
                      <div style={{
                        background: 'rgba(24, 144, 255, 0.05)',
                        border: '1px solid rgba(24, 144, 255, 0.2)',
                        borderRadius: '8px',
                        padding: '12px 16px',
                        marginBottom: '20px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <Text strong style={{ color: 'var(--ac-ink, #ffffff)', fontSize: '13px' }}>
                            🪙 Token Pricing Rate for {cleanModel}:
                          </Text>
                          <Tag color="blue">{rate.provider || 'AI Provider'}</Tag>
                        </div>
                        <Row gutter={[16, 8]}>
                          <Col span={8} xs={24} sm={8}>
                            <Text type="secondary" style={{ fontSize: '12px', display: 'block' }}>Input Token Price</Text>
                            <Text strong style={{ fontSize: '13px' }}>${rate.input_per_million ? rate.input_per_million.toFixed(2) : (rate.input_rate * 1000).toFixed(2)} / 1M</Text>
                            <div style={{ fontSize: '11px', color: 'var(--ac-muted)' }}>(${rate.input_rate} / 1k tokens)</div>
                          </Col>
                          <Col span={8} xs={24} sm={8}>
                            <Text type="secondary" style={{ fontSize: '12px', display: 'block' }}>Output Token Price</Text>
                            <Text strong style={{ fontSize: '13px' }}>${rate.output_per_million ? rate.output_per_million.toFixed(2) : (rate.output_rate * 1000).toFixed(2)} / 1M</Text>
                            <div style={{ fontSize: '11px', color: 'var(--ac-muted)' }}>(${rate.output_rate} / 1k tokens)</div>
                          </Col>
                          <Col span={8} xs={24} sm={8}>
                            <Text type="secondary" style={{ fontSize: '12px', display: 'block' }}>Est. Cost per Video</Text>
                            <Text strong style={{ fontSize: '13px', color: '#52c41a' }}>~$0.001 - $0.005</Text>
                            <div style={{ fontSize: '11px', color: 'var(--ac-muted)' }}>for ~10-15 min video</div>
                          </Col>
                        </Row>
                      </div>
                    )
                  })()
                )}

                <Form.Item className="form-item">
                  <Space>
                    <Button
                      type="default"
                      icon={<ApiOutlined />}
                      className="test-button"
                      onClick={handleTestApiKey}
                      loading={loading}
                    >
                      Test Connection
                    </Button>
                  </Space>
                </Form.Item>

                <Divider className="settings-divider" />

                <Title level={4} className="section-title">Pipeline Parameters</Title>
                
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="Text Chunk Size"
                      name="chunk_size"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        placeholder="5000" 
                        addonAfter="chars" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="Min Highlight Score Threshold"
                      name="min_score_threshold"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        step="0.1" 
                        min="0" 
                        max="1" 
                        placeholder="0.7" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      label="Max Clips Per Collection"
                      name="max_clips_per_collection"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        placeholder="5" 
                        addonAfter="clips" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item className="form-item">
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SaveOutlined />}
                    size="large"
                    className="save-button"
                    loading={loading}
                  >
                    Save Configuration
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            <Card title="Instructions" className="settings-card">
              <Space direction="vertical" size="large" className="instructions-space">
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 1. Choose AI Provider
                  </Title>
                  <Paragraph className="instruction-text">
                    ClipFarm supports 11+ AI providers:
                    <br />• <Text strong>Local AI</Text>: Ollama (localhost:11434) & LM Studio (localhost:1234) — 100% offline & free.
                    <br />• <Text strong>Cloud APIs</Text>: DeepSeek Direct, Anthropic Claude, Groq, OpenRouter, OpenAI, Google Gemini, SiliconFlow, Alibaba DashScope, and Custom OpenAI endpoints.
                  </Paragraph>
                </div>
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 2. Configuration Parameters
                  </Title>
                  <Paragraph className="instruction-text">
                    • <Text strong>Chunk Size</Text>: Affects analysis chunking, recommend 5000 characters.<br />
                    • <Text strong>Min Score Threshold</Text>: Only clips above this score will be retained.<br />
                    • <Text strong>Clips per Collection</Text>: Maximum number of highlight clips grouped into a topic collection.
                  </Paragraph>
                </div>
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 3. Test Connection
                  </Title>
                  <Paragraph className="instruction-text">
                    Always test your API key to ensure the provider connection succeeds before running pipelines.
                  </Paragraph>
                </div>
              </Space>
            </Card>

            <Card 
              title={
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#FF5E5B', fontWeight: 600 }}>
                  <CoffeeOutlined /> Support ClipFarm Development
                </span>
              } 
              className="settings-card"
              style={{ marginTop: 16, border: '1px solid rgba(255, 94, 91, 0.35)', background: 'rgba(255, 94, 91, 0.03)' }}
            >
              <Paragraph style={{ color: 'var(--ac-sub)', marginBottom: 16, fontSize: '13px', lineHeight: '1.6' }}>
                ClipFarm is an independent, 100% free and open-source studio. If it saves you hours of video editing, helps grow your social channels, or powers your creator pipeline, please consider buying a coffee!
              </Paragraph>
              <Button
                type="primary"
                icon={<CoffeeOutlined style={{ fontSize: '16px' }} />}
                href="https://ko-fi.com/santima"
                target="_blank"
                rel="noopener noreferrer"
                block
                style={{
                  background: 'linear-gradient(135deg, #FF5E5B 0%, #FF7E67 100%)',
                  borderColor: '#FF5E5B',
                  fontWeight: 600,
                  height: '42px',
                  borderRadius: '10px',
                  fontSize: '14px',
                  boxShadow: '0 4px 14px rgba(255, 94, 91, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                Buy me a coffee on Ko-fi
              </Button>
            </Card>
          </TabPane>

          <TabPane 
            tab={
              <span>
                <SoundOutlined />
                Speech Recognition
              </span>
            } 
            key="speech"
          >
            <Card title="Speech Recognition Configuration" className="settings-card">
              <Alert
                message="Speech Recognition Service"
                description="Configure Whisper speech-to-text models for video subtitle generation. Supports local Whisper and cloud APIs."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <SpeechRecognitionConfig
                onConfigChange={(config) => {
                  console.log('Speech config updated:', config)
                }}
              />
            </Card>
          </TabPane>

          <TabPane 
            tab={
              <span>
                <PictureOutlined />
                Watermark Presets
              </span>
            } 
            key="watermarks"
          >
            <WatermarkManager />
          </TabPane>

          <TabPane 
            tab={
              <span>
                <DollarOutlined />
                Token Usage & Rates
              </span>
            } 
            key="tokens"
          >
            <Card title="Token Consumption & Pricing Rates" className="settings-card">
              <Alert
                message="AI Token Consumption & Cost Tracking"
                description="Monitor real-time token consumption across all video processing steps (Outline, Timeline, Scoring, Title, and Clustering) and check pricing rates for all supported AI models."
                type="info"
                showIcon
                className="settings-alert"
                action={
                  <Space>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />} 
                      loading={loadingTokenStats} 
                      onClick={handleRefreshTokenStats}
                    >
                      Refresh
                    </Button>
                    <Popconfirm
                      title="Reset Token Consumption?"
                      description="Are you sure you want to reset all token usage counters to zero?"
                      onConfirm={handleResetTokenStats}
                      okText="Yes, Reset"
                      cancelText="Cancel"
                      okButtonProps={{ danger: true }}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        Reset Counters
                      </Button>
                    </Popconfirm>
                  </Space>
                }
              />

              {/* 4 Overview Statistics Cards */}
              <Row gutter={[16, 16]} style={{ marginTop: '16px', marginBottom: '24px' }}>
                <Col span={6} xs={24} sm={12} md={6}>
                  <Card style={{ background: 'var(--ac-card, #1f1f1f)', border: '1px solid var(--ac-line, #303030)' }}>
                    <Statistic
                      title={<span style={{ color: 'var(--ac-muted)' }}>Total Tokens Consumed</span>}
                      value={tokenStats?.total_tokens || 0}
                      valueStyle={{ color: '#1890ff', fontWeight: 600 }}
                      prefix={<ThunderboltOutlined />}
                    />
                    <div style={{ fontSize: '12px', color: 'var(--ac-muted)', marginTop: '4px' }}>
                      Across all API requests
                    </div>
                  </Card>
                </Col>

                <Col span={6} xs={24} sm={12} md={6}>
                  <Card style={{ background: 'var(--ac-card, #1f1f1f)', border: '1px solid var(--ac-line, #303030)' }}>
                    <Statistic
                      title={<span style={{ color: 'var(--ac-muted)' }}>Estimated Cost</span>}
                      value={tokenStats?.total_cost_usd || 0}
                      precision={4}
                      prefix="$"
                      valueStyle={{ color: '#52c41a', fontWeight: 600 }}
                    />
                    <div style={{ fontSize: '12px', color: 'var(--ac-muted)', marginTop: '4px' }}>
                      Calculated from model rates
                    </div>
                  </Card>
                </Col>

                <Col span={6} xs={24} sm={12} md={6}>
                  <Card style={{ background: 'var(--ac-card, #1f1f1f)', border: '1px solid var(--ac-line, #303030)' }}>
                    <Statistic
                      title={<span style={{ color: 'var(--ac-muted)' }}>Prompt / Input Tokens</span>}
                      value={tokenStats?.total_prompt_tokens || 0}
                      valueStyle={{ color: '#faad14', fontWeight: 600 }}
                    />
                    <div style={{ fontSize: '12px', color: 'var(--ac-muted)', marginTop: '4px' }}>
                      Subtitles & instructions sent
                    </div>
                  </Card>
                </Col>

                <Col span={6} xs={24} sm={12} md={6}>
                  <Card style={{ background: 'var(--ac-card, #1f1f1f)', border: '1px solid var(--ac-line, #303030)' }}>
                    <Statistic
                      title={<span style={{ color: 'var(--ac-muted)' }}>Completion / Output Tokens</span>}
                      value={tokenStats?.total_completion_tokens || 0}
                      valueStyle={{ color: '#722ed1', fontWeight: 600 }}
                    />
                    <div style={{ fontSize: '12px', color: 'var(--ac-muted)', marginTop: '4px' }}>
                      AI generated responses
                    </div>
                  </Card>
                </Col>
              </Row>

              {/* Consumption by Model Table */}
              <Title level={4} style={{ marginTop: '24px', marginBottom: '12px' }}>
                Usage Breakdown by Model
              </Title>
              <Table
                dataSource={
                  tokenStats?.by_model
                    ? Object.entries(tokenStats.by_model).map(([model, data]: [string, any]) => ({
                        key: model,
                        model,
                        ...data
                      }))
                    : []
                }
                pagination={false}
                locale={{ emptyText: 'No token consumption recorded yet. Process a video or test an API to see metrics.' }}
                columns={[
                  {
                    title: 'Model',
                    dataIndex: 'model',
                    key: 'model',
                    render: (text: string) => <Text strong>{text}</Text>
                  },
                  {
                    title: 'Total Tokens',
                    dataIndex: 'total_tokens',
                    key: 'total_tokens',
                    render: (val: number) => (val || 0).toLocaleString()
                  },
                  {
                    title: 'Prompt Tokens',
                    dataIndex: 'prompt_tokens',
                    key: 'prompt_tokens',
                    render: (val: number) => (val || 0).toLocaleString()
                  },
                  {
                    title: 'Completion Tokens',
                    dataIndex: 'completion_tokens',
                    key: 'completion_tokens',
                    render: (val: number) => (val || 0).toLocaleString()
                  },
                  {
                    title: 'Est. Cost ($)',
                    dataIndex: 'cost_usd',
                    key: 'cost_usd',
                    render: (val: number) => `$${(val || 0).toFixed(4)}`
                  },
                  {
                    title: 'Requests',
                    dataIndex: 'requests',
                    key: 'requests',
                    render: (val: number) => val || 0
                  }
                ]}
              />

              <Divider style={{ margin: '28px 0' }} />

              {/* Supported Models Rates Table */}
              <Title level={4} style={{ marginBottom: '12px' }}>
                Model Pricing & Token Rates Reference
              </Title>
              <Paragraph type="secondary" style={{ fontSize: '13px', marginBottom: '16px' }}>
                Standard token rates per million (1M) tokens and context limits across all integrated providers.
              </Paragraph>

              <Table
                dataSource={
                  tokenStats?.model_rates
                    ? Object.entries(tokenStats.model_rates).map(([model, data]: [string, any]) => ({
                        key: model,
                        model,
                        ...data
                      }))
                    : []
                }
                pagination={false}
                columns={[
                  {
                    title: 'Provider',
                    dataIndex: 'provider',
                    key: 'provider',
                    render: (text: string) => (
                      <Tag color={
                        text?.includes('Alibaba') ? 'blue' :
                        text?.includes('OpenAI') ? 'green' :
                        text?.includes('Google') ? 'gold' : 'purple'
                      }>
                        {text}
                      </Tag>
                    )
                  },
                  {
                    title: 'Model ID',
                    dataIndex: 'model',
                    key: 'model',
                    render: (text: string) => <Text code>{text}</Text>
                  },
                  {
                    title: 'Input Rate (Prompt)',
                    dataIndex: 'input_per_million',
                    key: 'input_per_million',
                    render: (val: number, row: any) => (
                      <div>
                        <Text strong>${val ? val.toFixed(2) : (row.input_rate * 1000).toFixed(2)} / 1M</Text>
                        <div style={{ fontSize: '11px', color: 'var(--ac-muted)' }}>(${row.input_rate} / 1k)</div>
                      </div>
                    )
                  },
                  {
                    title: 'Output Rate (Completion)',
                    dataIndex: 'output_per_million',
                    key: 'output_per_million',
                    render: (val: number, row: any) => (
                      <div>
                        <Text strong>${val ? val.toFixed(2) : (row.output_rate * 1000).toFixed(2)} / 1M</Text>
                        <div style={{ fontSize: '11px', color: 'var(--ac-muted)' }}>(${row.output_rate} / 1k)</div>
                      </div>
                    )
                  },
                  {
                    title: 'Description & Best Use Case',
                    dataIndex: 'description',
                    key: 'description',
                    render: (text: string) => <span style={{ fontSize: '12.5px' }}>{text}</span>
                  }
                ]}
              />

              {/* Recent History */}
              {tokenStats?.recent_history && tokenStats.recent_history.length > 0 && (
                <>
                  <Divider style={{ margin: '28px 0' }} />
                  <Title level={4} style={{ marginBottom: '12px' }}>
                    Recent API Calls History
                  </Title>
                  <Table
                    dataSource={tokenStats.recent_history.slice(0, 10).map((item: any, idx: number) => ({
                      key: idx,
                      ...item
                    }))}
                    pagination={false}
                    size="small"
                    columns={[
                      {
                        title: 'Time',
                        dataIndex: 'timestamp',
                        key: 'timestamp',
                        render: (text: string) => text ? new Date(text).toLocaleTimeString() : '-'
                      },
                      {
                        title: 'Model',
                        dataIndex: 'model',
                        key: 'model',
                        render: (text: string) => <Text code>{text}</Text>
                      },
                      {
                        title: 'Prompt Tokens',
                        dataIndex: 'prompt_tokens',
                        key: 'prompt_tokens'
                      },
                      {
                        title: 'Output Tokens',
                        dataIndex: 'completion_tokens',
                        key: 'completion_tokens'
                      },
                      {
                        title: 'Total Tokens',
                        dataIndex: 'total_tokens',
                        key: 'total_tokens',
                        render: (val: number) => <Text strong>{val}</Text>
                      },
                      {
                        title: 'Cost ($)',
                        dataIndex: 'cost_usd',
                        key: 'cost_usd',
                        render: (val: number) => `$${val?.toFixed(5)}`
                      }
                    ]}
                  />
                </>
              )}
            </Card>
          </TabPane>

          <TabPane 
            tab={
              <span>
                <SettingOutlined />
                App Settings
              </span>
            } 
            key="app"
          >
            <Card title="App Settings" className="settings-card">
              <Alert
                message="Application Behavior"
                description="Configure startup behavior and system integration."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <AppSettings />
            </Card>

            <Card title="Privacy & Telemetry" className="settings-card" style={{ marginTop: 16 }}>
              <Alert
                message="Usage Statistics"
                description="To improve ClipFarm, anonymous usage statistics (such as errors or feature usage) can be collected. No video contents, subtitles, or API keys are ever sent. You can disable this anytime."
                type="info"
                showIcon
                className="settings-alert"
              />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
                <div>
                  <Text strong>Allow anonymous usage statistics</Text>
                  <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                    When disabled, no usage statistics will be sent.
                  </Paragraph>
                </div>
                <Switch
                  checked={analyticsOn}
                  onChange={(checked) => {
                    setAnalyticsEnabled(checked)
                    setAnalyticsOn(checked)
                    message.success(checked ? 'Anonymous statistics enabled' : 'Anonymous statistics disabled')
                  }}
                />
              </div>
            </Card>
          </TabPane>
        </Tabs>

      </div>
    </Content>
  )
}

// Apply settings component
const AppSettings: React.FC = () => {
  const [autostartEnabled, setAutostartEnabled] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    checkAutostartStatus()
  }, [])

  const checkAutostartStatus = async () => {
    try {
      const isDesktop = await isDesktopMode()
      if (isDesktop) {
        const { invoke } = await import('@tauri-apps/api/core')
        const enabled = await invoke('is_autostart_enabled')
        setAutostartEnabled(Boolean(enabled))
      }
    } catch (error) {
      console.error('Failed to check auto-start status:', error)
    }
  }

  const handleAutostartToggle = async (enabled: boolean) => {
    const isDesktop = await isDesktopMode()
    if (!isDesktop) {
      message.error('This feature is only available in the desktop app')
      return
    }

    setLoading(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      
      if (enabled) {
        await invoke('enable_autostart')
        message.success('Auto-start enabled')
      } else {
        await invoke('disable_autostart')
        message.success('Auto-start disabled')
      }
      
      setAutostartEnabled(enabled)
    } catch (error) {
      console.error('Failed to toggle autostart:', error)
      message.error(`Operation failed: ${error}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card 
            size="small" 
            style={{ 
              background: 'rgba(255,255,255,0.05)', 
              border: '1px solid #404040',
              marginBottom: '16px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                  <PoweroffOutlined style={{ color: '#1890ff', marginRight: '8px' }} />
                  <Text strong style={{ color: 'var(--ac-ink)' }}>Launch at Startup</Text>
                </div>
                <Text type="secondary" style={{ color: '#b0b0b0' }}>
                  Automatically run ClipFarm when your system starts
                </Text>
              </div>
              <Switch
                checked={autostartEnabled}
                onChange={handleAutostartToggle}
                loading={loading}
                checkedChildren="On"
                unCheckedChildren="Off"
              />
            </div>
          </Card>
        </Col>
      </Row>
      
      <Alert
        message="Note"
        description="Auto-start is available when running in Tauri desktop mode. When enabled, the app runs at login and can be accessed from the system tray."
        type="info"
        showIcon
        style={{ marginTop: '16px' }}
      />
    </div>
  )
}

export default SettingsPage
