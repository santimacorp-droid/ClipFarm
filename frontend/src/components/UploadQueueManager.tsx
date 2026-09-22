import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Progress,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
  Tooltip,
  Statistic,
  Row,
  Col,
  Badge
} from 'antd';
import {
  ReloadOutlined,
  PlusOutlined,
  UploadOutlined,
  EyeOutlined,
  StopOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { TextArea } = Input;
const { Option } = Select;

interface UploadTask {
  task_id: string;
  video_path: string;
  title: string;
  description: string;
  tags: string;
  account_id?: number;
  priority: number;
  status: string;
  created_at: string;
  updated_at: string;
  progress: number;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  celery_task_id?: string;
  bv_id?: string;
}

interface QueueStatus {
  queued_tasks: number;
  processing_tasks: number;
  max_concurrent: number;
  queue_details: Array<{
    task_id: string;
    title: string;
    priority: number;
    created_at: string;
  }>;
  processing_details: Array<{
    task_id: string;
    title: string;
    progress: number;
    account_id: number;
  }>;
}

interface BilibiliAccount {
  id: number;
  username: string;
  nickname?: string;
  status: string;
  is_vip: boolean;
  level: number;
  can_upload: boolean;
}

const UploadQueueManager: React.FC = () => {
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [accounts, setAccounts] = useState<BilibiliAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [addTaskModalVisible, setAddTaskModalVisible] = useState(false);
  const [batchUploadModalVisible, setBatchUploadModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [batchForm] = Form.useForm();

  // Getting queue status
  const fetchQueueStatus = async () => {
    try {
      const response = await fetch('/api/upload-queue/status');
      if (response.ok) {
        const data = await response.json();
        setQueueStatus(data);
      }
    } catch (error) {
      console.error('Failed to get queue status:', error);
    }
  };

  // Getting upload history
  const fetchUploadHistory = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/upload-queue/history?limit=50');
      if (response.ok) {
        const data = await response.json();
        setTasks(data.records || []);
      }
    } catch (error) {
      console.error('Failed to get upload history:', error);
      message.error('Failed to get upload history');
    } finally {
      setLoading(false);
    }
  };

  // getBSite account list
  const fetchAccounts = async () => {
    try {
      const response = await fetch('/bilibili/accounts');
      if (response.ok) {
        const data = await response.json();
        setAccounts(data.accounts || []);
      }
    } catch (error) {
      console.error('Failed to get account list:', error);
    }
  };

  // Adding single task
  const handleAddTask = async (values: any) => {
    try {
      const response = await fetch('/api/upload-queue/add-task', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        const data = await response.json();
        message.success(`Task added successfully: ${data.task_id}`);
        setAddTaskModalVisible(false);
        form.resetFields();
        fetchQueueStatus();
        fetchUploadHistory();
      } else {
        const error = await response.json();
        message.error(`Failed to add task: ${error.detail}`);
      }
    } catch (error) {
      console.error('Failed to add task:', error);
      message.error('Failed to add task');
    }
  };

  // Batch add tasks
  const handleBatchUpload = async (values: any) => {
    try {
      const tasks = values.tasks.split('\n').filter((line: string) => line.trim()).map((line: string) => {
        const [video_path, title, description = '', tags = ''] = line.split('|').map((s: string) => s.trim());
        return {
          video_path,
          title,
          description,
          tags,
          priority: values.priority || 'normal'
        };
      });

      const response = await fetch('/api/upload-queue/add-batch-tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tasks }),
      });

      if (response.ok) {
        const data = await response.json();
        message.success(`Added batch ${data.count} Tasks`);
        setBatchUploadModalVisible(false);
        batchForm.resetFields();
        fetchQueueStatus();
        fetchUploadHistory();
      } else {
        const error = await response.json();
        message.error(`Batch add failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Batch add failed:', error);
      message.error('Batch add failed');
    }
  };

  // Cancel task
  const handleCancelTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/upload-queue/task/${taskId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        message.success('Task canceled');
        fetchQueueStatus();
        fetchUploadHistory();
      } else {
        const error = await response.json();
        message.error(`Cancel task failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Cancel task failed:', error);
      message.error('Cancel task failed');
    }
  };

  // Retry task
  const handleRetryTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/upload-queue/retry/${taskId}`, {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        message.success(`Task re-added successfully: ${data.new_task_id}`);
        fetchQueueStatus();
        fetchUploadHistory();
      } else {
        const error = await response.json();
        message.error(`Failed to retry task: ${error.detail}`);
      }
    } catch (error) {
      console.error('Failed to retry task:', error);
      message.error('Failed to retry task');
    }
  };

  // Getting status labels
  const getStatusTag = (status: string) => {
    const statusConfig: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: 'Pending' },
      queued: { color: 'blue', text: 'In queue' },
      processing: { color: 'orange', text: 'In progress' },
      completed: { color: 'green', text: 'Completed' },
      failed: { color: 'red', text: 'Failed' },
      cancelled: { color: 'gray', text: 'Canceled' }
    };
    
    const config = statusConfig[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // Getting priority labels failed
  const getPriorityTag = (priority: number) => {
    const priorityConfig: Record<number, { color: string; text: string }> = {
      1: { color: 'default', text: 'low' },
      2: { color: 'blue', text: 'Standard' },
      3: { color: 'orange', text: 'high' },
      4: { color: 'red', text: 'emergency' }
    };
    
    const config = priorityConfig[priority] || { color: 'default', text: 'Standard' };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // Table column definition
  const columns: ColumnsType<UploadTask> = [
    {
      title: 'taskID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 120,
      render: (text: string) => (
        <Tooltip title={text}>
          <span>{text.substring(0, 8)}...</span>
        </Tooltip>
      ),
    },
    {
      title: 'title',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: 'status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: number) => getPriorityTag(priority),
    },
    {
      title: 'progress',
      dataIndex: 'progress',
      key: 'progress',
      width: 120,
      render: (progress: number, record: UploadTask) => (
        <Progress 
          percent={progress} 
          size="small" 
          status={record.status === 'failed' ? 'exception' : 'active'}
        />
      ),
    },
    {
      title: 'accountID',
      dataIndex: 'account_id',
      key: 'account_id',
      width: 80,
    },
    {
      title: 'BVID',
      dataIndex: 'bv_id',
      key: 'bv_id',
      width: 120,
      render: (bvId: string) => bvId ? (
        <a href={`https://www.bilibili.com/video/${bvId}`} target="_blank" rel="noopener noreferrer">
          {bvId}
        </a>
      ) : '-',
    },
    {
      title: 'Creation time',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: 'operation',
      key: 'action',
      width: 150,
      render: (_, record: UploadTask) => (
        <Space size="small">
          {record.status === 'failed' && (
            <Button
              type="link"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => handleRetryTask(record.task_id)}
            >
              Retry
            </Button>
          )}
          {(record.status === 'queued' || record.status === 'processing') && (
            <Button
              type="link"
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancelTask(record.task_id)}
            >
              Cancel
            </Button>
          )}
          {record.error_message && (
            <Tooltip title={record.error_message}>
              <Button type="link" size="small" icon={<EyeOutlined />}>
                error
              </Button>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  useEffect(() => {
    fetchQueueStatus();
    fetchUploadHistory();
    fetchAccounts();

    // Schedule status refresh
    const interval = setInterval(() => {
      fetchQueueStatus();
      fetchUploadHistory();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="upload-queue-manager">
      {/* Queue status summary */}
      {queueStatus && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="Tasks in queue"
                value={queueStatus.queued_tasks}
                prefix={<Badge status="processing" />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Task in progress"
                value={queueStatus.processing_tasks}
                prefix={<Badge status="success" />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Maximum concurrent count"
                value={queueStatus.max_concurrent}
                prefix={<Badge status="default" />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Available account"
                value={(accounts || []).filter(acc => acc.status === 'active' && acc.can_upload).length}
                prefix={<Badge status="success" />}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Operation button */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddTaskModalVisible(true)}
          >
            Add task
          </Button>
          <Button
            icon={<UploadOutlined />}
            onClick={() => setBatchUploadModalVisible(true)}
          >
            Bulk upload
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              fetchQueueStatus();
              fetchUploadHistory();
            }}
          >
            Refresh
          </Button>
        </Space>
      </Card>

      {/* Task list */}
      <Card title="Upload task">
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="task_id"
          loading={loading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `shared ${total} Records`,
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* Add task modal */}
      <Modal
        title="Add upload task"
        open={addTaskModalVisible}
        onCancel={() => setAddTaskModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAddTask}
        >
          <Form.Item
            name="video_path"
            label="Video file path"
            rules={[{ required: true, message: 'Please enter the video file path' }]}
          >
            <Input placeholder="/path/to/video.mp4" />
          </Form.Item>
          
          <Form.Item
            name="title"
            label="Video title"
            rules={[{ required: true, message: 'Please enter the video title' }]}
          >
            <Input placeholder="Video title" maxLength={80} />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="Video description"
          >
            <TextArea rows={4} placeholder="Video description" maxLength={2000} />
          </Form.Item>
          
          <Form.Item
            name="tags"
            label="label"
          >
            <Input placeholder="label1,label2,label3" />
          </Form.Item>
          
          <Form.Item
            name="account_id"
            label="Specify account"
          >
            <Select placeholder="Auto select best account" allowClear>
              {(accounts || []).filter(acc => acc.status === 'active' && acc.can_upload).map(account => (
                <Option key={account.id} value={account.id}>
                  {account.nickname || account.username} 
                  {account.is_vip && <Tag color="gold">VIP</Tag>}
                  <Tag color="blue">Lv.{account.level}</Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item
            name="priority"
            label="Priority"
            initialValue="normal"
          >
            <Select>
              <Option value="low">low</Option>
              <Option value="normal">Standard</Option>
              <Option value="high">high</Option>
              <Option value="urgent">emergency</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Batch upload modal */}
      <Modal
        title="Batch upload tasks"
        open={batchUploadModalVisible}
        onCancel={() => setBatchUploadModalVisible(false)}
        onOk={() => batchForm.submit()}
        width={800}
      >
        <Form
          form={batchForm}
          layout="vertical"
          onFinish={handleBatchUpload}
        >
          <Form.Item
            name="tasks"
            label="Task list"
            rules={[{ required: true, message: 'Please enter the task list' }]}
            extra="One task per row, format: video file path|title|description|label"
          >
            <TextArea
              rows={10}
              placeholder={`/path/to/video1.mp4|Video title1|Video description1|label1,label2
/path/to/video2.mp4|Video title2|Video description2|label3,label4`}
            />
          </Form.Item>
          
          <Form.Item
            name="priority"
            label="Batch priority set"
            initialValue="normal"
          >
            <Select>
              <Option value="low">low</Option>
              <Option value="normal">Standard</Option>
              <Option value="high">high</Option>
              <Option value="urgent">emergency</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UploadQueueManager;