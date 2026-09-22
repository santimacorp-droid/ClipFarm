import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Typography, 
  Spin, 
  Empty,
  message,
  Segmented
} from 'antd'
import { useNavigate } from 'react-router-dom'
import ProjectCard from '../components/ProjectCard'
import FileUpload from '../components/FileUpload'

import { projectApi } from '../services/api'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { Project, useProjectStore } from '../store/useProjectStore'
import { useProjectPolling } from '../hooks/useProjectPolling'

const { Content } = Layout
const { Title, Text } = Typography

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const { projects, setProjects, deleteProject, loading, setLoading } = useProjectStore()
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Use project pollingHook
  const { startPolling: startProjectPolling, stopPolling: stopProjectPolling } = useProjectPolling({
    onProjectsUpdate: (updatedProjects) => {
      setProjects(updatedProjects || [])
    },
    enabled: true,
    interval: 30000 // 30Poll once per second to reduce frequent requests
  })

  // Global safety: stop progress polling only when there are truly no active/downloading projects
  useEffect(() => {
    const hasActive = projects.some(p => p.status === 'processing' || p.status === 'pending')
    if (hasActive) {
      startProjectPolling()
    } else {
      stopProjectPolling()
      try {
        const { stopPolling, clearAllProgress } = useSimpleProgressStore.getState()
        stopPolling()
        clearAllProgress()
        console.log('No active projects, stopped global progress polling')
      } catch (e) {
        console.warn('Issue while stopping global progress polling:', e)
      }
    }
  }, [projects.map(p => `${p.id}:${p.status}`).join(',')])

  useEffect(() => {
    // Lazy load items to avoid immediately making many requests on startup
    const timer = setTimeout(() => {
      loadProjects()
    }, 1000) // Delay1Seconds loading
    
    return () => clearTimeout(timer)
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      // From backendAPIGet actual project data
      const projects = await projectApi.getProjects()
      // EnsureprojectsIs array type
      const safeProjects = Array.isArray(projects) ? projects : []
      setProjects(safeProjects)
    } catch (error) {
      message.error('Failed to load projects')
      console.error('Load projects error:', error)
      // IfAPICall failed, set empty array
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteProject = async (id: string) => {
    try {
      await projectApi.deleteProject(id)
      deleteProject(id)
      message.success('Project deleted successfully')
    } catch (error) {
      message.error('Failed to delete project')
      console.error('Delete project error:', error)
    }
  }

  // By ProjectCard In「User manually clicks retry」And call when the retry request has succeeded. 
  // ProjectCard.handleRetry Already sent start/retryProcessing Request handles only
  // Hint + Refresh list, do not send another retry request (would stack with card's own request and create)
  // loadProjects→Re-mount→Automatic start loop). 
  const handleRetryProject = async () => {
    message.success('Retrying project processing...')
    try {
      await loadProjects()
    } catch (error) {
      console.error('Refresh after retry error:', error)
    }
  }

  const handleProjectCardClick = (project: Project) => {
    // Projects in importing state cannot click to enter detail page
    if (project.status === 'pending') {
      message.warning('Project is currently importing, please wait...')
      return
    }
    
    // Other states can normally enter detail page
    navigate(`/project/${project.id}`)
  }

  const totalCount = projects.length
  const completedCount = projects.filter(p => p.status === 'completed').length
  const processingCount = projects.filter(p => p.status === 'processing' || p.status === 'pending').length
  const failedCount = projects.filter(p => p.status === 'error' || p.status === 'failed').length

  const filteredProjects = (projects || [])
    .filter(project => {
      const matchesStatus = statusFilter === 'all' || project.status === statusFilter
      return matchesStatus
    })
    .sort((a, b) => {
      // Sort by creation date descending, most recent first
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  return (
    <Layout style={{
      minHeight: '100vh',
      background: 'var(--ac-bg)'
    }}>
      <Content style={{ padding: '36px 48px 56px', position: 'relative' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto', position: 'relative' }}>
          {/* Studio Hero Header */}
          <div style={{ textAlign: 'center', marginBottom: '32px', marginTop: '4px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '14px', marginBottom: '10px' }}>
              <img
                src="/logo.png"
                alt="ClipFarm Logo"
                style={{ width: '56px', height: '56px', borderRadius: '12px', boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)', objectFit: 'contain' }}
              />
              <div style={{ textAlign: 'left' }}>
                <Title level={2} style={{ margin: 0, letterSpacing: '-0.5px', color: 'var(--ac-ink)', fontSize: '24px' }}>
                  ClipFarm Studio
                </Title>
                <Text style={{ fontSize: '13.5px', color: 'var(--ac-sub)', fontWeight: 500 }}>
                  AI Short-Form Video Studio · High-impact clips from podcasts, interviews & long videos
                </Text>
              </div>
            </div>

            {/* Feature Capability Badges */}
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px', marginTop: '10px' }}>
              {[
                { label: '⚡ AI Viral Moments', color: '#faad14' },
                { label: '📱 9:16 Smart Framing', color: '#52c41a' },
                { label: '🔥 Color Emoji Hooks', color: '#ff4d4f' },
                { label: '🎬 Multiplatform CTAs (TikTok, IG, Shorts, FB)', color: '#1890ff' },
              ].map(badge => (
                <span
                  key={badge.label}
                  style={{
                    padding: '3px 12px',
                    borderRadius: '999px',
                    fontSize: '11.5px',
                    fontWeight: 600,
                    background: 'var(--ac-line-2)',
                    color: 'var(--ac-ink)',
                    border: '1px solid var(--ac-line)',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                  }}
                >
                  {badge.label}
                </span>
              ))}
            </div>
          </div>

          {/* File upload area */}
          <div style={{ 
            marginBottom: '48px',
            display: 'flex',
            justifyContent: 'center'
          }}>
            <div style={{ width: '100%', maxWidth: '820px' }}>
              <div style={{ fontSize: '13px', color: 'var(--ac-muted)', margin: '0 4px 14px', letterSpacing: '0.2px' }}>
                Paste YouTube video link to extract the sharpest 60-second highlight moments:
              </div>
              <div style={{
                background: 'var(--ac-card)',
                borderRadius: '16px',
                border: '1px solid var(--ac-line)',
                padding: '18px',
                boxShadow: 'var(--ac-shadow)'
              }}>
              {/* File Upload */}
              <FileUpload onUploadSuccess={async () => {
                // After processing is complete, refresh project list
                await loadProjects()
                message.success('Project created, processing started...')
              }} />
              </div>
            </div>
          </div>

          {/* Project management area */}
          <div style={{
            background: 'transparent',
            padding: '0',
            marginBottom: '32px'
          }}>
            {/* Project list title area */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '14px',
              marginTop: '44px',
              marginBottom: '20px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Title
                  level={3}
                  style={{ margin: 0, color: 'var(--ac-ink)', fontSize: '18px', fontWeight: 600 }}
                >
                  Projects
                </Title>
                <span style={{ 
                  background: 'var(--ac-line-2)', 
                  color: 'var(--ac-sub)', 
                  border: '1px solid var(--ac-line)',
                  padding: '2px 8px', 
                  borderRadius: '999px', 
                  fontSize: '12px',
                  fontWeight: 600
                }}>
                  {filteredProjects.length}
                </span>
              </div>
              
              {/* Status filter Segmented tabs */}
              <Segmented
                value={statusFilter}
                onChange={(val) => setStatusFilter(String(val))}
                options={[
                  { label: `All (${totalCount})`, value: 'all' },
                  { label: `Completed (${completedCount})`, value: 'completed' },
                  { label: `Processing (${processingCount})`, value: 'processing' },
                  { label: `Failed (${failedCount})`, value: 'error' },
                ]}
                size="middle"
              />
            </div>

            {/* Project list content */}
             <div>
               {loading ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '72px 0',
                   background: 'var(--ac-card)',
                   borderRadius: '16px',
                   border: '1px solid var(--ac-line)'
                 }}>
                   <Spin size="large" />
                   <div style={{ marginTop: '18px', color: 'var(--ac-muted)', fontSize: '14px' }}>
                     Loading projects…
                   </div>
                 </div>
               ) : filteredProjects.length === 0 ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '72px 0',
                   background: 'var(--ac-card)',
                   borderRadius: '16px',
                   border: '1px solid var(--ac-line)'
                 }}>
                   <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description={
                       <div>
                         <Text type="secondary">
                           {projects.length === 0 ? 'No projects yet. Create your first project using the import box above.' : 'No matching projects found'}
                         </Text>
                       </div>
                     }
                   />
                 </div>
               ) : (
                 <div style={{
                   display: 'grid',
                   gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                   gap: '24px',
                   justifyContent: 'start'
                 }}>
                   {filteredProjects.map((project: Project) => (
                     <div key={project.id} style={{ position: 'relative', zIndex: 1 }}>
                       <ProjectCard 
                         project={project} 
                         onDelete={handleDeleteProject}
                         onRetry={() => handleRetryProject()}
                         onClick={() => handleProjectCardClick(project)}
                       />
                     </div>
                   ))}
                 </div>
               )}
             </div>
           </div>
         </div>
      </Content>
    </Layout>
  )
}

export default HomePage