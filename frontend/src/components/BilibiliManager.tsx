import React, { useState, useEffect } from 'react'
import { Button, Modal, Form, Input, Table, Tag, Space, message, Popconfirm, Tabs, Alert, Typography, Select, Row, Col, Tooltip, Progress, Descriptions, Statistic, Card } from 'antd'
import { PlusOutlined, DeleteOutlined, UserOutlined, CheckCircleOutlined, CloseCircleOutlined, UploadOutlined, QuestionCircleOutlined, ReloadOutlined, EyeOutlined, RedoOutlined, StopOutlined, ExclamationCircleOutlined, ClockCircleOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { uploadApi, BilibiliAccount, BILIBILI_PARTITIONS, UploadRecord } from '../services/uploadApi'
import './BilibiliManager.css'

const { TextArea } = Input
const { Text } = Typography
const { Option } = Select
const { TabPane } = Tabs

interface BilibiliManagerProps {
  visible: boolean
  onClose: () => void
  projectId?: string
  clipIds?: string[]
  clipTitles?: string[]
  onUploadSuccess?: () => void
}

const BilibiliManager: React.FC<BilibiliManagerProps> = ({
  visible,
  onClose,
  clipIds = [],
  clipTitles = []
}) => {
  const [activeTab, setActiveTab] = useState('upload')
  const [accounts, setAccounts] = useState<BilibiliAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [cookieForm] = Form.useForm()
  const [uploadForm] = Form.useForm()
  
  // Posting status-related states
  const [uploadRecords, setUploadRecords] = useState<UploadRecord[]>([])
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<UploadRecord | null>(null)
  const [detailModalVisible, setDetailModalVisible] = useState(false)

  // Get account list
  const fetchAccounts = async () => {
    try {
      setLoading(true)
      const data = await uploadApi.getAccounts()
      setAccounts(data)
    } catch (error: any) {
      message.error('Failed to get account list: ' + (error.message || 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // Get post history
  const fetchUploadRecords = async () => {
    try {
      setRecordsLoading(true)
      const data = await uploadApi.getUploadRecords()
      setUploadRecords(data)
    } catch (error: any) {
      message.error('Failed to retrieve posting record: ' + (error.message || 'Unknown error'))
    } finally {
      setRecordsLoading(false)
    }
  }

  // Retrying posting
  const handleRetry = async (recordId: string | number) => {
    try {
      await uploadApi.retryUpload(recordId)
      message.success('Retry task submitted')
      fetchUploadRecords()
    } catch (error: any) {
      message.error('Retrying failed uploads: ' + (error.message || 'Unknown error'))
    }
  }

  // Cancel posting
  const handleCancel = async (recordId: string | number) => {
    try {
      await uploadApi.cancelUpload(recordId)
      message.success('Task canceled')
      fetchUploadRecords()
    } catch (error: any) {
      message.error('Failed to cancel: ' + (error.message || 'Unknown error'))
    }
  }

  // Delete submission
  const handleDelete = async (recordId: string | number) => {
    try {
      await uploadApi.deleteUpload(recordId)
      message.success('Task deleted')
      fetchUploadRecords()
    } catch (error: any) {
      message.error('Deletion failed: ' + (error.message || 'Unknown error'))
    }
  }

  // View details
  const handleViewDetail = (record: UploadRecord) => {
    setSelectedRecord(record)
    setDetailModalVisible(true)
  }

  useEffect(() => {
    if (visible) {
      fetchAccounts()
      fetchUploadRecords()
      // If there are slice data, the upload tab will be displayed by default
      if (clipIds.length > 0) {
        setActiveTab('upload')
      } else {
        setActiveTab('accounts')
      }
    }
  }, [visible, clipIds])

  // CookieImport login
  const handleCookieLogin = async (values: any) => {
    try {
      setLoading(true)
      
      // ParseCookieString
      const cookieStr = values.cookies.trim()
      const cookies: Record<string, string> = {}
      
      cookieStr.split(';').forEach((cookie: string) => {
        const trimmedCookie = cookie.trim()
        const equalIndex = trimmedCookie.indexOf('=')
        if (equalIndex > 0) {
          const key = trimmedCookie.substring(0, equalIndex).trim()
          const value = trimmedCookie.substring(equalIndex + 1).trim()
          if (key && value) {
            cookies[key] = value
          }
        }
      })
      
      if (Object.keys(cookies).length === 0) {
        message.error('CookieIncorrect format, please check input')
        return
      }
      
      await uploadApi.cookieLogin(cookies, values.nickname)
      message.success('Account added successfully! ')
      setShowAddAccount(false)
      cookieForm.resetFields()
      fetchAccounts()
    } catch (error: any) {
      message.error('Failed to add account: ' + (error.message || 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // Delete account
  const handleDeleteAccount = async (accountId: string) => {
    try {
      await uploadApi.deleteAccount(accountId)
      message.success('Account deleted successfully')
      fetchAccounts()
    } catch (error: any) {
      message.error('Failed to delete account: ' + (error.message || 'Unknown error'))
    }
  }

  // Submit upload
  const handleUpload = async (_values: any) => {
    // Show under development notice
    message.info('BThe site upload feature is under development, please stay tuned! ', 3)
    /*
    if (!projectId || clipIds.length === 0) {
      message.error('No slices selected for upload')
      return
    }

    try {
      setLoading(true)
      
      const uploadData = {
        account_id: values.account_id,
        clip_ids: clipIds,
        title: values.title,
        description: values.description || '',
        tags: values.tags ? values.tags.split(',').map((tag: string) => tag.trim()) : [],
        partition_id: values.partition_id
      }

      // Call uploadAPI
      const response = await fetch(`/api/v1/upload/projects/${projectId}/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(uploadData)
      })

      if (response.ok) {
        message.success('Posting task created, processing in background...')
        onUploadSuccess?.()
        onClose()
      } else {
        const error = await response.json()
        message.error('Posting failed: ' + (error.detail || 'Unknown error'))
      }
    } catch (error: any) {
      message.error('Posting failed: ' + (error.message || 'Unknown error'))
    } finally {
      setLoading(false)
    }
    */
  }

  // Get status label
  const getStatusTag = (status: string) => {
    const statusConfig = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: 'Waiting' },
      processing: { color: 'processing', icon: <PlayCircleOutlined />, text: 'In progress' },
      success: { color: 'success', icon: <CheckCircleOutlined />, text: 'Success' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: 'Done / Completed' },
      failed: { color: 'error', icon: <ExclamationCircleOutlined />, text: 'Failed' },
      cancelled: { color: 'default', icon: <StopOutlined />, text: 'Cancelled' }
    }
    
    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    )
  }

  // Get section name
  const getPartitionName = (partitionId: number) => {
    const partition = BILIBILI_PARTITIONS.find(p => p.id === partitionId)
    return partition ? partition.name : `Partition${partitionId}`
  }

  // Format file size
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-'
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
  }

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    
    if (hours > 0) {
      return `${hours}hours${minutes}Minutes`
    } else if (minutes > 0) {
      return `${minutes}Minutes${secs}Seconds`
    } else {
      return `${secs}Seconds`
    }
  }

  // Get statistics
  const getStatistics = () => {
    const safeRecords = Array.isArray(uploadRecords) ? uploadRecords : []
    const total = safeRecords.length
    const success = safeRecords.filter(r => r.status === 'success' || r.status === 'completed').length
    const failed = safeRecords.filter(r => r.status === 'failed').length
    const processing = safeRecords.filter(r => r.status === 'processing').length
    const pending = safeRecords.filter(r => r.status === 'pending').length
    
    return { total, success, failed, processing, pending }
  }

  // CookieGet guide content
  const cookieGuideContent = (
    <div style={{ maxWidth: 300 }}>
      <div style={{ marginBottom: 8, fontWeight: 'bold' }}>CookieGet steps: </div>
      <ol style={{ margin: 0, paddingLeft: 16 }}>
        <li>OpenBLog in and site website</li>
        <li>ByF12Open developer tools</li>
        <li>ClickNetworkTab page</li>
        <li>Refresh page</li>
        <li>Find any request, click to view</li>
        <li>InRequest HeadersFound inCookieField</li>
        <li>CopyCookieThe value (excluding"Cookie: "Prefix)</li>
      </ol>
    </div>
  )

  // Account management table columns
  const accountColumns = [
    {
      title: 'Display name',
      dataIndex: 'nickname',
      key: 'nickname',
      render: (nickname: string, record: BilibiliAccount) => (
        <Space>
          <UserOutlined />
          <span>{nickname || record.username}</span>
        </Space>
      ),
    },
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'} icon={status === 'active' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
          {status === 'active' ? 'Active' : 'Abnormal'}
        </Tag>
      ),
    },
    {
      title: 'Operation',
      key: 'action',
      render: (_: any, record: BilibiliAccount) => (
        <Popconfirm
          title="Are you sure you want to delete this account?? "
          description="After deletion, it cannot be restored, please operate prudently. "
          onConfirm={() => handleDeleteAccount(record.id)}
          okText="Confirm"
          cancelText="Cancel"
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small">
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ]

  // Posting status table columns
  const uploadStatusColumns = [
    {
      title: 'TaskID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      render: (id: string | number) => <Text code>{id}</Text>
    },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string) => (
        <Tooltip title={title}>
          <Text>{title}</Text>
        </Tooltip>
      )
    },
    {
      title: 'Posting account',
      dataIndex: 'account_nickname',
      key: 'account_nickname',
      width: 120,
      render: (nickname: string, record: UploadRecord) => (
        <div>
          <div>{nickname || record.account_username}</div>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {record.account_username}
          </Text>
        </div>
      )
    },
    {
      title: 'Partition',
      dataIndex: 'partition_id',
      key: 'partition_id',
      width: 100,
      render: (partitionId: number) => (
        <Tag>{getPartitionName(partitionId)}</Tag>
      )
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status)
    },
    {
      title: 'Progress',
      dataIndex: 'progress',
      key: 'progress',
      width: 120,
      render: (progress: number, record: UploadRecord) => {
        if (record.status === 'success' || record.status === 'completed') {
          return <Progress percent={100} size="small" status="success" />
        } else if (record.status === 'failed') {
          return <Progress percent={progress} size="small" status="exception" />
        } else if (record.status === 'processing') {
          return <Progress percent={progress} size="small" status="active" />
        } else {
          return <Progress percent={progress} size="small" />
        }
      }
    },
    {
      title: 'File size',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (fileSize: number) => <span>{formatFileSize(fileSize)}</span>
    },
    {
      title: 'Creation time',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (date: string) => <span>{new Date(date).toLocaleString()}</span>
    },
    {
      title: 'Operation',
      key: 'actions',
      width: 200,
      render: (_: any, record: UploadRecord) => (
        <Space size="small">
          <Button 
            type="link" 
            icon={<EyeOutlined />} 
            onClick={() => handleViewDetail(record)}
            size="small"
          >
            Details
          </Button>
          {record.status === 'failed' && (
            <Popconfirm
              title="Are you sure you want to retry this posting task?? "
              onConfirm={() => handleRetry(record.id)}
              okText="Confirm"
              cancelText="Cancel"
            >
              <Button 
                type="link" 
                icon={<RedoOutlined />} 
                size="small"
              >
                Retry
              </Button>
            </Popconfirm>
          )}
          {(record.status === 'pending' || record.status === 'processing') && (
            <Popconfirm
              title="Are you sure you want to cancel this posting task?? "
              onConfirm={() => handleCancel(record.id)}
              okText="Confirm"
              cancelText="Cancel"
            >
              <Button 
                type="link" 
                icon={<StopOutlined />} 
                danger
                size="small"
              >
                Cancel
              </Button>
            </Popconfirm>
          )}
          {(record.status === 'success' || record.status === 'completed' || record.status === 'failed' || record.status === 'cancelled') && (
            <Popconfirm
              title="Are you sure you want to delete this posting task? This cannot be undone. "
              onConfirm={() => handleDelete(record.id)}
              okText="Confirm"
              cancelText="Cancel"
            >
              <Button 
                type="link" 
                icon={<DeleteOutlined />} 
                danger
                size="small"
              >
                Delete
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
    }
  ]

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnClose
      className="bilibili-manager-modal"
    >
      {/* Custom title bar */}
      <div className="bilibili-manager-header">
        <div className="bilibili-manager-header-icon">
          <UploadOutlined />
        </div>
        <div className="bilibili-manager-header-content">
          <h2 className="bilibili-manager-header-title">BSite management</h2>
          <p className="bilibili-manager-header-subtitle">
            {clipIds.length > 0 
              ? `Prepare for upload ${clipIds.length} From slice toBSite` 
              : 'Manage yourBSite account and posting settings'
            }
          </p>
        </div>
      </div>

      <div className="bilibili-manager-tabs">
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
        {/* Upload labels tab */}
        {clipIds.length > 0 && (
          <TabPane 
            tab={
              <span>
                <UploadOutlined />
                Post upload
              </span>
            } 
            key="upload"
          >
            <div className="bilibili-manager-content">
              <Alert
                message="Submission information"
                description={`Prepare for upload ${clipIds.length} From slice toBSite`}
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />

              <Form
              form={uploadForm}
              onFinish={handleUpload}
              layout="vertical"
              initialValues={{
                title: clipTitles.length === 1 ? clipTitles[0] : `${clipTitles[0]} Equals${clipIds.length}videos`,
                partition_id: 4 // Default game region
              }}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="Select account"
                    name="account_id"
                    rules={[{ required: true, message: 'SelectBSite account' }]}
                  >
                    <Select 
                      placeholder="Choose which account to useBSite account"
                      notFoundContent={
                        <div style={{ textAlign: 'center', padding: '20px' }}>
                          <p>No available accounts found</p>
                          <Button 
                            type="link" 
                            icon={<PlusOutlined />}
                            onClick={() => setShowAddAccount(true)}
                          >
                            Add account
                          </Button>
                        </div>
                      }
                    >
                      {(accounts || []).filter(acc => acc.status === 'active').map(account => (
                        <Option key={account.id} value={account.id}>
                          {account.nickname || account.username}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="Video partition"
                    name="partition_id"
                    rules={[{ required: true, message: 'Please select video partition' }]}
                  >
                    <Select placeholder="Select video partition" showSearch>
                      {BILIBILI_PARTITIONS.map(partition => (
                        <Option key={partition.id} value={partition.id}>
                          {partition.name}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                label="Title"
                name="title"
                rules={[{ required: true, message: 'Please enter video title' }]}
              >
                <Input placeholder="Input video title" maxLength={80} showCount />
              </Form.Item>

              <Form.Item
                label="Description"
                name="description"
              >
                <TextArea
                  placeholder="Input video description (optional))"
                  rows={3}
                  maxLength={2000}
                  showCount
                />
              </Form.Item>

              <Form.Item
                label="Tag"
                name="tags"
              >
                <Input placeholder="Enter tags, separated by commas (optional))" />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button 
                    type="primary" 
                    onClick={() => message.info('Under development, stay tuned', 3)}
                    icon={<UploadOutlined />}
                  >
                    Starting to post
                  </Button>
                  <Button onClick={onClose}>
                    Cancel
                  </Button>
                </Space>
              </Form.Item>
              </Form>
            </div>
          </TabPane>
        )}

        {/* Account management tab page */}
        <TabPane 
          tab={
            <span>
              <UserOutlined />
              Account management
            </span>
          } 
          key="accounts"
        >
          <div className="bilibili-manager-content">
            <div style={{ marginBottom: 16 }}>
              <Button 
                type="primary" 
                icon={<PlusOutlined />} 
                onClick={() => setShowAddAccount(true)}
              >
                Add account
              </Button>
            </div>

            <Table
              columns={accountColumns}
              dataSource={accounts}
              rowKey="id"
              loading={loading}
              pagination={false}
              size="small"
            />
          </div>
        </TabPane>

        {/* Posting status tab page */}
        <TabPane 
          tab={
            <span>
              <ReloadOutlined />
              Submission status
            </span>
          } 
          key="status"
        >
          <div className="bilibili-manager-content">
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, color: '#ffffff' }}>Post task status</h3>
              <Button 
                type="primary" 
                icon={<ReloadOutlined />} 
                onClick={fetchUploadRecords}
                loading={recordsLoading}
              >
                Refresh
              </Button>
            </div>

            {/* Statistics information */}
            {(() => {
              const stats = getStatistics()
              return (
                <Row gutter={16} style={{ marginBottom: 24 }}>
                  <Col span={6}>
                    <Card style={{ background: '#262626', border: '1px solid #404040' }}>
                      <Statistic 
                        title={<span style={{ color: '#ffffff' }}>Total tasks</span>} 
                        value={stats.total} 
                        valueStyle={{ color: '#ffffff' }} 
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card style={{ background: '#262626', border: '1px solid #404040' }}>
                      <Statistic 
                        title={<span style={{ color: '#ffffff' }}>Success</span>} 
                        value={stats.success} 
                        valueStyle={{ color: '#52c41a' }}
                        prefix={<CheckCircleOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card style={{ background: '#262626', border: '1px solid #404040' }}>
                      <Statistic 
                        title={<span style={{ color: '#ffffff' }}>Failed</span>} 
                        value={stats.failed} 
                        valueStyle={{ color: '#ff4d4f' }}
                        prefix={<ExclamationCircleOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card style={{ background: '#262626', border: '1px solid #404040' }}>
                      <Statistic 
                        title={<span style={{ color: '#ffffff' }}>In progress</span>} 
                        value={stats.processing + stats.pending} 
                        valueStyle={{ color: '#1890ff' }}
                        prefix={<PlayCircleOutlined />}
                      />
                    </Card>
                  </Col>
                </Row>
              )
            })()}

            {/* Task list */}
            <Table
              columns={uploadStatusColumns}
              dataSource={uploadRecords}
              rowKey="id"
              loading={recordsLoading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total, range) => `First ${range[0]}-${range[1]} entries, total of ${total} Rows`
              }}
              scroll={{ x: 1200 }}
              size="small"
            />
          </div>
        </TabPane>
      </Tabs>
      </div>

      {/* Add account modal */}
      <Modal
        title="AddBSite account"
        open={showAddAccount}
        onCancel={() => {
          setShowAddAccount(false)
          cookieForm.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Alert
          message="We recommendCookieImport"
          description="CookieImport is the safest and most stable login method and will not triggerBSite risk control. "
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Form form={cookieForm} onFinish={handleCookieLogin} layout="vertical">
          <Form.Item
            name="nickname"
            label="Account nickname"
            rules={[{ required: true, message: 'Please enter account nickname' }]}
          >
            <Input placeholder="Enter account nickname for identification" />
          </Form.Item>
          
          <Form.Item
            name="cookies"
            label={
              <Space>
                <span>Cookie</span>
                <Tooltip title={cookieGuideContent} placement="topLeft">
                  <Button 
                    type="link" 
                    size="small" 
                    icon={<QuestionCircleOutlined />}
                  >
                    Getting started guide
                  </Button>
                </Tooltip>
              </Space>
            }
            rules={[
              { required: true, message: 'Please enterCookie' },
              { min: 10, message: 'CookieLength cannot be less than10characters' }
            ]}
          >
            <TextArea
              rows={4}
              placeholder="Please copy from browser developer toolsCookie, Format is: SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
            />
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                Add account
              </Button>
              <Button onClick={() => setShowAddAccount(false)}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Posting status details modal */}
      <Modal
        title="Post task details"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={800}
        className="bilibili-manager-modal"
      >
        {selectedRecord && (
          <div>
            <Descriptions 
              column={2} 
              bordered
              labelStyle={{ 
                background: '#1f1f1f', 
                color: '#ffffff',
                fontWeight: 'bold',
                borderRight: '1px solid #303030'
              }}
              contentStyle={{ 
                background: '#262626', 
                color: '#ffffff',
                borderLeft: '1px solid #303030'
              }}
              style={{ 
                background: '#262626',
                border: '1px solid #303030'
              }}
            >
              <Descriptions.Item label="TaskID" span={1}>
                <Text code>{selectedRecord.id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Status" span={1}>
                {getStatusTag(selectedRecord.status)}
              </Descriptions.Item>
              <Descriptions.Item label="Title" span={2}>
                <Text>{selectedRecord.title}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Posting account" span={1}>
                <Text>{selectedRecord.account_nickname || selectedRecord.account_username}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Partition" span={1}>
                <Tag>{getPartitionName(selectedRecord.partition_id)}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Project name" span={1}>
                <Text>{selectedRecord.project_name || '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="SliceID" span={1}>
                <Text code>{selectedRecord.clip_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Progress" span={2}>
                <Progress 
                  percent={selectedRecord.progress} 
                  status={
                    selectedRecord.status === 'failed' ? 'exception' :
                    selectedRecord.status === 'success' || selectedRecord.status === 'completed' ? 'success' :
                    selectedRecord.status === 'processing' ? 'active' : 'normal'
                  }
                />
              </Descriptions.Item>
              <Descriptions.Item label="File size" span={1}>
                <Text>{formatFileSize(selectedRecord.file_size)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Uploading duration" span={1}>
                <Text>{formatDuration(selectedRecord.upload_duration)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="BVNumber" span={1}>
                {selectedRecord.bv_id ? <Text code>{selectedRecord.bv_id}</Text> : <Text>-</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="AVNumber" span={1}>
                {selectedRecord.av_id ? <Text code>{selectedRecord.av_id}</Text> : <Text>-</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="Creation time" span={1}>
                <Text>{new Date(selectedRecord.created_at).toLocaleString()}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Update time" span={1}>
                <Text>{new Date(selectedRecord.updated_at).toLocaleString()}</Text>
              </Descriptions.Item>
            </Descriptions>

            {selectedRecord.description && (
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ color: '#ffffff' }}>Description</h4>
                <Text>{selectedRecord.description}</Text>
              </div>
            )}

            {selectedRecord.tags && (
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ color: '#ffffff' }}>Tag</h4>
                <Text>{selectedRecord.tags}</Text>
              </div>
            )}

            {selectedRecord.error_message && (
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ color: '#ffffff' }}>Error information</h4>
                <Alert
                  message="Posting failed"
                  description={selectedRecord.error_message}
                  type="error"
                  showIcon
                />
              </div>
            )}

            <div style={{ marginTop: '24px', textAlign: 'right' }}>
              <Space>
                {selectedRecord.status === 'failed' && (
                  <Popconfirm
                    title="Are you sure you want to retry this posting task?? "
                    onConfirm={() => {
                      handleRetry(selectedRecord.id)
                      setDetailModalVisible(false)
                    }}
                    okText="Confirm"
                    cancelText="Cancel"
                  >
                    <Button type="primary" icon={<RedoOutlined />}>
                      Retry
                    </Button>
                  </Popconfirm>
                )}
                <Button onClick={() => setDetailModalVisible(false)}>
                  Close
                </Button>
              </Space>
            </div>
          </div>
        )}
      </Modal>
    </Modal>
  )
}

export default BilibiliManager
