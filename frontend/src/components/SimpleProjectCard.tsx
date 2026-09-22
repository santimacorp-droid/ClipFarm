/**
 * Simplified project card component - integrated progress system
 */

import React, { useState, useEffect } from 'react'
import { Card, Typography, Space, Button, Tag, Tooltip, Modal, message } from 'antd'
import { 
  PlayCircleOutlined, 
  EyeOutlined, 
  DeleteOutlined, 
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { SimpleProgressBar } from './SimpleProgressBar'
import { 
  useSimpleProgressStore, 
  isCompleted, 
  isFailed,
  SimpleProgress 
} from '../stores/useSimpleProgressStore'

const { Title, Text } = Typography

interface Project {
  id: string
  title: string
  description?: string
  status: string
  created_at: string
  updated_at: string
  video_path?: string
  srt_path?: string
  category?: string
}

interface SimpleProjectCardProps {
  project: Project
  onStartProcessing?: (projectId: string) => void
  onViewDetails?: (projectId: string) => void
  onDelete?: (projectId: string) => void
  onRetry?: (projectId: string) => void
}

export const SimpleProjectCard: React.FC<SimpleProjectCardProps> = ({
  project,
  onStartProcessing,
  onViewDetails,
  onDelete,
  onRetry
}) => {
  const navigate = useNavigate()
  const { getProgress, startPolling, stopPolling } = useSimpleProgressStore()
  const [showProgress, setShowProgress] = useState(false)
  
  const progress = getProgress(project.id)

  // Determine whether to display progress based on project status
  useEffect(() => {
    if (project.status === 'processing') {
      setShowProgress(true)
      // Start polling for this project's progress
      startPolling([project.id], 2000)
    } else {
      setShowProgress(false)
      stopPolling()
    }
  }, [project.status, project.id, startPolling, stopPolling])

  const handleStartProcessing = () => {
    if (onStartProcessing) {
      onStartProcessing(project.id)
    }
  }

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails(project.id)
    } else {
      navigate(`/project/${project.id}`)
    }
  }

  const handleDelete = () => {
    Modal.confirm({
      title: 'Confirm delete',
      content: `Confirm deletion of project "${project.title}" ? This action cannot be undone. `,
      okText: 'delete',
      okType: 'danger',
      cancelText: 'cancel',
      onOk: () => {
        if (onDelete) {
          onDelete(project.id)
        }
      }
    })
  }

  const handleRetry = () => {
    if (onRetry) {
      onRetry(project.id)
    }
  }

  // Get status icon and color
  const getStatusConfig = (status: string, progress?: SimpleProgress) => {
    if (progress && isFailed(progress.message)) {
      return {
        icon: <ExclamationCircleOutlined />,
        color: '#ff4d4f',
        text: 'Processing failed'
      }
    }
    
    if (progress && isCompleted(progress.stage)) {
      return {
        icon: <CheckCircleOutlined />,
        color: '#52c41a',
        text: 'Processing completed'
      }
    }
    
    if (status === 'processing' || (progress && !isCompleted(progress.stage))) {
      return {
        icon: <ReloadOutlined spin />,
        color: '#1890ff',
        text: 'processing'
      }
    }
    
    return {
      icon: <PlayCircleOutlined />,
      color: '#666666',
      text: 'Waiting to process'
    }
  }

  const statusConfig = getStatusConfig(project.status, progress || undefined)
  const canStart = project.status === 'pending' || project.status === 'failed'
  const canRetry = project.status === 'failed' || (progress && isFailed(progress.message))

  return (
    <Card
      hoverable
      style={{ margin: '8px 0' }}
      actions={[
        canStart && (
          <Tooltip title="Starting processing">
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />}
              onClick={handleStartProcessing}
            >
              Starting processing
            </Button>
          </Tooltip>
        ),
        canRetry && (
          <Tooltip title="retry">
            <Button 
              icon={<ReloadOutlined />}
              onClick={handleRetry}
            >
              retry
            </Button>
          </Tooltip>
        ),
        <Tooltip title="View details">
          <Button 
            icon={<EyeOutlined />}
            onClick={handleViewDetails}
          >
            View details
          </Button>
        </Tooltip>,
        <Tooltip title="Delete project">
          <Button 
            danger 
            icon={<DeleteOutlined />}
            onClick={handleDelete}
          >
            delete
          </Button>
        </Tooltip>
      ].filter(Boolean)}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* Project title and status */}
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Title level={5} style={{ margin: 0, flex: 1 }}>
            {project.title}
          </Title>
          <Tag 
            color={statusConfig.color} 
            icon={statusConfig.icon}
            style={{ margin: 0 }}
          >
            {statusConfig.text}
          </Tag>
        </Space>

        {/* Project description */}
        {project.description && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {project.description}
          </Text>
        )}

        {/* Category tags */}
        {project.category && (
          <Tag color="blue" style={{ fontSize: '11px' }}>
            {project.category}
          </Tag>
        )}

        {/* progress bar */}
        {showProgress && (
          <SimpleProgressBar
            projectId={project.id}
            autoStart={false} // already existsuseEffectin progress
            showDetails={true}
            onProgressUpdate={(progress) => {
              // If processing is complete, update display status
              if (isCompleted(progress.stage)) {
                setShowProgress(false)
                message.success('Project processing completed! ')
              } else if (isFailed(progress.message)) {
                message.error('Project processing failed! ')
              }
            }}
          />
        )}

        {/* Time information */}
        <Space style={{ fontSize: '11px', color: '#999' }}>
          <Text type="secondary">
            create: {new Date(project.created_at).toLocaleDateString()}
          </Text>
          <Text type="secondary">
            update: {new Date(project.updated_at).toLocaleDateString()}
          </Text>
        </Space>
      </Space>
    </Card>
  )
}
