import React, { useState, useEffect } from 'react'
import { Modal, Form, Input, Select, Button, Alert, Typography, Divider, message } from 'antd'
import { 
  KeyOutlined, 
  RobotOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined, 
  LinkOutlined,
  ToolOutlined
} from '@ant-design/icons'
import { settingsApi } from '../services/api'

import { useApiModalStore } from '../store/useApiModalStore'

const { Title, Text } = Typography

export interface ApiConfigModalProps {
  open?: boolean
  onClose?: () => void
  onSuccess?: () => void
  title?: string
  description?: string
}

export const PROVIDER_OPTIONS = [
  { 
    label: '⚡ Google Gemini (Recommended — Fast & Free tier available)', 
    value: 'gemini', 
    defaultModel: 'gemini-1.5-flash',
    models: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
    keyUrl: 'https://aistudio.google.com/app/apikey',
    placeholder: 'AIzaSy...'
  },
  { 
    label: '🧠 OpenAI (GPT-4o / GPT-4o-mini)', 
    value: 'openai', 
    defaultModel: 'gpt-4o-mini',
    models: ['gpt-4o-mini', 'gpt-4o'],
    keyUrl: 'https://platform.openai.com/api-keys',
    placeholder: 'sk-proj-...'
  },
  { 
    label: '🤖 Anthropic Claude (Claude 3.5 Sonnet)', 
    value: 'anthropic', 
    defaultModel: 'claude-3-5-sonnet-20241022',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
    keyUrl: 'https://console.anthropic.com/settings/keys',
    placeholder: 'sk-ant-...'
  },
  { 
    label: '🚀 DeepSeek (DeepSeek V3 / R1)', 
    value: 'deepseek', 
    defaultModel: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    keyUrl: 'https://platform.deepseek.com/api_keys',
    placeholder: 'sk-...'
  },
  { 
    label: '🦙 Ollama (100% Free & Local — Zero Key Needed)', 
    value: 'ollama', 
    defaultModel: 'llama3.2',
    models: ['llama3.2', 'llama3', 'mistral', 'qwen2.5'],
    keyUrl: 'https://ollama.ai/',
    placeholder: 'Optional for local Ollama',
    hasBaseUrl: true,
    defaultBaseUrl: 'http://localhost:11434/v1'
  },
  { 
    label: '☁️ Alibaba Qwen (DashScope)', 
    value: 'dashscope', 
    defaultModel: 'qwen-plus',
    models: ['qwen-plus', 'qwen-turbo', 'qwen-max'],
    keyUrl: 'https://dashscope.console.aliyun.com/',
    placeholder: 'sk-...'
  },
  { 
    label: '🔌 Custom OpenAI-Compatible (LocalAI / vLLM / LM Studio)', 
    value: 'custom', 
    defaultModel: 'default',
    models: ['default'],
    keyUrl: '',
    placeholder: 'API Key or dummy string',
    hasBaseUrl: true,
    defaultBaseUrl: 'http://localhost:8000/v1'
  }
]

