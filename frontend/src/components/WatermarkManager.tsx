import React, { useState, useEffect, useRef } from 'react'
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
  Slider, 
  Upload, 
  message, 
  Popconfirm,
  Row,
  Col,
  Radio,
  Switch,
  Divider
} from 'antd'
import { 
  PlusOutlined, 
  DeleteOutlined, 
  EditOutlined, 
  UploadOutlined, 
  PictureOutlined, 
  EyeOutlined, 
  DragOutlined, 
  AimOutlined, 
  MobileOutlined, 
  DesktopOutlined 
} from '@ant-design/icons'
import { watermarkApi, WatermarkPreset } from '../services/api'

const { Text, Paragraph } = Typography

// Standard 9-point grid anchors
const ANCHOR_POSITIONS: Record<string, { label: string; icon: string; short: string }> = {
  top_left: { label: 'Top-Left', icon: '↖', short: 'TL' },
  top_center: { label: 'Top-Center', icon: '⬆', short: 'TC' },
  top_right: { label: 'Top-Right', icon: '↗', short: 'TR' },
  center_left: { label: 'Center-Left', icon: '⬅', short: 'ML' },
  center: { label: 'Center', icon: '⏺', short: 'C' },
  center_right: { label: 'Center-Right', icon: '➡', short: 'MR' },
  bottom_left: { label: 'Bottom-Left', icon: '↙', short: 'BL' },
  bottom_center: { label: 'Bottom-Center', icon: '⬇', short: 'BC' },
  bottom_right: { label: 'Bottom-Right', icon: '↘', short: 'BR' },
}

