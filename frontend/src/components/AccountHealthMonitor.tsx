import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Tooltip,
  Progress,
  Modal,
  message,
  Statistic,
  Row,
  Col,
  Alert,
  Spin,
  Badge
} from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
// Removedate-fnsDependency, using built-in method

// Interface definition
interface AccountHealth {
  account_id: number;
  username: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  message: string;
  details: {
    cookie?: {
      status: string;
      message: string;
      expires_in?: number;
    };
    login?: {
      status: string;
      message: string;
      user_info?: {
        uname: string;
        mid: number;
        level: number;
      };
    };
    upload?: {
      status: string;
      message: string;
    };
  };
  last_check: string;
  expires_in?: number;
}

interface HealthSummary {
  total_accounts: number;
  healthy_count: number;
  warning_count: number;
  critical_count: number;
  unknown_count: number;
  accounts: AccountHealth[];
  last_updated: string;
}

interface AccountHealthMonitorProps {
  onRefresh?: () => void;
}

const AccountHealthMonitor: React.FC<AccountHealthMonitorProps> = () => {
  const [healthData, setHealthData] = useState<HealthSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState<number[]>([]);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<AccountHealth | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<any>(null);

  // Time formatting function
  const getTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return 'Just';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}Minutes ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}Hours ago`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}Days ago`;
    }
  };

  // Get health status summary
  const fetchHealthSummary = async (forceCheck = false) => {
    try {
      setLoading(true);
      const endpoint = forceCheck ? '/health/check' : '/health/summary';
      const method = forceCheck ? 'POST' : 'GET';
      const body = forceCheck ? JSON.stringify({ force_check: true }) : undefined;
      
      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      setHealthData(data);
      
      if (forceCheck) {
        message.success('Health check complete');
      }
    } catch (error) {
      console.error('Failed to get health status:', error);
      message.error('Failed to get health status');
    } finally {
      setLoading(false);
    }
  };

  // Check single account
  const checkSingleAccount = async (accountId: number, forceCheck = true) => {
    try {
      setRefreshing(prev => [...prev, accountId]);
      
      const response = await fetch(`/api/v1/health/check/${accountId}?force_check=${forceCheck}`, {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const updatedAccount = await response.json();
      
      // Update health data
      setHealthData(prev => {
        if (!prev) return prev;
        
        const updatedAccounts = prev.accounts.map(account => 
          account.account_id === accountId ? updatedAccount : account
        );
        
        // Recalculate statistics
        const statusCounts = {
          healthy: 0,
          warning: 0,
          critical: 0,
          unknown: 0
        };
        
        updatedAccounts.forEach(account => {
          statusCounts[account.status as keyof typeof statusCounts]++;
        });
        
        return {
          ...prev,
          accounts: updatedAccounts,
          healthy_count: statusCounts.healthy,
          warning_count: statusCounts.warning,
          critical_count: statusCounts.critical,
          unknown_count: statusCounts.unknown,
          last_updated: new Date().toISOString()
        };
      });
      
      message.success(`Account ${updatedAccount.username} Check completed`);
    } catch (error) {
      console.error('Account check failed:', error);
      message.error('Account check failed');
    } finally {
      setRefreshing(prev => prev.filter(id => id !== accountId));
    }
  };

  // RefreshCookie
  const refreshCookie = async (accountId: number) => {
    try {
      const response = await fetch('/health/refresh-cookie', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          account_id: accountId,
          auto_refresh: true
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch (error) {
      console.error('RefreshCookieFailure:', error);
      message.error('RefreshCookieFailure');
    }
  };

  // Get status labels
  const getStatusTag = (status: string) => {
    const statusConfig = {
      healthy: { color: 'success', icon: <CheckCircleOutlined />, text: 'Healthy' },
      warning: { color: 'warning', icon: <ExclamationCircleOutlined />, text: 'Warning' },
      critical: { color: 'error', icon: <CloseCircleOutlined />, text: 'Severe' },
      unknown: { color: 'default', icon: <QuestionCircleOutlined />, text: 'Unknown' }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
    
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  // Get expiration progress bar
  const getExpirationProgress = (expiresIn?: number) => {
    if (expiresIn === undefined || expiresIn === null) {
      return null;
    }
    
    const totalDays = 30; // AssumeCookieTotal duration of30Days
    const percentage = Math.max(0, Math.min(100, (expiresIn / totalDays) * 100));
    
    let status: 'success' | 'normal' | 'exception' = 'success';
    if (expiresIn <= 0) {
      status = 'exception';
    } else if (expiresIn <= 7) {
      status = 'normal';
    }
    
    return (
      <Tooltip title={`There are ${expiresIn} days until expiration`}>
        <Progress
          percent={percentage}
          status={status}
          size="small"
          showInfo={false}
          strokeWidth={6}
        />
      </Tooltip>
    );
  };

  // Table column definitions
  const columns = [
    {
      title: 'Account',
      dataIndex: 'username',
      key: 'username',
      render: (username: string, record: AccountHealth) => (
        <Space>
          <span>{username}</span>
          {record.details.login?.user_info && (
            <Tooltip title={`Level: ${record.details.login.user_info.level}`}>
              <Badge count={record.details.login.user_info.level} color="blue" />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: 'Health status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: 'CookieStatus',
      key: 'cookie_status',
      render: (record: AccountHealth) => (
        <Space direction="vertical" size="small">
          {getStatusTag(record.details.cookie?.status || 'unknown')}
          {getExpirationProgress(record.expires_in)}
        </Space>
      ),
    },
    {
      title: 'Last check',
      dataIndex: 'last_check',
      key: 'last_check',
      render: (lastCheck: string) => (
        <Tooltip title={new Date(lastCheck).toLocaleString()}>
          <Space>
            <ClockCircleOutlined />
            {getTimeAgo(lastCheck)}
          </Space>
        </Tooltip>
      ),
    },
    {
      title: 'Action',
      key: 'actions',
      render: (record: AccountHealth) => (
        <Space>
          <Button
            type="text"
            icon={<ReloadOutlined />}
            loading={refreshing.includes(record.account_id)}
            onClick={() => checkSingleAccount(record.account_id)}
          >
            Check
          </Button>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => {
              setSelectedAccount(record);
              setDetailsVisible(true);
            }}
          >
            Details
          </Button>
          {record.status === 'critical' || record.status === 'warning' ? (
            <Button
              type="text"
              danger
              onClick={() => refreshCookie(record.account_id)}
            >
              RefreshCookie
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  // Fetch data when mounting component
  useEffect(() => {
    fetchHealthSummary();
  }, []);

  // Auto refresh
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchHealthSummary();
      }, 60000); // Refresh every minute
      setRefreshInterval(interval);
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
    
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, [autoRefresh]);

  return (
    <div>
      {/* Statistics card */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total account count"
              value={healthData?.total_accounts || 0}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Healthy account"
              value={healthData?.healthy_count || 0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Warning account"
              value={healthData?.warning_count || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Critical issue"
              value={healthData?.critical_count || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Action bar */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => fetchHealthSummary(true)}
          >
            All checks
          </Button>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => fetchHealthSummary()}
          >
            Refresh status
          </Button>
          <Button
            type={autoRefresh ? 'primary' : 'default'}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            {autoRefresh ? 'Stop auto-refreshing' : 'Start auto-refreshing'}
          </Button>
        </Space>
        
        {healthData?.last_updated && (
          <div style={{ float: 'right', color: '#666' }}>
            Last updated: {getTimeAgo(healthData.last_updated)}
          </div>
        )}
      </Card>

      {/* Warning information */}
      {healthData && (healthData.critical_count > 0 || healthData.warning_count > 0) && (
        <Alert
          message="Account health warning"
          description={`Found ${healthData.critical_count} <n> serious issues and ${healthData.warning_count} Warnings, please address immediately`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Account list */}
      <Card title="Account health status">
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={healthData?.accounts || []}
            rowKey="account_id"
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `Total / Together ${total} accounts`,
            }}
          />
        </Spin>
      </Card>

      {/* Details popup */}
      <Modal
        title={`Account details - ${selectedAccount?.username}`}
        open={detailsVisible}
        onCancel={() => setDetailsVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailsVisible(false)}>
            Close
          </Button>,
          <Button
            key="refresh"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={() => {
              if (selectedAccount) {
                checkSingleAccount(selectedAccount.account_id);
              }
            }}
          >
            Recheck
          </Button>,
        ]}
        width={600}
      >
        {selectedAccount && (
          <div>
            <Row gutter={16}>
              <Col span={12}>
                <Card title="Basic information" size="small">
                  <p><strong>AccountID:</strong> {selectedAccount.account_id}</p>
                  <p><strong>Username:</strong> {selectedAccount.username}</p>
                  <p><strong>Overall status:</strong> {getStatusTag(selectedAccount.status)}</p>
                  <p><strong>Status message:</strong> {selectedAccount.message}</p>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="Check time" size="small">
                  <p><strong>Last check:</strong> {new Date(selectedAccount.last_check).toLocaleString()}</p>
                  {selectedAccount.expires_in !== undefined && (
                    <p><strong>CookieExpired:</strong> {selectedAccount.expires_in} Days later</p>
                  )}
                </Card>
              </Col>
            </Row>
            
            <Card title="Detailed status" size="small" style={{ marginTop: 16 }}>
              {selectedAccount.details.cookie && (
                <div style={{ marginBottom: 12 }}>
                  <strong>CookieStatus:</strong> {getStatusTag(selectedAccount.details.cookie.status)}
                  <p>{selectedAccount.details.cookie.message}</p>
                </div>
              )}
              
              {selectedAccount.details.login && (
                <div style={{ marginBottom: 12 }}>
                  <strong>Login status:</strong> {getStatusTag(selectedAccount.details.login.status)}
                  <p>{selectedAccount.details.login.message}</p>
                  {selectedAccount.details.login.user_info && (
                    <p>User information: {selectedAccount.details.login.user_info.uname} (Level {selectedAccount.details.login.user_info.level})</p>
                  )}
                </div>
              )}
              
              {selectedAccount.details.upload && (
                <div>
                  <strong>Upload permission:</strong> {getStatusTag(selectedAccount.details.upload.status)}
                  <p>{selectedAccount.details.upload.message}</p>
                </div>
              )}
            </Card>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default AccountHealthMonitor;