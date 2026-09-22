import React, { useState, useEffect } from 'react'
import { Card, Button, Typography, Space, Alert, message, Form, Input, Select } from 'antd'
import { 
  SoundOutlined, 
  ApiOutlined, 
  CheckCircleOutlined,
  LoadingOutlined,
  LinkOutlined,
  InfoCircleOutlined
} from '@ant-design/icons'
import { ExternalLink } from '../utils/externalLinks'
import { settingsApi } from '../services/api'
import { isDesktopMode } from '../utils/desktopMode'

const { Title, Text } = Typography
const { Option } = Select

interface FirstRunWizardProps {
  onComplete: () => void
}

interface ConfigForm {
  // Voice recognition configuration
  speechMethod: string
  whisperModel: string
  openaiApiKey: string
  
  // LLMconfig
  llmProvider: string
  llmApiKey: string
  azureApiKey?: string
  azureRegion?: string
  googleApiKey?: string
  aliyunApiKey?: string
  customApiKey?: string
  customEndpoint?: string
}

const FirstRunWizard: React.FC<FirstRunWizardProps> = ({ onComplete }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm<ConfigForm>()
  
  const [config, setConfig] = useState<ConfigForm>({
    speechMethod: 'whisper_local',
    whisperModel: 'base',
    openaiApiKey: '',
    llmProvider: 'dashscope',
    llmApiKey: ''
  })

  // Ensure form is properly initialized when component is mounted
  useEffect(() => {
    form.setFieldsValue(config)
    console.log('Form initialized completed, initial value:', config)
  }, [form])

  const handleNext = () => {
    if (currentStep === 0) {
      // Validate first step configuration
      const values = form.getFieldsValue()
      console.log('Next button clicked - form values:', values)
      console.log('llmProvider:', values.llmProvider)
      console.log('llmApiKey:', values.llmApiKey)
      
      if (!values.llmProvider || !values.llmApiKey || values.llmApiKey.trim() === '') {
        message.error('Choose oneLLMProvider and inputAPI Key')
        return
      }
      setConfig({ ...config, ...values })
      setCurrentStep(1)
    } else {
      handleComplete()
    }
  }

  const handleComplete = async () => {
    setLoading(true)
    try {
      const values = form.getFieldsValue()
      const finalConfig = { ...config, ...values }
      
      // Verify speech recognition configuration
      if (!finalConfig.speechMethod) {
        message.error('Please select a speech recognition plan')
        setLoading(false)
        return
      }
      
      // Only when user provides inputAPI keybefore savingLLMconfig
      if (finalConfig.llmApiKey && finalConfig.llmApiKey.trim()) {
        try {
          await saveLLMConfig(finalConfig)
          console.log('LLMConfiguration saved successfully')
        } catch (error) {
          console.error('LLMConfiguration save failed:', error)
          message.error('LLMConfiguration save failed. Please try again.')
          setLoading(false)
          return
        }
      }
      
      // Save speech recognition configuration - add error handling
      try {
        await saveSpeechConfig(finalConfig)
      } catch (error) {
        console.warn('Failed to save speech recognition configuration, using default configuration:', error)
        // Not throwing an error, allows user to continue with wizard
      }
      
      // If it's localWhisper, Download model
      if (finalConfig.speechMethod === 'whisper_local') {
        await downloadWhisperModel(finalConfig.whisperModel)
      }
      
      // Configuration saved successfully, directly enter tool homepage
      message.success('Configuration complete! Welcome to ClipFarm!')
      onComplete()
    } catch (error) {
      console.error('Configuration save failed:', error)
      const errorMessage = error instanceof Error ? error.message : 'Configuration save failed, please try again'
      message.error(`Configuration save failed: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  // Skip current step, set later
  const handleSkip = async () => {
    if (currentStep === 0) {
      // skipAIModel configuration, enter speech recognition configuration
      setCurrentStep(1)
      message.info('Skipped alreadyAIModel configuration, please set it up in the configuration page later', 3)
    } else {
      // Skip speech recognition config, complete wizard
      // Ensure no empty values are savedAPIconfig
      try {
        // Save only speech recognition config, do not saveLLMconfig
        const values = form.getFieldsValue()
        const finalConfig = { ...config, ...values }
        try {
          await saveSpeechConfig(finalConfig)
        } catch (error) {
          console.warn('Failed to save speech recognition configuration, using default configuration:', error)
        }
        
        message.info('Skipped speech recognition configuration, please set it up in the configuration page later', 3)
        onComplete()
      } catch (error) {
        message.error('Configuration save failed, please try again')
        console.error('Configuration save failed:', error)
      }
    }
  }

  const saveLLMConfig = async (config: ConfigForm) => {
    try {
      // inWebConfiguration is also allowed under mode, used for testing and development
      const isDesktop = await isDesktopMode()
      console.log('Desktop mode detection result:', isDesktop)

      console.log('Start savingLLMconfig:', {
        provider: config.llmProvider,
        apiKeyLength: config.llmApiKey?.length || 0
      })

      // First get existing configuration, avoid clearing what has already been enteredAPI key
      let existingSettings = null
      try {
        existingSettings = await settingsApi.getSettings()
      } catch (error) {
        console.warn('Failed to get existing configuration, default configuration will be used:', error)
      }

      // Get existingAPI keys, Only update current provider's settingskey
      const existingApiKeys = existingSettings?.api?.api_keys || {}
      
      const settings = {
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
            // Only update current provider's settingsAPI key, Keep values from other providers
            dashscope: config.llmProvider === 'dashscope' ? config.llmApiKey : (existingApiKeys.dashscope || ''),
            openai: config.llmProvider === 'openai' ? config.llmApiKey : (existingApiKeys.openai || ''),
            gemini: config.llmProvider === 'gemini' ? config.llmApiKey : (existingApiKeys.gemini || ''),
            siliconflow: config.llmProvider === 'siliconflow' ? config.llmApiKey : (existingApiKeys.siliconflow || ''),
            jimeng_access: existingApiKeys.jimeng_access || '',
            jimeng_secret: existingApiKeys.jimeng_secret || ''
          },
          api_model: config.llmProvider === 'dashscope' ? 'qwen-plus' : 
                     config.llmProvider === 'openai' ? 'gpt-3.5-turbo' :
                     config.llmProvider === 'gemini' ? 'gemini-pro' : 'qwen-plus',
          api_max_tokens: 4000,
          api_timeout: 30
        },
        processing: {
          processing_chunk_size: 5000,
          processing_min_score: 0.7,
          processing_max_clips: 5,
          processing_max_retries: 3
        },
        logs: {
          log_level: "INFO",
          log_file_path: "",
          log_file_max_size: 10,
          log_file_backup_count: 5
        }
      }
      
      console.log('Sending settings to backend:', settings)
      const result = await settingsApi.updateSettings(settings)
      console.log('LLMConfiguration saved successfully, backend response:', result)
    } catch (error) {
      console.error('LLMConfiguration save failed:', error)
      const detail = error instanceof Error ? error.message : 'Unknown error'
      throw new Error(`LLMConfiguration save failed: ${detail}`)
    }
  }

  const saveSpeechConfig = async (config: ConfigForm) => {
    try {
      // Check if desktop mode
      const isDesktop = await isDesktopMode()
      if (!isDesktop) {
        console.warn('Non-desktop mode, skip saving voice config')
        return
      }

      const values = form.getFieldsValue()
      const speechConfig = {
        method: config.speechMethod,
        whisper_config: {
          model_name: config.whisperModel || 'base',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        openai_config: {
          api_key: values.openaiApiKey || '',
          language: 'auto',
          enable_timestamps: true
        },
        azure_config: {
          api_key: values.azureApiKey || '',
          region: values.azureRegion || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        google_config: {
          api_key: values.googleApiKey || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        aliyun_config: {
          api_key: values.aliyunApiKey || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        custom_api_config: {
          api_key: values.customApiKey || '',
          endpoint: values.customEndpoint || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        enable_fallback: true,
        fallback_method: 'whisper_local',
        output_format: 'srt'
      }
      
      const response = await fetch('/api/v1/speech-recognition/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(speechConfig)
      })
      
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Voice recognition configuration save failed: ${response.status} ${errorText}`)
      }
      
      console.log('Speech recognition configuration saved successfully')
    } catch (error) {
      console.error('Voice recognition configuration save failed:', error)
      if (error instanceof Error) {
        throw new Error(`Voice recognition configuration save failed: ${error.message}`)
      } else {
        throw new Error('Voice recognition configuration save failed')
      }
    }
  }

  const downloadWhisperModel = async (modelName: string) => {
    try {
      const response = await fetch('/api/v1/speech-recognition/whisper-models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      })
      
      if (!response.ok) {
        throw new Error('Model download failed')
      }
    } catch (error) {
      console.error('WhisperModel download failed:', error)
      // Not blocking wizard completion
    }
  }


  const testApiConnection = async (provider: string, apiKey: string) => {
    // Retrieve latest from formAPI Keyvalue
    const formValues = form.getFieldsValue()
    const currentApiKey = formValues.llmApiKey || apiKey
    
    console.log('testApiConnection Invocation parameters:', { provider, apiKey })
    console.log('testApiConnection Form value:', formValues)
    console.log('testApiConnection currentAPI Key:', currentApiKey)
    
    if (!currentApiKey || currentApiKey.trim() === '') {
      message.warning('Please enter firstAPI Key')
      return
    }
    
    try {
      const response = await fetch('/api/v1/settings/test-api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: currentApiKey })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const result = await response.json()
      if (result.success) {
        message.success('APIConnection test successful!')
      } else {
        message.error(`APIConnection test failed: ${result.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('APITest failure:', error)
      const detail = error instanceof Error ? error.message : 'Network error'
      message.error(`APIConnection test failed: ${detail}`)
    }
  }

  // getAPI KeyIntelligent prompt for acquiring keys
  const getApiKeyHelp = (provider: string) => {
    const helpMap: Record<string, { name: string; url: string; description: string }> = {
      dashscope: {
        name: 'Alibaba Cloud Tongyi Qianwen',
        url: 'https://dashscope.aliyun.com',
        description: 'Register for an Aliyun account and activateDashScopeService, createAPI Key'
      },
      openai: {
        name: 'OpenAI',
        url: 'https://platform.openai.com',
        description: 'registerOpenAIAccount, inAPI KeysPage creates new secret key'
      },
      gemini: {
        name: 'Google Gemini',
        url: 'https://makersuite.google.com',
        description: 'useGoogleAccount login, atAPI KeysPage create key'
      },
      siliconflow: {
        name: 'SiliconFlow',
        url: 'https://cloud.siliconflow.cn',
        description: 'registerSiliconFlowAccount - Create in consoleAPI Key'
      }
    }
    return helpMap[provider] || helpMap.dashscope
  }

  return (
    <div style={{ 
      maxWidth: '600px', 
      margin: '0 auto', 
      padding: '24px 16px',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center'
    }}>
      {/* Header title area - more compact */}
      <div style={{ textAlign: 'center', marginBottom: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <img src="/favicon.png" alt="ClipFarm" style={{ width: 40, height: 40, marginBottom: '8px', display: 'block' }} />
        <Title level={2} style={{ color: '#1890ff', marginBottom: '8px' }}>
          Welcome to ClipFarm
        </Title>
        <Text type="secondary" style={{ fontSize: '14px' }}>
          Let us quickly configure yourAIVideo slice tool
        </Text>
      </div>

      {/* Main config card - more compact spacing */}
      <Card style={{ marginBottom: '16px' }}>
        {/* Step title - more compact */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            gap: '8px',
            marginBottom: '4px'
          }}>
            {currentStep === 0 ? <ApiOutlined style={{ color: '#1890ff' }} /> : <SoundOutlined style={{ color: '#1890ff' }} />}
            <Title level={4} style={{ margin: 0 }}>
              {currentStep === 0 ? 'configAIModel ' : ' Configure speech recognition'}
            </Title>
          </div>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {currentStep === 0 
              ? 'Select large language model provider and enterAPI Key' 
              : 'Select speech recognition plan'
            }
          </Text>
        </div>

        <Form 
          form={form} 
          layout="vertical" 
          initialValues={config}
          onValuesChange={(changedValues, allValues) => {
            console.log('Form value changes:', { changedValues, allValues })
          }}
        >
          {currentStep === 0 ? (
            // LLMConfiguration steps - more compact layout
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form.Item
                name="llmProvider"
                label="selectAIModel provider"
                rules={[{ required: true, message: 'Choose oneAIModel provider' }]}
                style={{ marginBottom: '12px' }}
              >
                <Select size="middle" placeholder="Select provider">
                  <Option value="dashscope">
                    <Space>
                      <Text strong>Alibaba Cloud Tongyi Qianwen</Text>
                      <Text type="secondary">(Recommended for domestic users)</Text>
                    </Space>
                  </Option>
                  <Option value="openai">
                    <Space>
                      <Text strong>OpenAI GPT</Text>
                      <Text type="secondary">(Requires science internet access)</Text>
                    </Space>
                  </Option>
                  <Option value="gemini">
                    <Space>
                      <Text strong>Google Gemini</Text>
                      <Text type="secondary">(Requires science internet access)</Text>
                    </Space>
                  </Option>
                  <Option value="siliconflow">
                    <Space>
                      <Text strong>SiliconFlow</Text>
                      <Text type="secondary">(Domestic alternative solution)</Text>
                    </Space>
                  </Option>
                </Select>
              </Form.Item>

              {/* API KeyInput box and test button - horizontal layout */}
              <Form.Item
                name="llmApiKey"
                label="API Key"
                rules={[{ required: true, message: 'EnterAPI Key' }]}
                style={{ marginBottom: '12px' }}
              >
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Input.Password 
                    size="middle" 
                    placeholder="Enter yourAPI Key"
                    style={{ 
                      flex: 1,
                      backgroundColor: '#fafafa',
                      borderColor: '#d9d9d9'
                    }}
                  />
                  <Button 
                    type="default"
                    size="middle"
                    onClick={() => {
                      const values = form.getFieldsValue()
                      console.log('Test button clicked - form values:', values)
                      testApiConnection(values.llmProvider || 'dashscope', values.llmApiKey || '')
                    }}
                    style={{ width: '80px' }}
                    icon={<LinkOutlined />}
                  >
                    test
                  </Button>
                </div>
              </Form.Item>

              {/* intelligentAPI KeyGet method hint */}
              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.llmProvider !== currentValues.llmProvider}>
                {({ getFieldValue }) => {
                  const provider = getFieldValue('llmProvider') || 'dashscope'
                  const help = getApiKeyHelp(provider)
                  return (
                    <Alert
                      message={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <InfoCircleOutlined />
                          <span>{help.name} API KeyAcquisition method</span>
                        </div>
                      }
                      description={
                        <div>
                          <p style={{ margin: '4px 0', fontSize: '12px' }}>{help.description}</p>
                          <p style={{ margin: '4px 0', fontSize: '12px' }}>
                            access: <ExternalLink url={help.url} text={help.url} />
                          </p>
                        </div>
                      }
                      type="info"
                      showIcon={false}
                      style={{ fontSize: '12px' }}
                    />
                  )
                }}
              </Form.Item>
            </Space>
          ) : (
            // Speech recognition configuration steps - more compact layout
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form.Item
                name="speechMethod"
                label="Select speech recognition plan"
                rules={[{ required: true, message: 'Please select a speech recognition plan' }]}
                style={{ marginBottom: '12px' }}
              >
                <Select size="middle" placeholder="Select a plan">
                  <Option value="whisper_local">
                    <Space>
                      <span>🆓</span>
                      <Text strong>local Whisper model</Text>
                      <Text type="secondary">(Free offline - Recommended for beginners)</Text>
                    </Space>
                  </Option>
                  <Option value="openai_api">
                    <Space>
                      <span>🤖</span>
                      <Text strong>OpenAI Whisper API</Text>
                      <Text type="secondary">(Cloud processing, higher accuracy)</Text>
                    </Space>
                  </Option>
                  <Option value="azure_speech">
                    <Space>
                      <span>☁️</span>
                      <Text strong>Azure Speech Services</Text>
                      <Text type="secondary">(Enterprise service)</Text>
                    </Space>
                  </Option>
                  <Option value="google_speech">
                    <Space>
                      <span>🌐</span>
                      <Text strong>Google Speech-to-Text</Text>
                      <Text type="secondary">(Multi-language support)</Text>
                    </Space>
                  </Option>
                  <Option value="aliyun_speech">
                    <Space>
                      <span>☁️</span>
                      <Text strong>Alibaba Cloud Speech Recognition</Text>
                      <Text type="secondary">(Chinese optimization)</Text>
                    </Space>
                  </Option>
                  <Option value="custom_api">
                    <Space>
                      <span>⚙️</span>
                      <Text strong>CustomizationAPI</Text>
                      <Text type="secondary">(Custom endpoint)</Text>
                    </Space>
                  </Option>
                </Select>
              </Form.Item>

              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.speechMethod !== currentValues.speechMethod} noStyle>
                {({ getFieldValue }) => {
                  const speechMethod = getFieldValue('speechMethod')
                  
                  if (speechMethod === 'whisper_local') {
                    return (
                      <Form.Item
                        name="whisperModel"
                        label="Select model size"
                        style={{ marginBottom: '12px' }}
                      >
                        <Select size="middle" placeholder="Select model">
                          <Option value="tiny">Tiny (39MB) - Fastest speed</Option>
                          <Option value="base">Base (74MB) - Balance selection (recommended))</Option>
                          <Option value="small">Small (244MB) - Good accuracy</Option>
                          <Option value="medium">Medium (769MB) - High accuracy</Option>
                          <Option value="large">Large (1550MB) - Highest accuracy</Option>
                        </Select>
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'openai_api') {
                    return (
                      <Form.Item
                        name="openaiApiKey"
                        label="OpenAI API Key"
                        rules={[{ required: true, message: 'EnterOpenAI API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="EnterOpenAI API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'azure_speech') {
                    return (
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Form.Item
                          name="azureApiKey"
                          label="Azure API Key"
                          rules={[{ required: true, message: 'EnterAzure API Key' }]}
                          style={{ marginBottom: '8px' }}
                        >
                          <Input.Password 
                            size="middle" 
                            placeholder="EnterAzure Speech API Key"
                          />
                        </Form.Item>
                        <Form.Item
                          name="azureRegion"
                          label="Azure region"
                          style={{ marginBottom: '12px' }}
                        >
                          <Input 
                            size="middle" 
                            placeholder="e.g. / example: eastus, westus2"
                          />
                        </Form.Item>
                      </Space>
                    )
                  }
                  
                  if (speechMethod === 'google_speech') {
                    return (
                      <Form.Item
                        name="googleApiKey"
                        label="Google API Key"
                        rules={[{ required: true, message: 'EnterGoogle API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="EnterGoogle Speech-to-Text API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'aliyun_speech') {
                    return (
                      <Form.Item
                        name="aliyunApiKey"
                        label="Aliyun API Key"
                        rules={[{ required: true, message: 'Enter Aliyun Access Key and Secret Key API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="Enter Aliyun Speech Recognition API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'custom_api') {
                    return (
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Form.Item
                          name="customApiKey"
                          label="Customization API Key"
                          rules={[{ required: true, message: 'Enter custom API Key' }]}
                          style={{ marginBottom: '8px' }}
                        >
                          <Input.Password 
                            size="middle" 
                            placeholder="Enter custom API Key"
                          />
                        </Form.Item>
                        <Form.Item
                          name="customEndpoint"
                          label="API endpoint"
                          rules={[{ required: true, message: 'EnterAPIendpoint' }]}
                          style={{ marginBottom: '12px' }}
                        >
                          <Input 
                            size="middle" 
                            placeholder="e.g. / example: https://api.example.com/speech"
                          />
                        </Form.Item>
                      </Space>
                    )
                  }
                  
                  return null
                }}
              </Form.Item>

              {/* Smart configuration instructions - display corresponding instructions based on selected option */}
              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.speechMethod !== currentValues.speechMethod} style={{ marginBottom: '8px' }}>
                {({ getFieldValue }) => {
                  const speechMethod = getFieldValue('speechMethod')
                  
                  const getMethodDescription = (method: string) => {
                    const descriptions: Record<string, { icon: string; name: string; description: string }> = {
                      whisper_local: {
                        icon: '🆓',
                        name: 'local Whisper model',
                        description: 'Free offline usage, model will be automatically downloaded on first use, no network connection required after that. Recommended for beginners. '
                      },
                      openai_api: {
                        icon: '🤖',
                        name: 'OpenAI Whisper API',
                        description: 'Cloud processing, higher recognition accuracy, billed by usage volume. Requires a stable network connection. '
                      },
                      azure_speech: {
                        icon: '☁️',
                        name: 'Azure Speech Services',
                        description: 'Enterprise-grade speech recognition service, supports multiple languages and dialects, suitable for commercial use. '
                      },
                      google_speech: {
                        icon: '🌐',
                        name: 'Google Speech-to-Text',
                        description: 'Multi-language support, high recognition accuracy, supports real-time speech recognition. '
                      },
                      aliyun_speech: {
                        icon: '☁️',
                        name: 'Alibaba Cloud Speech Recognition',
                        description: 'Chinese-optimized, fast domestic access, supports various Chinese dialect recognition. '
                      },
                      custom_api: {
                        icon: '⚙️',
                        name: 'CustomizationAPI',
                        description: 'Support custom endpoint, can connect to your own speech recognition service. '
                      }
                    }
                    return descriptions[method] || descriptions.whisper_local
                  }
                  
                  const methodInfo = getMethodDescription(speechMethod)
                  
                  return (
                    <Alert
                      message={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{methodInfo.icon}</span>
                          <span>{methodInfo.name} Configuration details</span>
                        </div>
                      }
                      description={
                        <div style={{ fontSize: '12px' }}>
                          <p style={{ margin: '4px 0' }}>{methodInfo.description}</p>
                        </div>
                      }
                      type="info"
                      showIcon={false}
                      style={{ fontSize: '12px', marginTop: '8px' }}
                    />
                  )
                }}
              </Form.Item>
            </Space>
          )}
        </Form>
      </Card>

      {/* Bottom button area - remove step indicator, unify button style */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div>
          {currentStep > 0 && (
            <Button 
              size="middle"
              onClick={() => setCurrentStep(0)}
              disabled={loading}
            >
              Previous step
            </Button>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button 
            type="default"
            size="middle"
            onClick={handleSkip}
            disabled={loading}
          >
            Set later
          </Button>
          <Button 
            type="primary" 
            size="middle"
            onClick={handleNext}
            loading={loading}
            icon={loading ? <LoadingOutlined /> : <CheckCircleOutlined />}
          >
            {currentStep === 0 ? 'Next ' : ' Start using'}
          </Button>
        </div>
      </div>

      {loading && (
        <div style={{ 
          textAlign: 'center', 
          marginTop: '20px',
          padding: '20px',
          background: '#f5f5f5',
          borderRadius: '8px'
        }}>
          <LoadingOutlined style={{ fontSize: '24px', marginRight: '8px' }} />
          <Text>Saving configuration and creating sample project...</Text>
        </div>
      )}
    </div>
  )
}

export default FirstRunWizard