import React, { useState, useEffect } from 'react'
import { 
  Card, 
  Button, 
  Table, 
  Tag, 
  Space, 
  Typography, 
  Modal, 
  Form, 
  Input, 
  Select, 
  Slider, 
  Upload, 
  message, 
  Popconfirm,
  Row,
  Col
} from 'antd'
import { 
  PlusOutlined, 
  DeleteOutlined, 
  UploadOutlined, 
  PictureOutlined,
  EyeOutlined
} from '@ant-design/icons'
import { watermarkApi, WatermarkPreset } from '../services/api'

const { Text, Paragraph } = Typography
const { Option } = Select

export const WatermarkManager: React.FC = () => {
  const [presets, setPresets] = useState<WatermarkPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // Live preview settings for modal
  const [modalPosition, setModalPosition] = useState<'bottom_right' | 'bottom_left' | 'top_right' | 'top_left'>('bottom_right')
  const [modalScale, setModalScale] = useState<number>(15)
  const [modalOpacity, setModalOpacity] = useState<number>(85)
  const [modalMargin, setModalMargin] = useState<number>(24)

  const loadPresets = async () => {
    setLoading(true)
    try {
      const data = await watermarkApi.getPresets()
      setPresets(data)
    } catch (err: any) {
      console.error('Failed to load watermark presets:', err)
      message.error('Failed to load watermark presets')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPresets()
  }, [])

  const handleOpenModal = () => {
    form.resetFields()
    setSelectedFile(null)
    setPreviewUrl(null)
    setModalPosition('bottom_right')
    setModalScale(15)
    setModalOpacity(85)
    setModalMargin(24)
    setIsModalOpen(true)
  }

  const handleFileChange = (info: any) => {
    const file = info.file?.originFileObj || info.file
    if (file) {
      setSelectedFile(file)
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
    }
  }

  const handleCreatePreset = async () => {
    try {
      const values = await form.validateFields()
      if (!selectedFile) {
        message.error('Please upload a logo image (PNG/JPG/SVG)')
        return
      }

      const formData = new FormData()
      formData.append('name', values.name)
      formData.append('logo_file', selectedFile)
      formData.append('position', modalPosition)
      formData.append('scale_percent', String(modalScale))
      formData.append('opacity', String(modalOpacity / 100))
      formData.append('margin', String(modalMargin))
      formData.append('is_default', String(values.is_default || false))

      await watermarkApi.createPreset(formData)
      message.success('Watermark preset created successfully!')
      setIsModalOpen(false)
      loadPresets()
    } catch (err: any) {
      console.error('Failed to create watermark preset:', err)
      message.error(err.response?.data?.detail || 'Failed to create watermark preset')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await watermarkApi.deletePreset(id)
      message.success('Preset deleted')
      loadPresets()
    } catch (err) {
      message.error('Failed to delete preset')
    }
  }

  const handleSetDefault = async (preset: WatermarkPreset) => {
    try {
      await watermarkApi.updatePreset(preset.id, { is_default: true })
      message.success(`Set "${preset.name}" as default preset`)
      loadPresets()
    } catch (err) {
      message.error('Failed to set default preset')
    }
  }

  const positionLabels: Record<string, string> = {
    bottom_right: '↘ Bottom-Right',
    bottom_left: '↙ Bottom-Left',
    top_right: '↗ Top-Right',
    top_left: '↖ Top-Left'
  }

  const columns = [
    {
      title: 'Logo',
      dataIndex: 'logo_url',
      key: 'logo_url',
      width: 100,
      render: (url: string, record: WatermarkPreset) => (
        <div style={{
          width: '64px',
          height: '40px',
          background: '#141414',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid var(--ac-line)',
          overflow: 'hidden'
        }}>
          {url ? (
            <img 
              src={url} 
              alt={record.name} 
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} 
            />
          ) : (
            <PictureOutlined style={{ color: 'var(--ac-sub)' }} />
          )}
        </div>
      )
    },
    {
      title: 'Preset Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: WatermarkPreset) => (
        <div>
          <Text strong style={{ color: '#ffffff', fontSize: '14px' }}>{name}</Text>
          {record.is_default && (
            <Tag color="gold" style={{ marginLeft: '8px' }}>Default</Tag>
          )}
        </div>
      )
    },
    {
      title: 'Position',
      dataIndex: 'position',
      key: 'position',
      render: (pos: string) => (
        <Tag color="blue">{positionLabels[pos] || pos}</Tag>
      )
    },
    {
      title: 'Scale & Opacity',
      key: 'scale_opacity',
      render: (_: any, record: WatermarkPreset) => (
        <Space size="middle">
          <Text style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
            Size: <Text style={{ color: '#ffffff' }}>{record.scale_percent}%</Text>
          </Text>
          <Text style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
            Opacity: <Text style={{ color: '#ffffff' }}>{Math.round(record.opacity * 100)}%</Text>
          </Text>
          <Text style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
            Margin: <Text style={{ color: '#ffffff' }}>{record.margin}px</Text>
          </Text>
        </Space>
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_: any, record: WatermarkPreset) => (
        <Space>
          {!record.is_default && (
            <Button 
              size="small" 
              type="link" 
              onClick={() => handleSetDefault(record)}
              style={{ color: '#faad14' }}
            >
              Set Default
            </Button>
          )}
          <Popconfirm
            title="Delete this watermark preset?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ]

  // Calculate live preview positioning styles
  const getPreviewLogoStyle = (): React.CSSProperties => {
    const style: React.CSSProperties = {
      position: 'absolute',
      width: `${modalScale * 1.5}%`,
      opacity: modalOpacity / 100,
      pointerEvents: 'none',
      transition: 'all 0.2s ease'
    }

    if (modalPosition === 'bottom_right') {
      style.bottom = `${modalMargin / 3}px`
      style.right = `${modalMargin / 3}px`
    } else if (modalPosition === 'bottom_left') {
      style.bottom = `${modalMargin / 3}px`
      style.left = `${modalMargin / 3}px`
    } else if (modalPosition === 'top_right') {
      style.top = `${modalMargin / 3}px`
      style.right = `${modalMargin / 3}px`
    } else if (modalPosition === 'top_left') {
      style.top = `${modalMargin / 3}px`
      style.left = `${modalMargin / 3}px`
    }

    return style
  }

  return (
    <Card 
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Watermark & Campaign Presets</span>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleOpenModal}
            style={{
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              border: 'none',
              fontWeight: 600
            }}
          >
            New Preset
          </Button>
        </div>
      }
      className="settings-card"
    >
      <Paragraph style={{ color: 'var(--ac-sub)', marginBottom: '20px' }}>
        Create reusable brand watermarks and logos (e.g., "Brand X", "CoD RICOCHET"). Save once and select them with one click when creating clipping projects.
      </Paragraph>

      <Table 
        columns={columns} 
        dataSource={presets} 
        rowKey="id" 
        loading={loading}
        pagination={false}
        style={{ marginBottom: '20px' }}
      />

      {/* Create Preset Modal */}
      <Modal
        title="Create Watermark Preset"
        open={isModalOpen}
        onOk={handleCreatePreset}
        onCancel={() => setIsModalOpen(false)}
        okText="Save Preset"
        cancelText="Cancel"
        width={720}
      >
        <Row gutter={24}>
          <Col span={14}>
            <Form form={form} layout="vertical">
              <Form.Item
                label="Preset Name"
                name="name"
                rules={[{ required: true, message: 'Please enter preset name' }]}
              >
                <Input placeholder="e.g. My Brand Logo, CoD RICOCHET" />
              </Form.Item>

              <Form.Item
                label="Upload Logo (PNG with transparency recommended)"
                required
              >
                <Upload
                  beforeUpload={() => false}
                  maxCount={1}
                  accept=".png,.jpg,.jpeg,.webp,.svg"
                  onChange={handleFileChange}
                  showUploadList={false}
                >
                  <Button icon={<UploadOutlined />}>
                    {selectedFile ? selectedFile.name : 'Select Logo Image'}
                  </Button>
                </Upload>
              </Form.Item>

              <Form.Item label="Position">
                <Select 
                  value={modalPosition} 
                  onChange={(val) => setModalPosition(val)}
                >
                  <Option value="bottom_right">↘ Bottom-Right (Default)</Option>
                  <Option value="bottom_left">↙ Bottom-Left</Option>
                  <Option value="top_right">↗ Top-Right</Option>
                  <Option value="top_left">↖ Top-Left</Option>
                </Select>
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label={`Size: ${modalScale}% of width`}>
                    <Slider
                      min={5}
                      max={40}
                      value={modalScale}
                      onChange={(val) => setModalScale(val)}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label={`Opacity: ${modalOpacity}%`}>
                    <Slider
                      min={10}
                      max={100}
                      value={modalOpacity}
                      onChange={(val) => setModalOpacity(val)}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label={`Edge Margin: ${modalMargin}px`}>
                <Slider
                  min={0}
                  max={80}
                  value={modalMargin}
                  onChange={(val) => setModalMargin(val)}
                />
              </Form.Item>
            </Form>
          </Col>

          {/* Live Preview Column */}
          <Col span={10}>
            <Text strong style={{ display: 'block', marginBottom: '8px', color: 'var(--ac-sub)' }}>
              <EyeOutlined /> Live Video Frame Preview
            </Text>
            <div style={{
              width: '100%',
              height: '280px',
              background: 'linear-gradient(180deg, #1f2937 0%, #111827 100%)',
              borderRadius: '10px',
              position: 'relative',
              overflow: 'hidden',
              border: '2px dashed var(--ac-line)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {/* Fake video elements for preview context */}
              <div style={{
                position: 'absolute',
                top: '16px',
                textAlign: 'center',
                width: '80%',
                background: 'rgba(0,0,0,0.5)',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                color: '#fff',
                fontWeight: 600
              }}>
                🔥 TOP HOOK BANNER
              </div>

              <div style={{
                position: 'absolute',
                bottom: '16px',
                textAlign: 'center',
                width: '70%',
                background: 'rgba(0,0,0,0.6)',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#ffe600',
                fontWeight: 700
              }}>
                DYNAMIC CAPTION PREVIEW
              </div>

              {/* Watermark Logo Overlay in preview */}
              {previewUrl ? (
                <img 
                  src={previewUrl} 
                  alt="Watermark Preview" 
                  style={getPreviewLogoStyle()} 
                />
              ) : (
                <div style={{
                  ...getPreviewLogoStyle(),
                  background: 'rgba(79, 172, 254, 0.3)',
                  border: '1px solid #4facfe',
                  borderRadius: '4px',
                  padding: '6px',
                  textAlign: 'center',
                  fontSize: '10px',
                  color: '#fff'
                }}>
                  [LOGO]
                </div>
              )}
            </div>
            <Text style={{ fontSize: '11px', color: 'var(--ac-sub)', marginTop: '6px', display: 'block' }}>
              Shows real-time placement relative to captions & hooks.
            </Text>
          </Col>
        </Row>
      </Modal>
    </Card>
  )
}

export default WatermarkManager
