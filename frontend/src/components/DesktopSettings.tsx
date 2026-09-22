import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Tabs, 
  Form, 
  Input, 
  InputNumber, 
  Switch, 
  Button, 
  message, 
  Space,
  Typography,
  Divider,
  Row,
  Col,
  Statistic
} from 'antd';
import { 
  SettingOutlined, 
  ApiOutlined, 
  DatabaseOutlined, 
  ToolOutlined,
  SaveOutlined,
  ReloadOutlined
} from '@ant-design/icons';

const { Title } = Typography;
const { TabPane } = Tabs;

interface DesktopConfig {
  app_name: string;
  app_version: string;
  debug_mode: boolean;
  host: string;
  port: number;
  max_memory_usage: number;
  database_url: string;
  celery_broker_url: string;
  celery_result_backend: string;
  celery_worker_concurrency: number;
  dashscope_api_key: string;
  openai_api_key: string;
  gemini_api_key: string;
  siliconflow_api_key: string;
  default_model: string;
  max_tokens: number;
  timeout: number;
  chunk_size: number;
  min_score_threshold: number;
  max_clips_per_collection: number;
  max_retries: number;
  log_level: string;
  log_retention_days: number;
}

interface SystemInfo {
  platform: string;
  platform_version: string;
  architecture: string;
  processor: string;
  memory_total: number;
  memory_available: number;
  memory_usage_percent: number;
  disk_usage_percent: number;
  python_version: string;
  app_version: string;
}

interface ServiceStatus {
  is_running: boolean;
  port: number;
  uptime: string;
  memory_usage: number;
  cpu_usage: number;
  last_health_check: string;
}

