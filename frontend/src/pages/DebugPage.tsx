import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Card, 
  Button, 
  Typography, 
  Space, 
  Alert, 
  Row, 
  Col, 
  Form, 
  Input, 
  message,
  Tag,
  Descriptions,
  Collapse
} from 'antd'
import { 
  BugOutlined, 
  ApiOutlined, 
  SettingOutlined, 
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import { settingsApi } from '../services/api'
import { isDesktopMode } from '../utils/desktopMode'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

interface DebugInfo {
  desktopMode: {
    isDesktop: boolean
    source: string
    environment?: any
  }
  apiStatus: {
    settings: boolean
    desktopMode: boolean
    testApi: boolean
  }
  currentSettings: any
  errors: string[]
}

const DebugPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [debugInfo, setDebugInfo] = useState<DebugInfo>({
    desktopMode: { isDesktop: false, source: 'unknown' },
    apiStatus: { settings: false, desktopMode: false, testApi: false },
    currentSettings: null,
    errors: []
  })
  const [form] = Form.useForm()

  // Test desktop mode detection
  const testDesktopMode = async () => {
    try {
      setLoading(true)
      const isDesktop = await isDesktopMode()
      const info = {
        isDesktop,
        source: 'frontend_check',
        environment: {
          userAgent: navigator.userAgent,
          hasTauri: Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__),
          location: window.location.href,
        }
      }
      setDebugInfo(prev => ({
        ...prev,
        desktopMode: info
      }))
      message.success('Desktop mode detection completed')
    } catch (error: any) {
      const errorMsg = `Desktop mode detection failed: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // TestAPIConnect
  const testApiConnections = async () => {
    const errors: string[] = []
    const apiStatus = { settings: false, desktopMode: false, testApi: false }

    try {
      setLoading(true)
      
      // Test settingsAPI
      try {
        const settings = await settingsApi.getSettings()
        apiStatus.settings = true
        setDebugInfo(prev => ({
          ...prev,
          currentSettings: settings
        }))
      } catch (error: any) {
        errors.push(`Settings API failed: ${error.message}`)
      }

      // Test desktop modeAPI
      try {
        const desktopMode = await settingsApi.checkDesktopMode()
        apiStatus.desktopMode = true
        console.log('Desktop modeAPIResponse:', desktopMode)
      } catch (error: any) {
        errors.push(`Desktop mode API failed: ${error.message}`)
      }

      // TestAPI KeyTest interface
      try {
        const testResult = await settingsApi.testApiKey('dashscope', 'test-key')
        apiStatus.testApi = true
        console.log('APITest response:', testResult)
      } catch (error: any) {
        errors.push(`API test endpoint failed: ${error.message}`)
      }

      setDebugInfo(prev => ({
        ...prev,
        apiStatus,
        errors: [...prev.errors, ...errors]
      }))

      if (errors.length === 0) {
        message.success('All API connection tests passed')
      } else {
        message.warning(`Some API tests failed: ${errors.length} errors found`)
      }
    } catch (error: any) {
      const errorMsg = `API connection test failed: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // TestAPI KeySave
  const testApiKeySave = async () => {
    try {
      setLoading(true)
      const values = form.getFieldsValue()
      
      if (!values.apiKey || !values.provider) {
        message.error('Please enter API Key and Provider')
        return
      }

      const testSettings = {
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
            dashscope: values.provider === 'dashscope' ? values.apiKey : '',
            openai: values.provider === 'openai' ? values.apiKey : '',
            gemini: values.provider === 'gemini' ? values.apiKey : '',
            siliconflow: values.provider === 'siliconflow' ? values.apiKey : '',
            jimeng_access: '',
            jimeng_secret: ''
          },
          api_model: values.provider === 'dashscope' ? 'qwen-plus' : 
                     values.provider === 'openai' ? 'gpt-3.5-turbo' :
                     values.provider === 'gemini' ? 'gemini-pro' : 'qwen-plus',
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
          log_retention_days: 7
        }
      }

      await settingsApi.updateSettings(testSettings)
      message.success('API Key save test successful!')
    } catch (error: any) {
      const errorMsg = `API Key save failed: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // Clear cache andRe-detect
  const refreshAll = async () => {
    await testDesktopMode()
    await testApiConnections()
  }

  // Auto-detect on page load
  useEffect(() => {
    testDesktopMode()
    testApiConnections()
  }, [])

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <Title level={2}>
            <BugOutlined /> System Debug Page
          </Title>
          
          <Paragraph>
            This page is used to debug desktop mode detection and API key configuration. Please test functions in sequence.
          </Paragraph>

          <Row gutter={[16, 16]}>
            {/* Test desktop mode detection */}
            <Col span={24}>
              <Card title="Desktop Mode Detection" extra={
                <Space>
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={testDesktopMode}
                    loading={loading}
                  >
                    Re-detect
                  </Button>
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={refreshAll}
                    loading={loading}
                  >
                    Refresh All
                  </Button>
                </Space>
              }>
                <Descriptions bordered column={2}>
                  <Descriptions.Item label="Desktop Mode Status">
                    <Tag color={debugInfo.desktopMode.isDesktop ? 'green' : 'red'}>
                      {debugInfo.desktopMode.isDesktop ? 'Yes' : 'No'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Detection Source">
                    <Tag color="blue">{debugInfo.desktopMode.source}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Environment Info" span={2}>
                    <pre style={{ margin: 0, fontSize: '12px' }}>
                      {JSON.stringify(debugInfo.desktopMode.environment, null, 2)}
                    </pre>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>

            {/* APIConnect test */}
            <Col span={24}>
              <Card title="API Connection Test" extra={
                <Button 
                  icon={<ApiOutlined />} 
                  onClick={testApiConnections}
                  loading={loading}
                >
                  Test Connection
                </Button>
              }>
                <Row gutter={16}>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.settings ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>Settings API</Text>
                      </Space>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.desktopMode ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>Desktop Mode API</Text>
                      </Space>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.testApi ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>API Test Endpoint</Text>
                      </Space>
                    </Card>
                  </Col>
                </Row>
              </Card>
            </Col>

            {/* API KeySave test */}
            <Col span={24}>
              <Card title="API Key Save Test" extra={
                <Button 
                  type="primary"
                  icon={<SettingOutlined />} 
                  onClick={testApiKeySave}
                  loading={loading}
                >
                  Test Save
                </Button>
              }>
                <Form form={form} layout="vertical">
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="provider"
                        label="API Provider"
                        rules={[{ required: true, message: 'Please select a provider' }]}
                      >
                        <Input placeholder="dashscope, openai, gemini, siliconflow" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="apiKey"
                        label="API Key"
                        rules={[{ required: true, message: 'Please enter API Key' }]}
                      >
                        <Input.Password placeholder="Enter API Key" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
              </Card>
            </Col>

            {/* Current settings information */}
            {debugInfo.currentSettings && (
              <Col span={24}>
                <Card title="Current Settings Info">
                  <Collapse>
                    <Panel header="View Full Settings" key="1">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '16px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        maxHeight: '400px',
                        overflow: 'auto'
                      }}>
                        {JSON.stringify(debugInfo.currentSettings, null, 2)}
                      </pre>
                    </Panel>
                  </Collapse>
                </Card>
              </Col>
            )}

            {/* Error message */}
            {debugInfo.errors.length > 0 && (
              <Col span={24}>
                <Card title="Error Details" style={{ borderColor: '#ff4d4f' }}>
                  {debugInfo.errors.map((error, index) => (
                    <Alert
                      key={index}
                      message={error}
                      type="error"
                      showIcon
                      style={{ marginBottom: '8px' }}
                    />
                  ))}
                </Card>
              </Col>
            )}

            {/* Usage instructions */}
            <Col span={24}>
              <Card title="Instructions">
                <Alert
                  message="Debug Steps"
                  description={
                    <div>
                      <p>1. First verify if Desktop Mode Detection displays "Yes" or active status</p>
                      <p>2. Run "API Connection Test" to verify connectivity</p>
                      <p>3. Test saving credentials in "API Key Save Test"</p>
                      <p>4. If errors occur, inspect the Error Details section</p>
                    </div>
                  }
                  type="info"
                  showIcon
                />
              </Card>
            </Col>
          </Row>
        </div>
      </Content>
    </Layout>
  )
}

export default DebugPage