export const WatermarkManager: React.FC = () => {
  const [presets, setPresets] = useState<WatermarkPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingPreset, setEditingPreset] = useState<WatermarkPreset | null>(null)
  const [form] = Form.useForm()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // Live preview & watermark controls
  const [modalPosition, setModalPosition] = useState<string>('bottom_right')
  const [modalScale, setModalScale] = useState<number>(15)
  const [modalOpacity, setModalOpacity] = useState<number>(85)
  const [modalMargin, setModalMargin] = useState<number>(24)

  // Interactive preview canvas state
  const previewRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [previewAspect, setPreviewAspect] = useState<'9_16' | '16_9'>('9_16')

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

  const handleOpenCreateModal = () => {
    setEditingPreset(null)
    form.resetFields()
    form.setFieldsValue({ is_default: false })
    setSelectedFile(null)
    setPreviewUrl(null)
    setModalPosition('bottom_right')
    setModalScale(15)
    setModalOpacity(85)
    setModalMargin(24)
    setIsModalOpen(true)
  }

  const handleOpenEditModal = (preset: WatermarkPreset) => {
    setEditingPreset(preset)
    form.resetFields()
    form.setFieldsValue({
      name: preset.name,
      is_default: preset.is_default
    })
    setSelectedFile(null)
    setPreviewUrl(preset.logo_url || null)
    setModalPosition(preset.position || 'bottom_right')
    setModalScale(preset.scale_percent || 15)
    setModalOpacity(Math.round((preset.opacity ?? 0.85) * 100))
    setModalMargin(preset.margin ?? 24)
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

  const parseCustomCoords = (pos: string): { x: number; y: number } | null => {
    if (pos.startsWith('custom:') || pos.startsWith('custom_')) {
      const parts = pos.replace(':', '_').split('_')
      if (parts.length >= 3) {
        const x = Math.max(0, Math.min(100, parseFloat(parts[1]) || 0))
        const y = Math.max(0, Math.min(100, parseFloat(parts[2]) || 0))
        return { x: Math.round(x), y: Math.round(y) }
      }
    }
    return null
  }

  // Pointer dragging logic on the interactive preview frame
  const updateCoordsFromPointer = (clientX: number, clientY: number) => {
    if (!previewRef.current) return
    const rect = previewRef.current.getBoundingClientRect()
    const relX = clientX - rect.left
    const relY = clientY - rect.top
    const pctX = Math.round(Math.max(0, Math.min(100, (relX / rect.width) * 100)))
    const pctY = Math.round(Math.max(0, Math.min(100, (relY / rect.height) * 100)))
    setModalPosition(`custom:${pctX}:${pctY}`)
  }

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    } catch (_) {}
    updateCoordsFromPointer(e.clientX, e.clientY)
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return
    updateCoordsFromPointer(e.clientX, e.clientY)
  }

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDragging) {
      setIsDragging(false)
      try {
        (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
      } catch (_) {}
    }
  }

  const handleSavePreset = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      if (editingPreset) {
        // Update existing preset attributes
        await watermarkApi.updatePreset(editingPreset.id, {
          name: values.name,
          position: modalPosition,
          scale_percent: modalScale,
          opacity: modalOpacity / 100,
          margin: modalMargin,
          is_default: Boolean(values.is_default)
        })

        // If a new image was chosen, upload replacement
        if (selectedFile) {
          const formData = new FormData()
          formData.append('logo_file', selectedFile)
          await watermarkApi.uploadLogo(editingPreset.id, formData)
        }

        message.success(`Preset "${values.name}" updated successfully!`)
        setIsModalOpen(false)
        loadPresets()
      } else {
        // Creating a new preset
        if (!selectedFile) {
          message.error('Please upload a logo image (PNG/JPG/SVG)')
          setSubmitting(false)
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
      }
    } catch (err: any) {
      console.error('Failed to save watermark preset:', err)
      message.error(err.response?.data?.detail || 'Failed to save watermark preset')
    } finally {
      setSubmitting(false)
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

  const formatPositionLabel = (pos: string) => {
    if (ANCHOR_POSITIONS[pos]) {
      return `${ANCHOR_POSITIONS[pos].icon} ${ANCHOR_POSITIONS[pos].label}`
    }
    const custom = parseCustomCoords(pos)
    if (custom) {
      return `🎯 Drag (${custom.x}%, ${custom.y}%)`
    }
    return pos
  }

  // Calculate live preview logo CSS style
  const getPreviewLogoStyle = (): React.CSSProperties => {
    const customCoords = parseCustomCoords(modalPosition)
    
    const baseStyle: React.CSSProperties = {
      position: 'absolute',
      width: `${Math.max(10, modalScale * 1.6)}%`,
      maxWidth: '85%',
      opacity: modalOpacity / 100,
      cursor: isDragging ? 'grabbing' : 'grab',
      userSelect: 'none',
      zIndex: 10,
      transition: isDragging ? 'none' : 'all 0.15s ease-out'
    }

    if (customCoords) {
      return {
        ...baseStyle,
        left: `${customCoords.x}%`,
        top: `${customCoords.y}%`,
        transform: `translate(-${customCoords.x}%, -${customCoords.y}%)`
      }
    }

    const m = Math.round(modalMargin / 3)
    switch (modalPosition) {
      case 'top_left':
        return { ...baseStyle, top: `${m}px`, left: `${m}px` }
      case 'top_center':
        return { ...baseStyle, top: `${m}px`, left: '50%', transform: 'translateX(-50%)' }
      case 'top_right':
        return { ...baseStyle, top: `${m}px`, right: `${m}px` }
      case 'center_left':
        return { ...baseStyle, top: '50%', left: `${m}px`, transform: 'translateY(-50%)' }
      case 'center':
        return { ...baseStyle, top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
      case 'center_right':
        return { ...baseStyle, top: '50%', right: `${m}px`, transform: 'translateY(-50%)' }
      case 'bottom_left':
        return { ...baseStyle, bottom: `${m}px`, left: `${m}px` }
      case 'bottom_center':
        return { ...baseStyle, bottom: `${m}px`, left: '50%', transform: 'translateX(-50%)' }
      case 'bottom_right':
      default:
        return { ...baseStyle, bottom: `${m}px`, right: `${m}px` }
    }
  }

  const customCoords = parseCustomCoords(modalPosition)

  const columns = [
    {
      title: 'Logo',
      dataIndex: 'logo_url',
      key: 'logo_url',
      width: 90,
      render: (url: string, record: WatermarkPreset) => (
        <div style={{
          width: '64px',
          height: '42px',
          background: 'rgba(0, 0, 0, 0.4)',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid var(--ac-line)',
          overflow: 'hidden',
          padding: '2px'
        }}>
          {url ? (
            <img 
              src={url} 
              alt={record.name} 
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} 
            />
          ) : (
            <PictureOutlined style={{ color: 'var(--ac-sub)', fontSize: '18px' }} />
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
            <Tag color="gold" style={{ marginLeft: '8px', fontWeight: 600 }}>Default</Tag>
          )}
        </div>
      )
    },
    {
      title: 'Position',
      dataIndex: 'position',
      key: 'position',
      render: (pos: string) => {
        const isCustom = pos.startsWith('custom:') || pos.startsWith('custom_')
        return (
          <Tag color={isCustom ? 'cyan' : 'blue'} style={{ fontSize: '12px', padding: '2px 8px' }}>
            {formatPositionLabel(pos)}
          </Tag>
        )
      }
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
      width: 220,
      render: (_: any, record: WatermarkPreset) => (
        <Space size="small">
          <Button 
            size="small" 
            type="primary"
            ghost
            icon={<EditOutlined />}
            onClick={() => handleOpenEditModal(record)}
          >
            Edit
          </Button>

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

  return (
    <Card 
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Watermark & Campaign Presets</span>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleOpenCreateModal}
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
        Create reusable brand watermarks and logos (e.g. Brand X, Channel Badges, Esports Logos). Watermarks can be freely dragged anywhere on the video frame or snapped to 9 anchor points.
      </Paragraph>

      <Table 
        columns={columns} 
        dataSource={presets} 
        rowKey="id" 
        loading={loading}
        pagination={false}
        style={{ marginBottom: '20px' }}
      />

      {/* Create / Edit Preset Modal */}
      <Modal
        title={editingPreset ? `Edit Watermark: ${editingPreset.name}` : "Create Watermark Preset"}
        open={isModalOpen}
        onOk={handleSavePreset}
        onCancel={() => setIsModalOpen(false)}
        okText={editingPreset ? "Update Preset" : "Save Preset"}
        confirmLoading={submitting}
        cancelText="Cancel"
        width={860}
      >
        <Row gutter={24}>
          {/* Controls Column */}
          <Col span={13}>
            <Form form={form} layout="vertical">
              <Form.Item
                label="Preset Name"
                name="name"
                rules={[{ required: true, message: 'Please enter preset name' }]}
              >
                <Input placeholder="e.g. My Brand Logo, Channel Badge" />
              </Form.Item>

              <Form.Item
                label={editingPreset ? "Replace Logo Image (Optional)" : "Upload Logo (PNG with transparency recommended)"}
                required={!editingPreset}
              >
                <Space direction="horizontal" align="center" style={{ width: '100%' }}>
                  <Upload
                    beforeUpload={() => false}
                    maxCount={1}
                    accept=".png,.jpg,.jpeg,.webp,.svg"
                    onChange={handleFileChange}
                    showUploadList={false}
                  >
                    <Button icon={<UploadOutlined />}>
                      {selectedFile ? selectedFile.name : (editingPreset ? 'Choose New Logo Image' : 'Select Logo Image')}
                    </Button>
                  </Upload>
                  {previewUrl && (
                    <Text style={{ fontSize: '12px', color: 'var(--ac-sub)' }}>
                      Preview updated
                    </Text>
                  )}
                </Space>
              </Form.Item>

              <Divider style={{ margin: '12px 0', borderColor: 'var(--ac-line)' }} />

              {/* Position Snap Grid */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <Text strong style={{ color: '#fff', fontSize: '13px' }}>
                    <AimOutlined /> Placement Anchor & Snap Grid
                  </Text>
                  <Tag color={customCoords ? 'cyan' : 'blue'}>
                    {formatPositionLabel(modalPosition)}
                  </Tag>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', maxWidth: '270px' }}>
                  {Object.entries(ANCHOR_POSITIONS).map(([posKey, posInfo]) => {
                    const isActive = modalPosition === posKey
                    return (
                      <Button
                        key={posKey}
                        size="small"
                        type={isActive ? 'primary' : 'default'}
                        onClick={() => setModalPosition(posKey)}
                        style={{
                          fontSize: '11px',
                          fontWeight: isActive ? 600 : 400,
                          background: isActive ? '#1890ff' : 'rgba(255, 255, 255, 0.05)',
                          borderColor: isActive ? '#40a9ff' : 'var(--ac-line)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '4px',
                          padding: '3px 6px'
                        }}
                      >
                        <span style={{ fontSize: '13px' }}>{posInfo.icon}</span>
                        <span>{posInfo.short}</span>
                      </Button>
                    )
                  })}
                </div>

                {customCoords && (
                  <div style={{ 
                    marginTop: '10px', 
                    padding: '8px 12px', 
                    background: 'rgba(0, 242, 254, 0.06)', 
                    borderRadius: '6px', 
                    border: '1px dashed #00f2fe60' 
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <Text style={{ fontSize: '12px', color: '#00f2fe' }}>
                        🎯 Interactive Canvas Position:
                      </Text>
                      <Button 
                        size="small" 
                        type="link" 
                        onClick={() => setModalPosition('bottom_right')}
                        style={{ padding: 0, fontSize: '11px', color: 'var(--ac-sub)' }}
                      >
                        Reset to Corner
                      </Button>
                    </div>
                    <Row gutter={12}>
                      <Col span={12}>
                        <div style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>Horizontal (X): {customCoords.x}%</div>
                        <Slider 
                          min={0} 
                          max={100} 
                          value={customCoords.x} 
                          onChange={(val) => setModalPosition(`custom:${val}:${customCoords.y}`)} 
                        />
                      </Col>
                      <Col span={12}>
                        <div style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>Vertical (Y): {customCoords.y}%</div>
                        <Slider 
                          min={0} 
                          max={100} 
                          value={customCoords.y} 
                          onChange={(val) => setModalPosition(`custom:${customCoords.x}:${val}`)} 
                        />
                      </Col>
                    </Row>
                  </div>
                )}
              </div>

              {/* Size, Opacity, Margin Sliders */}
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label={`Scale: ${modalScale}% of width`} style={{ marginBottom: '12px' }}>
                    <Slider
                      min={5}
                      max={45}
                      value={modalScale}
                      onChange={(val) => setModalScale(val)}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label={`Opacity: ${modalOpacity}%`} style={{ marginBottom: '12px' }}>
                    <Slider
                      min={10}
                      max={100}
                      value={modalOpacity}
                      onChange={(val) => setModalOpacity(val)}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item 
                label={`Edge Margin: ${modalMargin}px (for grid anchors)`}
                style={{ marginBottom: '12px' }}
              >
                <Slider
                  min={0}
                  max={80}
                  value={modalMargin}
                  onChange={(val) => setModalMargin(val)}
                />
              </Form.Item>

              <Form.Item name="is_default" valuePropName="checked" style={{ marginBottom: 0 }}>
                <Space>
                  <Switch checked={form.getFieldValue('is_default')} onChange={(checked) => form.setFieldsValue({ is_default: checked })} />
                  <Text style={{ color: '#fff', fontSize: '13px' }}>Set as default watermark for new projects</Text>
                </Space>
              </Form.Item>
            </Form>
          </Col>

          {/* Interactive Preview Canvas Column */}
          <Col span={11}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <Text strong style={{ color: 'var(--ac-sub)', fontSize: '13px' }}>
                <EyeOutlined /> Interactive Live Canvas
              </Text>

              {/* Aspect Ratio Switch */}
              <Radio.Group 
                size="small" 
                value={previewAspect} 
                onChange={(e) => setPreviewAspect(e.target.value)}
              >
                <Radio.Button value="9_16">
                  <MobileOutlined /> 9:16
                </Radio.Button>
                <Radio.Button value="16_9">
                  <DesktopOutlined /> 16:9
                </Radio.Button>
              </Radio.Group>
            </div>

            {/* Canvas Outer Wrapper */}
            <div style={{
              width: '100%',
              height: '350px',
              background: '#0a0d14',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '12px',
              border: '1px solid var(--ac-line)'
            }}>
              {/* Interactive Video Frame */}
              <div 
                ref={previewRef}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                style={{
                  width: previewAspect === '9_16' ? '180px' : '100%',
                  height: previewAspect === '9_16' ? '320px' : '180px',
                  background: 'linear-gradient(180deg, #182234 0%, #0d131f 100%)',
                  borderRadius: '8px',
                  position: 'relative',
                  overflow: 'hidden',
                  border: isDragging ? '2px solid #00f2fe' : '2px dashed rgba(255, 255, 255, 0.25)',
                  boxShadow: isDragging ? '0 0 16px rgba(0, 242, 254, 0.3)' : '0 4px 12px rgba(0, 0, 0, 0.5)',
                  cursor: isDragging ? 'grabbing' : 'crosshair',
                  touchAction: 'none'
                }}
              >
                {/* Visual Video Elements for Context */}
                <div style={{
                  position: 'absolute',
                  top: '12px',
                  left: '10%',
                  width: '80%',
                  background: 'rgba(0, 0, 0, 0.55)',
                  padding: '3px 6px',
                  borderRadius: '4px',
                  fontSize: '9px',
                  color: '#fff',
                  fontWeight: 600,
                  textAlign: 'center',
                  pointerEvents: 'none',
                  border: '1px solid rgba(255,255,255,0.1)'
                }}>
                  🔥 HOOK BANNER
                </div>

                <div style={{
                  position: 'absolute',
                  bottom: '12px',
                  left: '12%',
                  width: '76%',
                  background: 'rgba(0, 0, 0, 0.65)',
                  padding: '3px 6px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  color: '#ffe600',
                  fontWeight: 700,
                  textAlign: 'center',
                  pointerEvents: 'none',
                  border: '1px solid rgba(255,230,0,0.2)'
                }}>
                  SUBTITLE CAPTION
                </div>

                {/* Snap alignment crosshair when dragging */}
                {isDragging && (
                  <>
                    <div style={{
                      position: 'absolute',
                      top: '50%',
                      left: 0,
                      right: 0,
                      borderTop: '1px dashed rgba(0, 242, 254, 0.4)',
                      pointerEvents: 'none'
                    }} />
                    <div style={{
                      position: 'absolute',
                      left: '50%',
                      top: 0,
                      bottom: 0,
                      borderLeft: '1px dashed rgba(0, 242, 254, 0.4)',
                      pointerEvents: 'none'
                    }} />
                  </>
                )}

                {/* Draggable Watermark Logo */}
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
                    border: '1px dashed #4facfe',
                    borderRadius: '4px',
                    padding: '4px',
                    textAlign: 'center',
                    fontSize: '9px',
                    color: '#fff',
                    fontWeight: 600
                  }}>
                    [LOGO]
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
              <DragOutlined style={{ color: '#00f2fe' }} />
              <Text style={{ fontSize: '11px', color: 'var(--ac-sub)' }}>
                Drag the logo or click anywhere on the canvas to place freely.
              </Text>
            </div>
          </Col>
        </Row>
      </Modal>
    </Card>
  )
}

export default WatermarkManager