const DesktopSettings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<DesktopConfig | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);

  // Load configuration
  const loadConfig = async () => {
    try {
      const response = await fetch('/api/v1/desktop/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data.config);
        form.setFieldsValue(data.config);
      } else {
        message.error('Configuration loading failed');
      }
    } catch (error) {
      console.error('Configuration loading error:', error);
      message.error('Configuration loading failed');
    }
  };

  // Loading configuration
  const loadSystemInfo = async () => {
    try {
      const response = await fetch('/api/v1/desktop/system/info');
      if (response.ok) {
        const data = await response.json();
        setSystemInfo(data);
      }
    } catch (error) {
      console.error('Failed to load system information:', error);
    }
  };

  // loading service state
  const loadServiceStatus = async () => {
    try {
      const response = await fetch('/api/v1/desktop/service/status');
      if (response.ok) {
        const data = await response.json();
        setServiceStatus(data);
      }
    } catch (error) {
      console.error('Failed to load service status:', error);
    }
  };

  // Save configuration
  const saveConfig = async (values: DesktopConfig) => {
    setLoading(true);
    try {
      // Convert flattend structure to backend expectedDesktopConfigStructure
      const configData = {
        app_name: values.app_name || "ClipFarm Desktop",
        app_version: values.app_version || "1.0.0",
        debug_mode: values.debug_mode || false,
        host: values.host || "127.0.0.1",
        port: values.port || 8000,
        max_memory_usage: values.max_memory_usage || 2048,
        database_url: values.database_url || "sqlite:///data/autoclip.db",
        celery_broker_url: values.celery_broker_url || "db+sqlite:///data/celery_broker.db",
        celery_result_backend: values.celery_result_backend || "db+sqlite:///data/celery_results.db",
        celery_worker_concurrency: values.celery_worker_concurrency || 1,
        dashscope_api_key: values.dashscope_api_key || "",
        openai_api_key: values.openai_api_key || "",
        gemini_api_key: values.gemini_api_key || "",
        siliconflow_api_key: values.siliconflow_api_key || "",
        default_model: values.default_model || "qwen-plus",
        max_tokens: values.max_tokens || 4000,
        timeout: values.timeout || 30,
        chunk_size: values.chunk_size || 5000,
        min_score_threshold: values.min_score_threshold || 0.7,
        max_clips_per_collection: values.max_clips_per_collection || 5,
        max_retries: values.max_retries || 3,
        log_level: values.log_level || "INFO",
        log_retention_days: values.log_retention_days || 7
      };

      const response = await fetch('/api/v1/desktop/config', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configData),
      });

      if (response.ok) {
        message.success('configuration saved successfully');
        setConfig(configData);
      } else {
        const errorData = await response.json();
        message.error(`failed to save configuration: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Configuration save error:', error);
      message.error('failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    loadSystemInfo();
    loadServiceStatus();
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>
        <SettingOutlined /> Desktop settings
      </Title>
      
      <Tabs defaultActiveKey="basic">
        {/* Basic settings */}
        <TabPane tab={<span><SettingOutlined />Basic settings</span>} key="basic">
          <Card>
            <Form
              form={form}
              layout="vertical"
              onFinish={saveConfig}
              initialValues={config ?? undefined}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="app_name"
                    label="application name"
                    rules={[{ required: true, message: 'Please enter application name' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="app_version"
                    label="application version"
                    rules={[{ required: true, message: 'Please enter application version' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="debug_mode"
                label="Debug mode"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Divider />

              <Title level={4}>service configuration</Title>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="host"
                    label="host address"
                    rules={[{ required: true, message: 'Please enter host address' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="port"
                    label="Port"
                    rules={[{ required: true, message: 'enter port' }]}
                  >
                    <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="max_memory_usage"
                label="maximum memory usage (MB)"
                rules={[{ required: true, message: 'Please enter maximum memory usage' }]}
              >
                <InputNumber min={512} max={8192} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button 
                    type="primary" 
                    htmlType="submit" 
                    loading={loading}
                    icon={<SaveOutlined />}
                  >
                    Save configuration
                  </Button>
                  <Button 
                    icon={<ReloadOutlined />}
                    onClick={loadConfig}
                  >
                    reload
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        {/* APISet */}
        <TabPane tab={<span><ApiOutlined />APISet</span>} key="api">
          <Card>
            <Form
              form={form}
              layout="vertical"
              onFinish={saveConfig}
              initialValues={config ?? undefined}
            >
              <Title level={4}>APIKey</Title>
              <Form.Item
                name="dashscope_api_key"
                label="DashScope API Key"
              >
                <Input.Password placeholder="EnterDashScope API Key" />
              </Form.Item>

              <Form.Item
                name="openai_api_key"
                label="OpenAI API Key"
              >
                <Input.Password placeholder="EnterOpenAI API Key" />
              </Form.Item>

              <Form.Item
                name="gemini_api_key"
                label="Gemini API Key"
              >
                <Input.Password placeholder="EnterGemini API Key" />
              </Form.Item>

              <Form.Item
                name="siliconflow_api_key"
                label="SiliconFlow API Key"
              >
                <Input.Password placeholder="EnterSiliconFlow API Key" />
              </Form.Item>

              <Divider />

              <Title level={4}>model configuration</Title>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="default_model"
                    label="default model"
                    rules={[{ required: true, message: 'Please enter default model' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="max_tokens"
                    label="MaxTokendigit"
                    rules={[{ required: true, message: 'enter maxTokendigit' }]}
                  >
                    <InputNumber min={100} max={8000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="timeout"
                label="Timeout (seconds))"
                rules={[{ required: true, message: 'Please enter timeout' }]}
              >
                <InputNumber min={10} max={300} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item>
                <Button 
                  type="primary" 
                  htmlType="submit" 
                  loading={loading}
                  icon={<SaveOutlined />}
                >
                  Save configuration
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        {/* Process settings */}
        <TabPane tab={<span><ToolOutlined />Process settings</span>} key="processing">
          <Card>
            <Form
              form={form}
              layout="vertical"
              onFinish={saveConfig}
              initialValues={config ?? undefined}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="chunk_size"
                    label="Block size"
                    rules={[{ required: true, message: 'enter block size' }]}
                  >
                    <InputNumber min={1000} max={10000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="min_score_threshold"
                    label="Minimum score threshold"
                    rules={[{ required: true, message: 'Please enter minimum score threshold' }]}
                  >
                    <InputNumber min={0.1} max={1.0} step={0.1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="max_clips_per_collection"
                    label="Maximum number of fragments per collection"
                    rules={[{ required: true, message: 'Please enter maximum number of fragments' }]}
                  >
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="max_retries"
                    label="maximum retry count"
                    rules={[{ required: true, message: 'Please enter maximum number of retries' }]}
                  >
                    <InputNumber min={1} max={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Button 
                  type="primary" 
                  htmlType="submit" 
                  loading={loading}
                  icon={<SaveOutlined />}
                >
                  Save configuration
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        {/* system information */}
        <TabPane tab={<span><DatabaseOutlined />system information</span>} key="system">
          <Card>
            {systemInfo && (
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="Operating system"
                    value={systemInfo.platform}
                    suffix={systemInfo.platform_version}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="Architecture"
                    value={systemInfo.architecture}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="PythonVersion"
                    value={systemInfo.python_version}
                  />
                </Col>
              </Row>
            )}

            {systemInfo && (
              <>
                <Divider />
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="Total memory"
                      value={formatBytes(systemInfo.memory_total)}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="available memory"
                      value={formatBytes(systemInfo.memory_available)}
                    />
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="memory utilization rate"
                      value={systemInfo.memory_usage_percent}
                      suffix="%"
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="disk utilization rate"
                      value={systemInfo.disk_usage_percent}
                      suffix="%"
                    />
                  </Col>
                </Row>
              </>
            )}

            {serviceStatus && (
              <>
                <Divider />
                <Title level={4}>Service status</Title>
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic
                      title="Service status"
                      value={serviceStatus.is_running ? "Running" : "Stopped"}
                      valueStyle={{ color: serviceStatus.is_running ? '#3f8600' : '#cf1322' }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="Port"
                      value={serviceStatus.port}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="Runtime"
                      value={serviceStatus.uptime}
                    />
                  </Col>
                </Row>
              </>
            )}

            <Divider />
            <Button 
              icon={<ReloadOutlined />}
              onClick={() => {
                loadSystemInfo();
                loadServiceStatus();
              }}
            >
              refresh information
            </Button>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default DesktopSettings;
