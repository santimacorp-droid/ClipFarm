import React, { useState, useEffect } from 'react'
import { Card, Button, Modal, Form, Input, Table, Tag, Space, message, Popconfirm, Tabs, Alert, Typography, Divider, Tooltip, Statistic } from 'antd'
import { PlusOutlined, DeleteOutlined, UserOutlined, CheckCircleOutlined, CloseCircleOutlined, QrcodeOutlined, ExclamationCircleOutlined, QuestionCircleOutlined, HeartOutlined, TrophyOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import { uploadApi, BilibiliAccount } from '../services/uploadApi'
import CookieHelper from './CookieHelper'
import AccountHealthMonitor from './AccountHealthMonitor'

const { TextArea } = Input
const { Text, Paragraph } = Typography
const { TabPane } = Tabs

interface AccountHealth {
  score: number
  status: 'excellent' | 'good' | 'warning' | 'poor'
  lastActive: string
  uploadCount: number
  successRate: number
}

const BilibiliAccountManager: React.FC = () => {
  const [accounts, setAccounts] = useState<BilibiliAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [activeTab, setActiveTab] = useState('cookie')
  const [cookieHelperVisible, setCookieHelperVisible] = useState(false)
  const [accountsHealth, setAccountsHealth] = useState<Record<string, AccountHealth>>({})
  const [refreshing, setRefreshing] = useState(false)
  
  // Form-related status
  const [passwordForm] = Form.useForm()
  const [cookieForm] = Form.useForm()
  const [qrSessionId, setQrSessionId] = useState<string>('')
  const [qrLoginStatus, setQrLoginStatus] = useState<string>('')
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('')
  const [statusCheckInterval, setStatusCheckInterval] = useState<any>(null)

  // Get account list
  const fetchAccounts = async () => {
    try {
      setLoading(true)
      const data = await uploadApi.getAccounts()
      setAccounts(data)
      // While retrieving account health status
      await fetchAccountsHealth(data)
    } catch (error: any) {
      message.error('Failed to retrieve account list: ' + (error.message || 'unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // Getting account health status
  const fetchAccountsHealth = async (accountList?: BilibiliAccount[]) => {
    try {
      const targetAccounts = accountList || accounts
      const healthData: Record<string, AccountHealth> = {}
      
      for (const account of targetAccounts) {
        // Simulating health status data, actual should be fromAPIGet
        const score = Math.floor(Math.random() * 40) + 60 // 60-100Minute
        const uploadCount = Math.floor(Math.random() * 50) + 10
        const successRate = Math.floor(Math.random() * 30) + 70
        
        let status: AccountHealth['status'] = 'good'
        if (score >= 90) status = 'excellent'
        else if (score >= 75) status = 'good'
        else if (score >= 60) status = 'warning'
        else status = 'poor'
        
        healthData[account.id] = {
          score,
          status,
          lastActive: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
          uploadCount,
          successRate
        }
      }
      
      setAccountsHealth(healthData)
    } catch (error: any) {
      console.error('Failed to retrieve account health status:', error)
    }
  }

  // Refreshing account health status
  const refreshAccountsHealth = async () => {
    try {
      setRefreshing(true)
      await fetchAccountsHealth()
      message.success('Health status refreshed successfully')
    } catch (error: any) {
      message.error('Refresh failed: ' + (error.message || 'unknown error'))
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
    
    // Clear timer
    return () => {
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval)
      }
    }
  }, [])

  // Account password login
  const handlePasswordLogin = async (values: any) => {
    try {
      setLoading(true)
      await uploadApi.passwordLogin(values.username, values.password, values.nickname)
      message.success('Account password login successful! ')
      setModalVisible(false)
      passwordForm.resetFields()
      fetchAccounts()
    } catch (error: any) {
      message.error('Account password login failed: ' + (error.message || 'unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // Cookieimport login
  const handleCookieLogin = async (values: any) => {
    try {
      setLoading(true)
      
      // ParseCookiestring
      const cookieStr = values.cookies.trim()
      const cookies: Record<string, string> = {}
      
      cookieStr.split(';').forEach((cookie: string) => {
        const [key, value] = cookie.trim().split('=')
        if (key && value) {
          cookies[key] = value
        }
      })
      
      if (Object.keys(cookies).length === 0) {
        message.error('CookieThe format is incorrect. Please check your input')
        return
      }
      
      await uploadApi.cookieLogin(cookies, values.nickname)
      message.success('Cookieimport successful! ')
      setModalVisible(false)
      cookieForm.resetFields()
      fetchAccounts()
    } catch (error: any) {
      message.error('Cookieimport failed: ' + (error.message || 'unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // Beginning QR code login
  const startQRLogin = async (nickname?: string) => {
    try {
      setLoading(true)
      
      // Clearing previous polling
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval)
        setStatusCheckInterval(null)
      }
      
      const response = await uploadApi.startQRLogin(nickname)
      setQrSessionId(response.session_id)
      setQrLoginStatus(response.status)
      
      // Beginning poll for login status
      let pollCount = 0
      const maxPolls = 60
      
      const interval = setInterval(async () => {
        try {
          pollCount++
          if (pollCount > maxPolls) {
            message.error('QR code login timed out. Please try again')
            setQrSessionId('')
            setQrLoginStatus('')
            setQrCodeUrl('')
            clearInterval(interval)
            return
          }
          
          const statusResponse = await uploadApi.checkQRLoginStatus(response.session_id)
          setQrLoginStatus(statusResponse.status)
          
          if (statusResponse.qr_code) {
            setQrCodeUrl(statusResponse.qr_code)
          }
          
          if (statusResponse.status === 'success') {
            message.success('QR code login successful! ')
            clearInterval(interval)
            setModalVisible(false)
            fetchAccounts()
          } else if (statusResponse.status === 'failed') {
            message.error('QR code login failed. Please try again')
            clearInterval(interval)
          }
        } catch (error: any) {
          console.error('Checking login status failed:', error)
        }
      }, 1000)
      
      setStatusCheckInterval(interval)
      
    } catch (error: any) {
      message.error('QR code login startup failed: ' + (error.message || 'unknown error'))
    } finally {
      setLoading(false)
    }
  }

  // delete account
  const handleDeleteAccount = async (accountId: string) => {
    try {
      await uploadApi.deleteAccount(accountId)
      message.success('Account deleted successfully')
      fetchAccounts()
    } catch (error: any) {
      message.error('Failed to delete account: ' + (error.message || 'unknown error'))
    }
  }

  // Unable to retrieve health status tags and colors
  const getHealthStatusTag = (health?: AccountHealth) => {
    if (!health) return <Tag>Unknown</Tag>
    
    const statusConfig = {
      excellent: { color: 'green', text: 'Excellent', icon: <TrophyOutlined /> },
      good: { color: 'blue', text: 'good', icon: <CheckCircleOutlined /> },
      warning: { color: 'orange', text: 'warning', icon: <ExclamationCircleOutlined /> },
      poor: { color: 'red', text: 'poor', icon: <CloseCircleOutlined /> }
    }
    
    const config = statusConfig[health.status]
    return (
      <Tooltip title={`health score: ${health.score}/100`}>
        <Tag color={config.color} icon={config.icon}>
          {config.text} ({health.score})
        </Tag>
      </Tooltip>
    )
  }

  // Format last active time
  const formatLastActive = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) return 'today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}days ago`
    return date.toLocaleDateString()
  }

  const columns = [
    {
      title: 'username',
      dataIndex: 'username',
      key: 'username',
      render: (username: string) => (
        <Space>
          <UserOutlined />
          <span>{username}</span>
        </Space>
      ),
    },
    {
      title: 'Nickname',
      dataIndex: 'nickname',
      key: 'nickname',
    },
    {
      title: 'Account status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'} icon={status === 'active' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}>
          {status === 'active' ? 'Normal' : 'Abnormal'}
        </Tag>
      ),
    },
    {
      title: 'health status',
      key: 'health',
      render: (_: any, record: BilibiliAccount) => getHealthStatusTag(accountsHealth[record.id]),
    },
    {
      title: 'activity level',
      key: 'activity',
      render: (_: any, record: BilibiliAccount) => {
        const health = accountsHealth[record.id]
        if (!health) return '-'
        
        return (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <EyeOutlined style={{ color: '#1890ff' }} />
              <span style={{ fontSize: '12px' }}>Upload: {health.uploadCount}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HeartOutlined style={{ color: '#52c41a' }} />
              <span style={{ fontSize: '12px' }}>success rate: {health.successRate}%</span>
            </div>
            <div style={{ fontSize: '11px', color: '#999' }}>
              last activity: {formatLastActive(health.lastActive)}
            </div>
          </Space>
        )
      },
    },
    {
      title: 'operation',
      key: 'action',
      render: (_: any, record: BilibiliAccount) => (
        <Space size="middle">
          <Tooltip title="view details">
            <Button type="text" icon={<EyeOutlined />} size="small">
              Details
            </Button>
          </Tooltip>
          <Popconfirm
            title="Are you sure you want to delete this account?? "
            description="After deletion, you will not be able to restore it. Please operate with caution. "
            onConfirm={() => handleDeleteAccount(record.id)}
            okText="Confirm"
            cancelText="Cancel"
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small">
              delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // Calculating overall statistical data
  const getTotalStats = () => {
    const safeAccounts = Array.isArray(accounts) ? accounts : []
    const totalAccounts = safeAccounts.length
    const activeAccounts = safeAccounts.filter(acc => acc.status === 'active').length
    const healthScores = Object.values(accountsHealth).map(h => h.score)
    const avgHealth = healthScores.length > 0 ? Math.round(healthScores.reduce((a, b) => a + b, 0) / healthScores.length) : 0
    const excellentCount = Object.values(accountsHealth).filter(h => h.status === 'excellent').length
    
    return { totalAccounts, activeAccounts, avgHealth, excellentCount }
  }

  const stats = getTotalStats()

  return (
    <div>
      <Tabs
        defaultActiveKey="accounts"
        items={[
          {
            key: 'accounts',
            label: (
              <span>
                <UserOutlined />
                account management
              </span>
            ),
            children: (
              <div>
                {/* Statistics card */}
                <div style={{ marginBottom: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  <Card size="small">
                    <Statistic
                      title="total number of accounts"
                      value={stats.totalAccounts}
                      prefix={<UserOutlined />}
                      valueStyle={{ color: '#1890ff' }}
                    />
                  </Card>
                  <Card size="small">
                    <Statistic
                      title="active accounts"
                      value={stats.activeAccounts}
                      suffix={`/ ${stats.totalAccounts}`}
                      prefix={<CheckCircleOutlined />}
                      valueStyle={{ color: '#52c41a' }}
                    />
                  </Card>
                  <Card size="small">
                    <Statistic
                      title="Average health score"
                      value={stats.avgHealth}
                      suffix="Minute"
                      prefix={<HeartOutlined />}
                      valueStyle={{ color: stats.avgHealth >= 80 ? '#52c41a' : stats.avgHealth >= 60 ? '#faad14' : '#ff4d4f' }}
                    />
                  </Card>
                  <Card size="small">
                    <Statistic
                      title="excellent accounts"
                      value={stats.excellentCount}
                      prefix={<TrophyOutlined />}
                      valueStyle={{ color: '#722ed1' }}
                    />
                  </Card>
                </div>

                <Card 
                  title="BManage station accounts" 
                  extra={
                    <Space>
                      <Tooltip title="Refresh health status">
                        <Button 
                          icon={<ReloadOutlined />} 
                          onClick={refreshAccountsHealth}
                          loading={refreshing}
                          size="small"
                        >
                          refresh
                        </Button>
                      </Tooltip>
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
                        Add account
                      </Button>
                    </Space>
                  }
                >
                  <Table
                    columns={columns}
                    dataSource={accounts}
                    rowKey="id"
                    loading={loading}
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: true,
                      showQuickJumper: true,
                      showTotal: (total, range) => `Page ${range[0]}-${range[1]} lines, total ${total} Line`
                    }}
                    scroll={{ x: 800 }}
                  />
                </Card>
              </div>
            ),
          },
          {
            key: 'health',
            label: (
              <span>
                <HeartOutlined />
                health monitoring
              </span>
            ),
            children: <AccountHealthMonitor onRefresh={fetchAccounts} />,
          },
        ]}
      />

      <Modal
        title="AddBsite account"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setQrSessionId('')
          setQrLoginStatus('')
          setQrCodeUrl('')
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval)
            setStatusCheckInterval(null)
          }
        }}
        footer={null}
        width={600}
      >
        <Alert
          message="Login method description"
          description="To avoid Bilibili risk control restrictions, we recommend using the Cookie import method. QR code login may trigger risk control mechanisms."
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="CookieImport" key="cookie">
            <Form form={cookieForm} onFinish={handleCookieLogin} layout="vertical">
              <Form.Item
                name="nickname"
                label="Nickname"
                rules={[{ required: true, message: 'Please enter nickname' }]}
              >
                <Input placeholder="Please enter account nickname" />
              </Form.Item>
              
                             <Form.Item
                 name="cookies"
                 label={
                   <Space>
                     <span>Cookie</span>
                     <Button 
                       type="link" 
                       size="small" 
                       icon={<QuestionCircleOutlined />}
                       onClick={() => setCookieHelperVisible(true)}
                     >
                       Get help
                     </Button>
                   </Space>
                 }
                 rules={[{ required: true, message: 'enterCookie' }]}
               >
                 <TextArea
                   rows={6}
                   placeholder="Please copy from the browser developer toolCookie, Format as: SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
                 />
               </Form.Item>
              
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} block>
                  ImportCookie
                </Button>
              </Form.Item>
            </Form>
            
                         <Divider />
             <Paragraph type="secondary" style={{ fontSize: '12px' }}>
               <Text strong>get quicklyCookie: </Text>
               <br />
               Click the "Get Help" button above to view detailedCookieGetting step-by-step guide
             </Paragraph>
          </TabPane>

          <TabPane tab="Account password" key="password">
            <Form form={passwordForm} onFinish={handlePasswordLogin} layout="vertical">
              <Form.Item
                name="username"
                label="username"
                rules={[{ required: true, message: 'Please enter username' }]}
              >
                <Input placeholder="enterBSite username or phone number" />
              </Form.Item>
              
              <Form.Item
                name="password"
                label="password"
                rules={[{ required: true, message: 'Please enter password' }]}
              >
                <Input.Password placeholder="Please enter password" />
              </Form.Item>
              
              <Form.Item
                name="nickname"
                label="Nickname"
                rules={[{ required: true, message: 'Please enter nickname' }]}
              >
                <Input placeholder="Please enter account nickname" />
              </Form.Item>
              
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} block>
                  login
                </Button>
              </Form.Item>
            </Form>
            
            <Alert
              message="Note"
              description="Account password login may require handling CAPTCHA; if you encounter problems, please consider usingCookieimport method. "
              type="warning"
              showIcon
            />
          </TabPane>

          <TabPane tab="scan to log in" key="qr">
            <div style={{ textAlign: 'center' }}>
              {!qrSessionId ? (
                <div>
                  <Form.Item label="Nickname">
                    <Input placeholder="Enter username (optional))" />
                  </Form.Item>
                  <Button 
                    type="primary" 
                    icon={<QrcodeOutlined />}
                    onClick={() => startQRLogin()}
                    loading={loading}
                    block
                  >
                    Start scanning QR code login
                  </Button>
                </div>
              ) : (
                <div>
                  {qrCodeUrl && (
                    <div style={{ marginBottom: '16px' }}>
                      <img src={qrCodeUrl} alt="QR code" style={{ maxWidth: '200px' }} />
                    </div>
                  )}
                  
                  {qrLoginStatus === 'pending' && (
                    <p>Generating QR code in progress...</p>
                  )}
                  
                  {qrLoginStatus === 'processing' && (
                    <p>Please useBSiteAPPScan QR code</p>
                  )}
                  
                  {qrLoginStatus === 'success' && (
                    <p style={{ color: '#52c41a' }}>✅ Login successful! </p>
                  )}
                  
                  {qrLoginStatus === 'failed' && (
                    <p style={{ color: '#ff4d4f' }}>❌ Login failed - please try again</p>
                  )}
                </div>
              )}
            </div>
            
            <Alert
              message="risk warning"
              description="QR code login may triggerBSite risk control mechanism, and we recommend prioritizing scanningCookieimport method. "
              type="error"
              showIcon
            />
          </TabPane>
        </Tabs>
      </Modal>

      <CookieHelper 
        visible={cookieHelperVisible}
        onClose={() => setCookieHelperVisible(false)}
      />
    </div>
  )
 }

export default BilibiliAccountManager
