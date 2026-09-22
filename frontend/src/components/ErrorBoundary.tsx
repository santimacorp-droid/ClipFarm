/**
 * React Error boundary component
 * Catch subcomponent JavaScript Error, log error information, and display degraded UI
 */

import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button, Card, Typography, Space, Collapse } from 'antd'
import { ReloadOutlined, BugOutlined, HomeOutlined } from '@ant-design/icons'
import { errorHandler } from '../utils/errorHandler'

const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showDetails?: boolean
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorId: string
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Update state Make the next render able to show degraded UI
    return {
      hasError: true,
      error,
      errorId: `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Record error information
    this.setState({ errorInfo })
    
    // Process error using error handler
    errorHandler.handleError(error, 'ReactErrorBoundary')
    
    // Call custom error handling function
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
    
    // Log detailed error information
    console.group('🚨 React Error Boundary')
    console.error('Error:', error)
    console.error('Error Info:', errorInfo)
    console.error('Error ID:', this.state.errorId)
    console.groupEnd()
  }

  handleReload = () => {
    // Clear error state
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    })
    
    // Refresh page
    window.location.reload()
  }

  handleGoHome = () => {
    // Clear error state
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    })
    
    // Go to home page
    window.location.href = '/'
  }

  handleReportError = () => {
    const { error, errorInfo, errorId } = this.state
    
    if (!error) return
    
    // Create error report
    const errorReport = {
      id: errorId,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo?.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      userId: localStorage.getItem('userId') || 'anonymous'
    }
    
    // Here you can send an error report to the server
    console.log('Error Report:', errorReport)
    
    // Display success message
    // message.success('Error report submitted. Thank you for your feedback! ')
  }

  render() {
    if (this.state.hasError) {
      // If there is a custom degradation UI, Use it
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      const { error, errorInfo, errorId } = this.state
      
      return (
        <div style={{ 
          minHeight: '100vh', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          padding: '20px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        }}>
          <Card 
            style={{ 
              maxWidth: '600px', 
              width: '100%',
              boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
              borderRadius: '12px'
            }}
          >
            <Result
              status="error"
              title="Page encountered an error"
              subTitle="Sorry, an unexpected error occurred on this page.: "
              extra={
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Space>
                    <Button 
                      type="primary" 
                      icon={<ReloadOutlined />} 
                      onClick={this.handleReload}
                    >
                      Refresh page
                    </Button>
                    <Button 
                      icon={<HomeOutlined />} 
                      onClick={this.handleGoHome}
                    >
                      Return to home page
                    </Button>
                  </Space>
                  
                  <Button 
                    type="link" 
                    icon={<BugOutlined />}
                    onClick={this.handleReportError}
                  >
                    Report this error
                  </Button>
                </Space>
              }
            />
            
            {/* Error details */}
            {this.props.showDetails && error && (
              <div style={{ marginTop: '24px' }}>
                <Title level={5}>Error details</Title>
                <Paragraph>
                  <Text code>Error ID: {errorId}</Text>
                </Paragraph>
                
                <Collapse size="small" defaultActiveKey={['1']}>
                  <Panel header="Error message" key="1">
                    <pre style={{ 
                      background: '#f5f5f5', 
                      padding: '12px', 
                      borderRadius: '4px',
                      fontSize: '12px',
                      overflow: 'auto',
                      maxHeight: '200px'
                    }}>
                      {error.message}
                    </pre>
                  </Panel>
                  
                  {error.stack && (
                    <Panel header="Error stack" key="2">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '12px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        overflow: 'auto',
                        maxHeight: '300px'
                      }}>
                        {error.stack}
                      </pre>
                    </Panel>
                  )}
                  
                  {errorInfo?.componentStack && (
                    <Panel header="Component stack" key="3">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '12px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        overflow: 'auto',
                        maxHeight: '300px'
                      }}>
                        {errorInfo.componentStack}
                      </pre>
                    </Panel>
                  )}
                </Collapse>
              </div>
            )}
            
            {/* Common solutions */}
            <div style={{ marginTop: '24px' }}>
              <Title level={5}>Common solutions</Title>
              <ul style={{ paddingLeft: '20px' }}>
                <li>Refresh page to retry</li>
                <li>Clear browser cache and Cookie</li>
                <li>Check network connection</li>
                <li>Try using another browser</li>
                <li>If the problem persists, please contact support</li>
              </ul>
            </div>
          </Card>
        </div>
      )
    }
    
    return this.props.children
  }
}

export default ErrorBoundary
