import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Card, Progress, Steps, Typography, Button, Alert, Space, Spin, message } from 'antd'
import { CheckCircleOutlined, LoadingOutlined, ExclamationCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { projectApi } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'

const { Content } = Layout
const { Title, Text } = Typography
const { Step } = Steps

interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

const ProcessingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [status, setStatus] = useState<ProcessingStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const steps = [
    { title: 'Outline Extraction', description: 'Extract structural outline from transcript' },
    { title: 'Time Localization', description: 'Locate timestamp ranges for topics from SRT' },
    { title: 'Content Scoring', description: 'Evaluate clip quality and viral potential' },
    { title: 'Title Generation', description: 'Generate catchy titles for highlight clips' },
    { title: 'Topic Clustering', description: 'Group clips into recommended collections' },
    { title: 'Video Cutting', description: 'Render highlight clips and collections via FFmpeg' }
  ]

  useEffect(() => {
    if (!id) return
    
    loadProject()
    const interval = setInterval(checkStatus, 2000) // Every2Check every second
    
    return () => clearInterval(interval)
  }, [id])

  const loadProject = async () => {
    if (!id) return
    
    try {
      const project = await projectApi.getProject(id)
      setCurrentProject(project)
      
      // If project is already complete, directly jump to detail page
      if (project.status === 'completed') {
        navigate(`/project/${id}`)
        return
      }
      
      // If project status is waiting for processing, begin processing
      if (project.status === 'pending') {
        await startProcessing()
      }
    } catch (error) {
      message.error('Failed to load project')
      console.error('Load project error:', error)
    } finally {
      setLoading(false)
    }
  }

  const startProcessing = async () => {
    if (!id) return
    
    try {
      await projectApi.startProcessing(id)
      message.success('Processing started')
    } catch (error) {
      message.error('Failed to start processing')
      console.error('Start processing error:', error)
    }
  }

  const checkStatus = async () => {
    if (!id) return
    
    try {
      const statusData = await projectApi.getProcessingStatus(id)
      setStatus(statusData)
      
      // If processing is complete, jump to project detail page
      if (statusData.status === 'completed') {
        message.success('🎉 Processing complete! Redirecting to results...')
        setTimeout(() => {
          navigate(`/project/${id}`)
        }, 2000)
      }
      
      // If processing fails, display detailed error information
      if (statusData.status === 'error') {
        const errorMsg = statusData.error_message || 'An unknown error occurred during processing'
        message.error(`Processing failed: ${errorMsg}`)
      }
      
    } catch (error: any) {
      console.error('Check status error:', error)
      
      // Provide different handling suggestions based on error type
      if (error.response?.status === 404) {
        message.error('Project not found or deleted')
        setTimeout(() => navigate('/'), 2000)
      } else if (error.code === 'ECONNABORTED') {
        message.warning('Connection timed out, retrying...')
      } else {
        message.error('Failed to fetch status, please refresh the page')
      }
    }
  }

  const getStepStatus = (stepIndex: number) => {
    if (!status) return 'wait'
    
    if (status.status === 'error') {
      return stepIndex < status.current_step ? 'finish' : 'error'
    }
    
    if (stepIndex < status.current_step) return 'finish'
    if (stepIndex === status.current_step) return 'process'
    return 'wait'
  }

  const getStepIcon = (stepIndex: number) => {
    const stepStatus = getStepStatus(stepIndex)
    
    if (stepStatus === 'finish') return <CheckCircleOutlined />
    if (stepStatus === 'process') return <LoadingOutlined />
    if (stepStatus === 'error') return <ExclamationCircleOutlined />
    return null
  }

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spin size="large" tip="Loading..." />
      </Content>
    )
  }

  return (
    <Content style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={2}>Processing Progress</Title>
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/')}
          >
            Back to Home
          </Button>
        </div>

        {currentProject && (
          <Card>
            <Title level={4}>{currentProject.name}</Title>
            <Text type="secondary">Project ID: {currentProject.id}</Text>
          </Card>
        )}

        {status?.status === 'error' && (
          <Alert
            message="Processing Failed"
            description={
              <div>
                <p>{status.error_message || 'An unknown error occurred during processing'}</p>
                <p style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
                  Possible causes: Unsupported format, corrupted file, network timeout, or AI provider error.
                </p>
              </div>
            }
            type="error"
            showIcon
            action={
              <Space>
                <Button size="small" onClick={() => window.location.reload()}>
                  Refresh
                </Button>
                <Button size="small" onClick={() => navigate('/')}>
                  Back to Home
                </Button>
              </Space>
            }
          />
        )}

        {status && status.status === 'processing' && (
          <Card title="Processing Progress">
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Text strong>Overall Progress</Text>
                  <Text>{Math.round(status.progress)}%</Text>
                </div>
                <Progress 
                  percent={status.progress} 
                  status="active"
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                />
              </div>

              <div>
                <Text strong>Current Step: </Text>
                <Text>{status.step_name}</Text>
              </div>

              <Steps 
                direction="vertical" 
                current={status.current_step}
                status="process"
              >
                {steps.map((step, index) => (
                  <Step
                    key={index}
                    title={step.title}
                    description={step.description}
                    status={getStepStatus(index)}
                    icon={getStepIcon(index)}
                  />
                ))}
              </Steps>
            </Space>
          </Card>
        )}

        {status?.status === 'completed' && (
          <Alert
            message="Processing Complete"
            description="Video processing finished successfully. Redirecting to project..."
            type="success"
            showIcon
          />
        )}
      </Space>
    </Content>
  )
}

export default ProcessingPage