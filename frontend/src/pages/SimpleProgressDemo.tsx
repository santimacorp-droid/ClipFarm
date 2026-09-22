/**
 * Simplified progress system demo page
 */

import React, { useState } from 'react'
import { 
  Card, 
  Typography, 
  Space, 
  Button, 
  Row, 
  Col, 
  Divider, 
  message,
  Input,
  Tag,
  Select
} from 'antd'
import { 
  PlayCircleOutlined, 
  StopOutlined, 
  ReloadOutlined,
  PlusOutlined
} from '@ant-design/icons'
import { BatchProgressBar } from '../components/SimpleProgressBar'
import { SimpleProjectCard } from '../components/SimpleProjectCard'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

const { Title, Text, Paragraph } = Typography
const { Option } = Select

// Simulated project data
const mockProjects = [
  {
    id: 'demo-project-1',
    title: 'AITechnology analysis video',
    description: 'Deeply analyzing artificial intelligence technology development process',
    status: 'pending',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    category: 'knowledge'
  },
  {
    id: 'demo-project-2', 
    title: 'Startup experience sharing',
    description: 'Share the ups and downs of starting up a business',
    status: 'processing',
    created_at: '2024-01-14T15:30:00Z',
    updated_at: '2024-01-15T09:45:00Z',
    category: 'business'
  },
  {
    id: 'demo-project-3',
    title: 'Game review video',
    description: 'In‑depth game review',
    status: 'completed',
    created_at: '2024-01-13T20:15:00Z',
    updated_at: '2024-01-14T16:20:00Z',
    category: 'entertainment'
  }
]

