import React, { useState, useEffect, useRef } from 'react'
import {
  Modal,
  Form,
  Input,
  Select,
  Button,
  Space,
  Tag,
  Progress,
  message,
  Divider,
  Row,
  Col,
  Typography,
  Alert,
  Spin
} from 'antd'
import {
  UploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'

const { Option } = Select
const { TextArea } = Input
const { Text } = Typography

interface UploadModalProps {
  visible: boolean
  onCancel: () => void
  projectId?: string
  clipIds: string[]
  clipTitles: string[]
  onSuccess?: () => void
}

interface UploadProgress {
  status: 'pending' | 'processing' | 'success' | 'failed'
  message: string
  progress: number
  bvid?: string
  error?: string
}

const UploadModal: React.FC<UploadModalProps> = ({
  visible,
  onCancel,
  clipIds,
  clipTitles
}) => {
  const [form] = Form.useForm()
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({
    status: 'pending',
    message: 'Preparing upload...',
    progress: 0
  })
  const [uploadRecordId, setUploadRecordId] = useState<string>('')
  const pollingIntervalRef = useRef<any>(null)

  // Form initial values
  const initialValues = {
    title: clipTitles.length === 1 ? clipTitles[0] : `${clipTitles[0]} Equals${clipIds.length}video(s)`,
    description: '',
    tags: [],
    partition_id: undefined,
    account_id: undefined
  }

  // GettingBSite account list
  const [accounts, setAccounts] = useState<any[]>([])
  useEffect(() => {
    if (visible) {
      setAccounts([])
    }
  }, [visible])

  // Submit posting
  const handleSubmit = async (_values: any) => {
    // Show under development notice
    message.info('Bilibili upload is coming soon!', 3)
    /* Disabled pending upload server implementation
    if (!_values.account_id) {
      message.error('Please select an account')
      return
    }

    setUploading(true)
    setUploadProgress({
      status: 'pending',
      message: 'Creating upload task...',
      progress: 10
    })

    try {
      const response = await uploadApi.createUploadTask(projectId, {
        clip_ids: clipIds,
        account_id: _values.account_id,
        title: _values.title,
        description: _values.description,
        tags: _values.tags,
        partition_id: _values.partition_id
      })

      setUploadRecordId(response.record_id)
      setUploadProgress({
        status: 'processing',
        message: `Task created, processing ${response.clip_count} clips...`,
        progress: 30
      })

      startPolling(response.record_id)
      message.success('Upload task created successfully!')
    } catch (error: any) {
      console.error('Failed to create upload task:', error)
      setUploadProgress({
        status: 'failed',
        message: `Failed: ${error.message || 'Unknown error'}`,
        progress: 0,
        error: error.message
      })
      setUploading(false)
    }
    */
  }

  /* Start polling upload status (pending server implementation)
  const startPolling = (recordId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await uploadApi.getUploadRecord(recordId)
        
        if (status.status === 'success') {
          setUploadProgress({
            status: 'success',
            message: 'Posting successful! ',
            progress: 100,
            bvid: status.bvid
          })
          setUploading(false)
          clearInterval(interval)
          
          // Delay closing popup to let user see success status
          setTimeout(() => {
            onSuccess?.()
            onCancel()
          }, 2000)
        } else if (status.status === 'failed') {
          setUploadProgress({
            status: 'failed',
            message: `Posting failed: ${status.error_message || 'Unknown error'}`,
            progress: 0,
            error: status.error_message
          })
          setUploading(false)
          clearInterval(interval)
        } else if (status.status === 'processing') {
          setUploadProgress({
            status: 'processing',
            message: 'Uploading toBStation...',
            progress: 60
          })
        } else if (status.status === 'pending') {
          setUploadProgress({
            status: 'processing',
            message: 'Task queued, please wait...',
            progress: 40
          })
        } else {
          // For other states, gradually increase progress
          setUploadProgress(prev => ({
            ...prev,
            message: `Task status: ${status.status}`,
            progress: Math.min(prev.progress + 5, 90)
          }))
        }
      } catch (error) {
        console.error('Get upload status failed:', error)
        setUploadProgress({
          status: 'failed',
          message: 'Get upload status failed',
          progress: 0,
          error: 'Network error'
        })
        setUploading(false)
        clearInterval(interval)
      }
    }, 2000)

    setPollingInterval(interval)
  }
  */

  /* Cleanup poll
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])
  */

  // Clean up state when popup closes
  const handleCancel = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
    setUploading(false)
    setUploadProgress({
      status: 'pending',
      message: 'Preparing upload...',
      progress: 0
    })
    setUploadRecordId('')
    form.resetFields()
    onCancel()
  }

  // Cancel posting task
  const handleCancelUpload = async () => {
    if (!uploadRecordId) {
      handleCancel()
      return
    }

    try {
      // Cleanup status
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      setUploading(false)
      setUploadProgress({
        status: 'pending',
        message: 'Preparing upload...',
        progress: 0
      })
      setUploadRecordId('')
      form.resetFields()
      
      // Show cancel success message
      message.success('Posting task cancelled')
      onCancel()
    } catch (error) {
      console.error('Cancel posting failed:', error)
      message.error('Cancel posting failed, please try again')
    }
  }

  // Get status icon
  const getStatusIcon = () => {
    switch (uploadProgress.status) {
      case 'pending':
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />
      case 'processing':
        return <ExclamationCircleOutlined style={{ color: '#faad14' }} />
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
      default:
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />
    }
  }

  // Get progress bar status
  const getProgressStatus = () => {
    if (uploadProgress.status === 'failed') return 'exception'
    if (uploadProgress.status === 'success') return 'success'
    return 'active'
  }

  return (
    <Modal
      title={
        <Space>
          <UploadOutlined style={{ color: '#1890ff' }} />
          <span>Publish to Bilibili</span>
          {clipIds.length > 1 && (
            <Tag color="blue">{clipIds.length} videos</Tag>
          )}
        </Space>
      }
      open={visible}
      onCancel={handleCancel}
      footer={null}
      width={700}
      destroyOnClose
      maskClosable={!uploading}
      closable={!uploading}
    >
      {!uploading ? (
        // Posting form
        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={handleSubmit}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Bilibili Account"
                name="account_id"
                rules={[{ required: true, message: 'Please select an account' }]}
              >
                <Select placeholder="Select account">
                  {accounts.map(account => (
                    <Option key={account.id} value={account.id}>
                      {account.nickname || account.username} ({account.username})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Partition"
                name="partition_id"
              >
                <Select placeholder="Select partition" showSearch disabled>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="Title"
            name="title"
            rules={[{ required: true, message: 'Please enter a title' }]}
          >
            <Input placeholder="Enter title" maxLength={80} showCount />
          </Form.Item>

          <Form.Item
            label="Description"
            name="description"
            rules={[{ required: true, message: 'Please enter a description' }]}
          >
            <TextArea
              placeholder="Enter description"
              rows={4}
              maxLength={250}
              showCount
            />
          </Form.Item>

          <Form.Item
            label="Tags"
            name="tags"
            extra="Add up to 10 tags, press Enter to add"
          >
            <Select
              mode="tags"
              placeholder="Type tags and press Enter"
              maxTagCount={10}
              maxTagTextLength={20}
            />
          </Form.Item>

          <Divider />

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={handleCancel}>
                Cancel
              </Button>
              <Button
                type="primary"
                onClick={() => message.info('Feature under development', 3)}
                icon={<UploadOutlined />}
              >
                Publish
              </Button>
            </Space>
          </div>
        </Form>
      ) : (
        // Upload progress
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{ marginBottom: '24px' }}>
            {getStatusIcon()}
            <Text style={{ marginLeft: '8px', fontSize: '16px' }}>
              {uploadProgress.message}
            </Text>
          </div>

          <Progress
            percent={uploadProgress.progress}
            status={getProgressStatus()}
            strokeWidth={8}
            style={{ marginBottom: '24px' }}
          />

          {uploadProgress.status === 'success' && uploadProgress.bvid && (
            <Alert
              message="Posting successful! "
              description={`BVNo.: ${uploadProgress.bvid}`}
              type="success"
              showIcon
              style={{ marginBottom: '16px' }}
            />
          )}

          {uploadProgress.status === 'failed' && uploadProgress.error && (
            <Alert
              message="Posting failed"
              description={uploadProgress.error}
              type="error"
              showIcon
              style={{ marginBottom: '16px' }}
            />
          )}

          {uploadProgress.status === 'processing' && (
            <div style={{ color: '#666', fontSize: '14px' }}>
              <Spin size="small" style={{ marginRight: '8px' }} />
              In processing, please wait...
              {uploadRecordId && (
                <div style={{ marginTop: '8px', fontSize: '12px', color: '#999' }}>
                  TaskID: {uploadRecordId}
                </div>
              )}
            </div>
          )}

          <div style={{ marginTop: '16px' }}>
            {uploadProgress.status === 'failed' && (
              <Button
                type="primary"
                onClick={() => {
                  setUploading(false)
                  setUploadProgress({
                    status: 'pending',
                    message: 'Preparing upload...',
                    progress: 0
                  })
                }}
                style={{ marginRight: '8px' }}
              >
                Resubmit
              </Button>
            )}
            
            <Button
              onClick={handleCancelUpload}
              disabled={uploadProgress.status === 'success'}
            >
              {uploadProgress.status === 'success' ? 'Close' : 'Cancel'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}

export default UploadModal
