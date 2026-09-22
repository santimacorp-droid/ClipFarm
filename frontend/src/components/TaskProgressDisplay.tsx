import React, { useState } from 'react';
import { Progress, Card, Typography, Tag, Space, Button, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useTaskProgress, TaskProgressState } from '../hooks/useTaskProgress';

const { Text } = Typography;

interface TaskProgressDisplayProps {
  userId: string;
  taskId: string;
  onTaskComplete?: (state: TaskProgressState) => void;
  onTaskFailed?: (state: TaskProgressState) => void;
}

export const TaskProgressDisplay: React.FC<TaskProgressDisplayProps> = ({
  userId,
  taskId,
  onTaskComplete,
  onTaskFailed
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const {
    taskState,
    isConnected,
    isSubscribed,
    performFinalStateCheck
  } = useTaskProgress({
    userId,
    taskId,
    onProgressUpdate: (state) => {
      console.log('Task progress update:', state);
    },
    onTaskComplete: (state) => {
      console.log('Task completed:', state);
      message.success('Task processing completed!');
      onTaskComplete?.(state);
    },
    onTaskFailed: (state) => {
      console.log('Task failed:', state);
      message.error(`Task processing failed: ${state.message}`);
      onTaskFailed?.(state);
    }
  });

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case 'transcribe': return 'blue';
      case 'analyze': return 'green';
      case 'clip': return 'orange';
      case 'encode': return 'purple';
      case 'upload': return 'red';
      default: return 'default';
    }
  };

  const getPhaseText = (phase: string) => {
    switch (phase) {
      case 'transcribe': return 'Voice recognition';
      case 'analyze': return 'Content analysis';
      case 'clip': return 'Video slice';
      case 'encode': return 'Video encoding';
      case 'upload': return 'Upload processing';
      default: return phase;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PENDING': return 'default';
      case 'PROGRESS': return 'processing';
      case 'DONE': return 'success';
      case 'FAIL': return 'error';
      default: return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'PENDING': return 'In wait';
      case 'PROGRESS': return 'In progress';
      case 'DONE': return 'Done';
      case 'FAIL': return 'failed';
      default: return status;
    }
  };

  if (!taskState) {
    return (
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Text type="secondary">task {taskId}</Text>
          <Tag color={isConnected ? 'success' : 'error'}>
            {isConnected ? 'Connected' : 'Not connected'}
          </Tag>
          <Tag color={isSubscribed ? 'success' : 'default'}>
            {isSubscribed ? 'Subscribed' : 'Not subscribed'}
          </Tag>
        </Space>
      </Card>
    );
  }

  return (
    <Card 
      size="small" 
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <Text strong>Task progress</Text>
          <Tag color={getStatusColor(taskState.status)}>
            {getStatusText(taskState.status)}
          </Tag>
          <Tag color={getPhaseColor(taskState.phase)}>
            {getPhaseText(taskState.phase)}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Button 
            size="small" 
            icon={<ReloadOutlined />}
            onClick={performFinalStateCheck}
            title="Final state calibration"
          />
          <Button 
            size="small" 
            type="text"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? 'Collapse' : 'Expand'}
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* Progress bar */}
        <div>
          <Progress 
            percent={taskState.progress}
            status={taskState.status === 'FAIL' ? 'exception' : 
                   taskState.status === 'DONE' ? 'success' : 'active'}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {taskState.step}/{taskState.total} step
          </Text>
        </div>

        {/* Current message */}
        <Text>{taskState.message}</Text>

        {/* Expanded details */}
        {isExpanded && (
          <div style={{ 
            padding: '12px', 
            backgroundColor: '#f5f5f5', 
            borderRadius: '6px',
            fontSize: '12px'
          }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Text strong>taskID:</Text> {taskState.task_id}
              </div>
              <div>
                <Text strong>Serial number:</Text> {taskState.seq}
              </div>
              <div>
                <Text strong>Timestamp:</Text> {new Date(taskState.ts * 1000).toLocaleString()}
              </div>
              <div>
                <Text strong>Last updated:</Text> {new Date(taskState.last_updated).toLocaleString()}
              </div>
              {taskState.meta && (
                <div>
                  <Text strong>metadata:</Text> {JSON.stringify(taskState.meta, null, 2)}
                </div>
              )}
              <div>
                <Text strong>Connection status:</Text> 
                <Tag color={isConnected ? 'success' : 'error'} style={{ marginLeft: 8 }}>
                  {isConnected ? 'Connected' : 'Not connected'}
                </Tag>
                <Tag color={isSubscribed ? 'success' : 'default'} style={{ marginLeft: 4 }}>
                  {isSubscribed ? 'Subscribed' : 'Not subscribed'}
                </Tag>
              </div>
            </Space>
          </div>
        )}
      </Space>
    </Card>
  );
};