export const SimpleProgressDemo: React.FC = () => {
  const { 
    startPolling, 
    stopPolling, 
    isPolling, 
    getAllProgress,
    clearAllProgress 
  } = useSimpleProgressStore()

  const [projects, setProjects] = useState(mockProjects)
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([])
  const [pollingInterval, setPollingInterval] = useState(2000)
  const [newProjectId, setNewProjectId] = useState('')

  // Simulating start processing project
  const handleStartProcessing = (projectId: string) => {
    setProjects(prev => prev.map(p => 
      p.id === projectId ? { ...p, status: 'processing' } : p
    ))
    message.success(`Starting to process project: ${projectId}`)
  }

  // View simulation details
  const handleViewDetails = (projectId: string) => {
    message.info(`View project details: ${projectId}`)
  }

  // Simulate deleting project
  const handleDelete = (projectId: string) => {
    setProjects(prev => prev.filter(p => p.id !== projectId))
    message.success(`Delete project: ${projectId}`)
  }

  // Simulate retrying project
  const handleRetry = (projectId: string) => {
    setProjects(prev => prev.map(p => 
      p.id === projectId ? { ...p, status: 'processing' } : p
    ))
    message.success(`Retry project: ${projectId}`)
  }

  // Add new project
  const handleAddProject = () => {
    if (!newProjectId.trim()) {
      message.warning('Please enter projectID')
      return
    }

    const newProject = {
      id: newProjectId,
      title: `New project ${newProjectId}`,
      description: 'This is a newly added demo project',
      status: 'pending' as const,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      category: 'default'
    }

    setProjects(prev => [...prev, newProject])
    setNewProjectId('')
    message.success(`Add project: ${newProjectId}`)
  }

  // Start polling selected projects
  const handleStartPolling = () => {
    if (selectedProjectIds.length === 0) {
      message.warning('Please select the project to poll')
      return
    }
    startPolling(selectedProjectIds, pollingInterval)
    message.success(`Start polling ${selectedProjectIds.length} projects`)
  }

  // Stopping polling
  const handleStopPolling = () => {
    stopPolling()
    message.info('Stopping polling')
  }

  // Clear all progress
  const handleClearProgress = () => {
    clearAllProgress()
    message.success('Clear all progress data')
  }

  const allProgress = getAllProgress()

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>Simplified progress system demo</Title>
      
      <Paragraph>
        This is a simplified progress system demonstration based on fixed phases and polling.6The system usesAPIGet latest progress. 
      </Paragraph>

      <Divider />

      {/* Control panel */}
      <Card title="Control panel" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Row gutter={16}>
            <Col span={8}>
              <Text strong>Polling interval:</Text>
              <Select
                value={pollingInterval}
                onChange={setPollingInterval}
                style={{ width: '100%', marginTop: '8px' }}
              >
                <Option value={1000}>1seconds</Option>
                <Option value={2000}>2seconds</Option>
                <Option value={3000}>3seconds</Option>
                <Option value={5000}>5seconds</Option>
              </Select>
            </Col>
            <Col span={8}>
              <Text strong>Polling status:</Text>
              <div style={{ marginTop: '8px' }}>
                <Tag color={isPolling ? 'green' : 'red'}>
                  {isPolling ? 'Polling' : 'Not yet polling'}
                </Tag>
              </div>
            </Col>
            <Col span={8}>
              <Text strong>Progress data:</Text>
              <div style={{ marginTop: '8px' }}>
                <Tag color="blue">
                  {Object.keys(allProgress).length} projects
                </Tag>
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Space>
                <Button 
                  type="primary" 
                  icon={<PlayCircleOutlined />}
                  onClick={handleStartPolling}
                  disabled={isPolling}
                >
                  Start polling
                </Button>
                <Button 
                  icon={<StopOutlined />}
                  onClick={handleStopPolling}
                  disabled={!isPolling}
                >
                  Stopping polling
                </Button>
                <Button 
                  icon={<ReloadOutlined />}
                  onClick={handleClearProgress}
                >
                  Clear progress
                </Button>
              </Space>
            </Col>
            <Col span={12}>
              <Space>
                <Input
                  placeholder="Enter new projectID"
                  value={newProjectId}
                  onChange={(e) => setNewProjectId(e.target.value)}
                  onPressEnter={handleAddProject}
                />
                <Button 
                  type="dashed" 
                  icon={<PlusOutlined />}
                  onClick={handleAddProject}
                >
                  Add project
                </Button>
              </Space>
            </Col>
          </Row>

          <Row>
            <Col span={24}>
              <Text strong>Select the project to poll:</Text>
              <div style={{ marginTop: '8px' }}>
                <Select
                  mode="multiple"
                  placeholder="Select project"
                  value={selectedProjectIds}
                  onChange={setSelectedProjectIds}
                  style={{ width: '100%' }}
                >
                  {projects.map(project => (
                    <Option key={project.id} value={project.id}>
                      {project.title} ({project.status})
                    </Option>
                  ))}
                </Select>
              </div>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* Batch progress display */}
      {selectedProjectIds.length > 0 && (
        <Card title="Batch progress display" style={{ marginBottom: '24px' }}>
          <BatchProgressBar
            projectIds={selectedProjectIds}
            autoStart={false}
            pollingInterval={pollingInterval}
            showDetails={true}
            onProgressUpdate={(projectId, progress) => {
              console.log(`Project ${projectId} Progress update:`, progress)
            }}
          />
        </Card>
      )}

      {/* Project card list */}
      <Card title="Project list">
        <Row gutter={[16, 16]}>
          {projects.map(project => (
            <Col span={24} key={project.id}>
              <SimpleProjectCard
                project={project}
                onStartProcessing={handleStartProcessing}
                onViewDetails={handleViewDetails}
                onDelete={handleDelete}
                onRetry={handleRetry}
              />
            </Col>
          ))}
        </Row>
      </Card>

      {/* Current progress data */}
      {Object.keys(allProgress).length > 0 && (
        <Card title="Current progress data" style={{ marginTop: '24px' }}>
          <pre style={{ 
            background: '#f5f5f5', 
            padding: '12px', 
            borderRadius: '4px',
            fontSize: '12px',
            maxHeight: '300px',
            overflow: 'auto'
          }}>
            {JSON.stringify(allProgress, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  )
}
