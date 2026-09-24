import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Card, Progress, Steps, Typography, Button, Alert, Space, Spin, message, Tag, Row, Col } from 'antd'
import { 
  CheckCircleOutlined, 
  LoadingOutlined, 
  ExclamationCircleOutlined, 
  ArrowLeftOutlined,
  FolderOpenOutlined,
  RedoOutlined,
  CodeOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'
import { projectApi, ProcessingStatus } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { Step } = Steps

const PIPELINE_STEPS = [
  { title: 'Audio Transcription & Setup', description: 'Transcribe speech with Whisper / cloud ASR and calibrate duration' },
  { title: 'Key Moments Discovery', description: 'AI transcript analysis and candidate moment extraction' },
  { title: 'Timeline & Speech Localization', description: 'Align exact speech timestamps and sentence boundaries' },
  { title: 'Content & Virality Scoring', description: 'Hook strength and audience retention evaluation' },
  { title: 'Title & Hook Generation', description: 'Crafting viral social titles and hook banners' },
  { title: 'Highlight Clustering', description: 'Selecting top highlights and thematic collections' },
  { title: 'Video Formatting & Cutting', description: 'Smart 9:16 vertical re-framing and FFmpeg clip rendering' }
]

export const ProcessingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [status, setStatus] = useState<ProcessingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)
  const [revealing, setRevealing] = useState(false)
  const [showLogs, setShowLogs] = useState(true)

  const isFinishedRef = useRef(false)
  const isStartingRef = useRef(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const logTerminalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs to bottom as they arrive
  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight
    }
  }, [status?.recent_logs])

  useEffect(() => {
    if (!id) return
    isFinishedRef.current = false
    isStartingRef.current = false

    loadProject()
    intervalRef.current = setInterval(checkStatus, 1500)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [id])

  const loadProject = async () => {
    if (!id) return

    try {
      const project = await projectApi.getProject(id)
      setCurrentProject(project)

      if (project.status === 'completed') {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        navigate(`/project/${id}`)
        return
      }

      if (project.status === 'pending' && !isStartingRef.current) {
        const downloadStatus = (project.processing_config as any)?.download_status
        if (downloadStatus !== 'downloading') {
          isStartingRef.current = true
          await startProcessing()
        }
      }
    } catch (error) {
      console.error('Load project error:', error)
      message.error('Failed to load project details')
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
      console.error('Start processing error:', error)
      message.error('Failed to start processing pipeline')
    }
  }

  const handleRetry = async () => {
    if (!id) return
    setRetrying(true)
    try {
      isFinishedRef.current = false
      await projectApi.startProcessing(id)
      message.success('Processing restarted')
      // Resume polling
      if (!intervalRef.current) {
        intervalRef.current = setInterval(checkStatus, 1500)
      }
      checkStatus()
    } catch (err: any) {
      console.error('Retry failed:', err)
      message.error(err.response?.data?.detail || 'Failed to retry processing')
    } finally {
      setRetrying(false)
    }
  }

  const handleRevealFolder = async () => {
    if (!id) return
    setRevealing(true)
    try {
      await projectApi.revealProjectFolder(id)
      message.success('Opened project directory in file manager')
    } catch (err) {
      message.error('Failed to open project folder')
    } finally {
      setRevealing(false)
    }
  }

  const checkStatus = async () => {
    if (!id || isFinishedRef.current) return

    try {
      const statusData = await projectApi.getProcessingStatus(id)
      setStatus(statusData)

      if (statusData.status === 'completed') {
        isFinishedRef.current = true
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        message.success('🎉 Processing complete! Redirecting to studio...')
        setTimeout(() => {
          navigate(`/project/${id}`)
        }, 1200)
        return
      }

      if (statusData.status === 'error' || statusData.status === 'failed') {
        isFinishedRef.current = true
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        const errorMsg = statusData.error_message || 'Video pipeline encountered an error'
        message.error(`Processing failed: ${errorMsg}`)
        return
      }

    } catch (error: any) {
      console.error('Check status error:', error)
      if (error.response?.status === 404) {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        message.error('Project not found')
        setTimeout(() => navigate('/'), 2000)
      }
    }
  }

  const getStepStatus = (stepIndex: number) => {
    if (!status) return 'wait'
    const curStep = status.current_step ?? 0

    if (status.status === 'error' || status.status === 'failed') {
      return stepIndex < curStep ? 'finish' : (stepIndex === curStep ? 'error' : 'wait')
    }

    if (status.status === 'completed') {
      return 'finish'
    }

    if (stepIndex < curStep) return 'finish'
    if (stepIndex === curStep) return 'process'
    return 'wait'
  }

  const getStepIcon = (stepIndex: number) => {
    const stepStatus = getStepStatus(stepIndex)
    if (stepStatus === 'finish') return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    if (stepStatus === 'process') return <LoadingOutlined style={{ color: '#00f2fe' }} />
    if (stepStatus === 'error') return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
    return null
  }

  const formatElapsed = (sec: number = 0) => {
    const m = Math.floor(sec / 60)
    const s = Math.round(sec % 60)
    if (m === 0) return `${s}s`
    return `${m}m ${s}s`
  }

  if (loading) {
    return (
      <Content style={{ padding: '48px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spin size="large" tip="Loading project pipeline..." />
      </Content>
    )
  }

  const progressPercent = Math.min(100, Math.max(0, Math.round(status?.progress || (status?.status === 'pending' ? 5 : 0))))

  return (
    <Content style={{ padding: '28px 36px', maxWidth: '1060px', margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Header navigation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <Title level={2} style={{ margin: '0 0 4px 0', color: '#fff' }}>
              <ThunderboltOutlined style={{ color: '#00f2fe', marginRight: '8px' }} />
              Video Processing Studio
            </Title>
            <Text type="secondary" style={{ fontSize: '13px' }}>
              Real-time multi-stage AI clipping, transcription, scoring, and 9:16 vertical video export
            </Text>
          </div>
          <Space>
            <Button icon={<FolderOpenOutlined />} onClick={handleRevealFolder} loading={revealing}>
              Project Folder
            </Button>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              Back to Home
            </Button>
          </Space>
        </div>

        {/* Project Card */}
        {currentProject && (
          <Card 
            size="small" 
            style={{ 
              background: 'rgba(255, 255, 255, 0.03)', 
              borderColor: 'var(--ac-line)',
              borderRadius: '10px'
            }}
          >
            <Row align="middle" justify="space-between">
              <Col>
                <Text strong style={{ fontSize: '15px', color: '#fff' }}>{currentProject.name}</Text>
                <div style={{ marginTop: '2px' }}>
                  <Text type="secondary" style={{ fontSize: '12px' }}>ID: {currentProject.id}</Text>
                  {status?.elapsed_seconds !== undefined && status.elapsed_seconds > 0 && (
                    <Text type="secondary" style={{ fontSize: '12px', marginLeft: '12px' }}>
                      <ClockCircleOutlined /> Running for: {formatElapsed(status.elapsed_seconds)}
                    </Text>
                  )}
                </div>
              </Col>
              <Col>
                <Space>
                  {status?.is_alive !== false && status?.status === 'processing' && (
                    <Tag color="cyan" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <span style={{
                        width: '7px',
                        height: '7px',
                        borderRadius: '50%',
                        background: '#52c41a',
                        display: 'inline-block',
                        boxShadow: '0 0 6px #52c41a'
                      }} />
                      Engine Active
                    </Tag>
                  )}
                  <Tag color={(status?.status === 'error' || status?.status === 'failed') ? 'error' : status?.status === 'completed' ? 'success' : 'processing'}>
                    {status?.status ? status.status.toUpperCase() : 'QUEUED'}
                  </Tag>
                </Space>
              </Col>
            </Row>
          </Card>
        )}

        {/* Error Alert with Recovery */}
        {(status?.status === 'error' || status?.status === 'failed') && (
          <Alert
            message="Processing Pipeline Interrupted"
            description={
              <div>
                <p style={{ margin: '4px 0 8px', color: '#ff7875', fontWeight: 500 }}>
                  {status.error_message || 'An error occurred during video processing.'}
                </p>
                <Paragraph type="secondary" style={{ fontSize: '12px', marginBottom: '12px' }}>
                  Possible causes: Audio without speech, invalid subtitle format, network timeout during cloud transcription, or corrupted video frames. You can safely retry or inspect the detailed logs below.
                </Paragraph>
                <Space>
                  <Button type="primary" danger icon={<RedoOutlined />} onClick={handleRetry} loading={retrying}>
                    Retry Processing
                  </Button>
                  <Button icon={<FolderOpenOutlined />} onClick={handleRevealFolder}>
                    Open Output Directory
                  </Button>
                </Space>
              </div>
            }
            type="error"
            showIcon
          />
        )}

        {/* Main Processing Progress Card */}
        {status && (status.status === 'processing' || status.status === 'pending') && (
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#fff' }}>Pipeline Progress</span>
                <span style={{ fontSize: '18px', fontWeight: 700, color: '#00f2fe' }}>
                  {progressPercent}%
                </span>
              </div>
            }
            style={{ borderRadius: '12px', borderColor: 'var(--ac-line)' }}
          >
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              {/* Overall Progress Bar */}
              <div>
                <Progress 
                  percent={progressPercent}
                  status="active"
                  strokeColor={{
                    '0%': '#1890ff',
                    '50%': '#00f2fe',
                    '100%': '#52c41a',
                  }}
                  strokeWidth={12}
                  style={{ marginBottom: '8px' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                  <Text strong style={{ color: '#fff', fontSize: '13px' }}>
                    Current Action: <span style={{ color: '#00f2fe' }}>{status.step_name || 'Processing...'}</span>
                  </Text>
                  {status.substep && (
                    <Tag color="geekblue" style={{ fontSize: '11px' }}>
                      {status.substep}
                    </Tag>
                  )}
                </div>
              </div>

              {/* Vertical Steps View */}
              <Steps 
                direction="vertical" 
                current={status.current_step || 0}
                style={{ marginTop: '8px' }}
              >
                {PIPELINE_STEPS.map((step, index) => (
                  <Step
                    key={index}
                    title={<span style={{ color: '#fff', fontWeight: 600 }}>{step.title}</span>}
                    description={<span style={{ color: 'var(--ac-sub)', fontSize: '12px' }}>{step.description}</span>}
                    status={getStepStatus(index)}
                    icon={getStepIcon(index)}
                  />
                ))}
              </Steps>
            </Space>
          </Card>
        )}

        {/* Completed Alert */}
        {status?.status === 'completed' && (
          <Alert
            message="Processing Completed Successfully"
            description="All viral highlights, captions, and 9:16 vertical clips have been rendered and saved. Redirecting to studio results..."
            type="success"
            showIcon
            action={
              <Button type="primary" onClick={() => navigate(`/project/${id}`)}>
                View Results Now
              </Button>
            }
          />
        )}

        {/* Real-time Streaming Log Terminal */}
        <Card
          size="small"
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', color: 'var(--ac-sub)' }}>
                <CodeOutlined style={{ marginRight: '6px' }} />
                Real-Time Execution Logs
              </span>
              <Button 
                type="link" 
                size="small" 
                onClick={() => setShowLogs(!showLogs)} 
                style={{ padding: 0, fontSize: '12px', color: '#00f2fe' }}
              >
                {showLogs ? 'Hide Console' : 'Show Console'}
              </Button>
            </div>
          }
          style={{ 
            background: '#090d16', 
            borderColor: 'var(--ac-line)', 
            borderRadius: '10px' 
          }}
        >
          {showLogs && (
            <div 
              ref={logTerminalRef}
              style={{
                maxHeight: '220px',
                overflowY: 'auto',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                fontSize: '12px',
                lineHeight: '1.6',
                color: '#7ee787',
                padding: '8px',
                background: 'rgba(0, 0, 0, 0.4)',
                borderRadius: '6px'
              }}
            >
              {status?.recent_logs && status.recent_logs.length > 0 ? (
                status.recent_logs.map((line, idx) => (
                  <div key={idx} style={{ wordBreak: 'break-word' }}>
                    <span style={{ color: '#8b949e', marginRight: '8px' }}>›</span>
                    {line}
                  </div>
                ))
              ) : (
                <div style={{ color: '#8b949e', fontStyle: 'italic' }}>
                  Awaiting engine output... logs will stream here as the pipeline executes.
                </div>
              )}
            </div>
          )}
        </Card>
      </Space>
    </Content>
  )
}

export default ProcessingPage