export const ApiConfigModal: React.FC<ApiConfigModalProps> = ({
  open: controlledOpen,
  onClose: controlledClose,
  onSuccess: controlledSuccess,
  title: propTitle,
  description: propDescription
}) => {
  const store = useApiModalStore()

  const isOpen = controlledOpen !== undefined ? controlledOpen : store.isOpen
  const title = propTitle || store.title || "AI Model Setup Required"
  const description = propDescription || store.description || "ClipFarm uses AI to identify viral hooks, evaluate narrative climax, and generate titles. Please choose an AI provider and enter your API key to continue."

  const [form] = Form.useForm()
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])

  const currentProviderDef = PROVIDER_OPTIONS.find(p => p.value === selectedProvider) || PROVIDER_OPTIONS[0]

  const handleClose = () => {
    if (controlledClose) {
      controlledClose()
    } else {
      store.closeModal()
    }
  }

  const handleSuccessTrigger = () => {
    if (controlledSuccess) {
      controlledSuccess()
    }
    if (controlledClose) {
      controlledClose()
    } else {
      store.triggerSuccess()
    }
  }

  useEffect(() => {
    if (isOpen) {
      loadCurrentConfig()
    } else {
      setTestResult(null)
    }
  }, [isOpen])

  const loadCurrentConfig = async () => {
    try {
      const settings = await settingsApi.getSettings()
      const prov = settings?.api?.llm_provider || 'gemini'
      const key = settings?.api?.api_keys?.[prov] || ''
      const model = settings?.api?.api_model || currentProviderDef.defaultModel
      const baseUrl = settings?.api?.custom_base_url || currentProviderDef.defaultBaseUrl || ''

      setSelectedProvider(prov)
      const def = PROVIDER_OPTIONS.find(p => p.value === prov) || PROVIDER_OPTIONS[0]
      setAvailableModels(def.models)

      form.setFieldsValue({
        provider: prov,
        apiKey: key,
        modelName: model,
        baseUrl: baseUrl
      })
    } catch (e) {
      console.warn('Failed to load current settings for modal:', e)
    }
  }

  const handleProviderChange = (val: string) => {
    setSelectedProvider(val)
    setTestResult(null)
    const def = PROVIDER_OPTIONS.find(p => p.value === val) || PROVIDER_OPTIONS[0]
    setAvailableModels(def.models)
    form.setFieldsValue({
      modelName: def.defaultModel,
      baseUrl: def.defaultBaseUrl || ''
    })
  }

  const handleTestConnection = async () => {
    const values = form.getFieldsValue()
    const prov = values.provider || selectedProvider
    const key = values.apiKey
    const model = values.modelName
    const baseUrl = values.baseUrl

    setTesting(true)
    setTestResult(null)
    try {
      const res = await settingsApi.testApiKey(prov, key, model, baseUrl)
      setTestResult(res)
      if (res.success) {
        message.success('API connection verified successfully!')
      } else {
        message.error(res.error || 'Connection test failed')
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'API connection failed'
      setTestResult({ success: false, error: msg })
      message.error(msg)
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      const existingSettings = await settingsApi.getSettings().catch(() => ({}))
      const existingKeys = existingSettings?.api?.api_keys || {}

      const updatedKeys = {
        ...existingKeys,
        [values.provider]: values.apiKey || ''
      }

      const backendPayload = {
        basic: existingSettings?.basic || {
          app_name: "ClipFarm Desktop",
          app_version: "2.0.0",
          debug_mode: false,
          auto_start: true
        },
        service: existingSettings?.service || {
          host: "127.0.0.1",
          port: 8000,
          max_memory_usage: 2048
        },
        api: {
          api_keys: updatedKeys,
          api_model: values.modelName || currentProviderDef.defaultModel,
          api_max_tokens: 4096,
          api_timeout: 30,
          custom_base_url: values.baseUrl || '',
          llm_provider: values.provider
        },
        processing: existingSettings?.processing || {
          processing_chunk_size: 5000,
          processing_min_score: 0.7,
          processing_max_clips: 5,
          processing_max_retries: 3
        }
      }

      await settingsApi.updateSettings(backendPayload)
      localStorage.removeItem('clipfarm_ai_mode')
      localStorage.setItem('clipfarm_api_configured', 'true')
      localStorage.setItem('clipfarm_llm_provider', values.provider)
      message.success('AI Provider configured successfully!')
      handleSuccessTrigger()
    } catch (err: any) {
      console.error('Failed to save settings:', err)
      message.error('Failed to save settings: ' + (err.message || 'Unknown error'))
    } finally {
      setSaving(false)
    }
  }

  const handleProceedWithHeuristic = () => {
    localStorage.setItem('clipfarm_ai_mode', 'offline_heuristic')
    localStorage.setItem('clipfarm_api_configured', 'true')
    message.info('Proceeding with built-in heuristic highlight detection (no API key required).')
    handleSuccessTrigger()
  }

  return (
    <Modal
      open={isOpen}
      onCancel={handleClose}
      footer={null}
      width={580}
      style={{ top: 40 }}
      styles={{
        content: {
          background: 'var(--ac-card)',
          border: '1px solid var(--ac-line)',
          borderRadius: '16px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
          padding: '28px'
        }
      }}
    >
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'rgba(59, 130, 246, 0.15)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#60A5FA',
            fontSize: '18px'
          }}>
            <RobotOutlined />
          </div>
          <div>
            <Title level={4} style={{ margin: 0, color: 'var(--ac-ink)', fontSize: '18px', fontWeight: 700 }}>
              {title}
            </Title>
            <Text style={{ fontSize: '12px', color: 'var(--ac-muted)' }}>
              Required for automated viral moment detection
            </Text>
          </div>
        </div>

        <Alert
          message={description}
          type="info"
          showIcon
          style={{
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.2)',
            borderRadius: '8px',
            fontSize: '13px',
            marginBottom: '18px'
          }}
        />
      </div>

      <Form form={form} layout="vertical" initialValues={{ provider: 'gemini' }}>
        <Form.Item
          name="provider"
          label={<span style={{ fontWeight: 600, color: 'var(--ac-ink)' }}>Select AI Provider</span>}
          rules={[{ required: true }]}
        >
          <Select
            size="large"
            onChange={handleProviderChange}
            options={PROVIDER_OPTIONS.map(p => ({ label: p.label, value: p.value }))}
            style={{ borderRadius: '8px' }}
          />
        </Form.Item>

        <Form.Item
          name="apiKey"
          label={
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: 'var(--ac-ink)' }}>
                {selectedProvider === 'ollama' ? 'API Key (Optional)' : 'API Key'}
              </span>
              {currentProviderDef.keyUrl && (
                <a
                  href={currentProviderDef.keyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '12px', color: '#60A5FA', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <LinkOutlined /> Get API Key
                </a>
              )}
            </div>
          }
          rules={[
            {
              required: selectedProvider !== 'ollama' && selectedProvider !== 'lmstudio',
              message: 'Please enter your API key'
            }
          ]}
        >
          <Input.Password
            size="large"
            placeholder={currentProviderDef.placeholder}
            prefix={<KeyOutlined style={{ color: 'var(--ac-muted)' }} />}
            style={{ borderRadius: '8px' }}
          />
        </Form.Item>

        {currentProviderDef.hasBaseUrl && (
          <Form.Item
            name="baseUrl"
            label={<span style={{ fontWeight: 600, color: 'var(--ac-ink)' }}>API Base URL</span>}
          >
            <Input
              size="large"
              placeholder={currentProviderDef.defaultBaseUrl}
              style={{ borderRadius: '8px' }}
            />
          </Form.Item>
        )}

        <Form.Item
          name="modelName"
          label={<span style={{ fontWeight: 600, color: 'var(--ac-ink)' }}>Model Name</span>}
          rules={[{ required: true }]}
        >
          <Select
            size="large"
            options={availableModels.map(m => ({ label: m, value: m }))}
            style={{ borderRadius: '8px' }}
          />
        </Form.Item>

        {testResult && (
          <div style={{ marginBottom: '16px' }}>
            <Alert
              type={testResult.success ? 'success' : 'error'}
              message={testResult.success ? 'Connection Successful! Model is responsive.' : (testResult.error || 'Connection Failed')}
              showIcon
              icon={testResult.success ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
              style={{ borderRadius: '8px' }}
            />
          </div>
        )}

        <div style={{ display: 'flex', gap: '10px', marginTop: '24px' }}>
          <Button
            size="large"
            onClick={handleTestConnection}
            loading={testing}
            style={{
              borderRadius: '8px',
              borderColor: 'var(--ac-line)',
              background: 'var(--ac-card)',
              color: 'var(--ac-ink)',
              flex: 1
            }}
          >
            Test Connection
          </Button>

          <Button
            type="primary"
            size="large"
            onClick={handleSave}
            loading={saving}
            style={{
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              border: 'none',
              fontWeight: 600,
              flex: 1.4
            }}
          >
            Save & Continue
          </Button>
        </div>

        <Divider style={{ margin: '18px 0', borderColor: 'var(--ac-line)' }}>
          <span style={{ fontSize: '11.5px', color: 'var(--ac-muted)' }}>OR</span>
        </Divider>

        <div style={{ textAlign: 'center' }}>
          <Button
            type="link"
            size="small"
            onClick={handleProceedWithHeuristic}
            icon={<ToolOutlined />}
            style={{ color: 'var(--ac-muted)', fontSize: '12.5px' }}
          >
            Continue with Built-in Offline Fallback (No AI Key Needed)
          </Button>
        </div>
      </Form>
    </Modal>
  )
}

export default ApiConfigModal
