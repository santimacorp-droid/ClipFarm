import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Typography, 
  Spin, 
  Empty,
  message,
  Segmented,
  Button,
  Popconfirm,
  Space
} from 'antd'
import { 
  CheckSquareOutlined, 
  DeleteOutlined, 
  CloseOutlined 
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import ProjectCard from '../components/ProjectCard'
import FileUpload from '../components/FileUpload'

import { projectApi } from '../services/api'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { Project, useProjectStore } from '../store/useProjectStore'
import { useProjectPolling } from '../hooks/useProjectPolling'
import { normalizeProjectStatus } from '../utils/statusUtils'

const { Content } = Layout
const { Title, Text } = Typography

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const { projects, setProjects, deleteProject, deleteProjects, loading, setLoading } = useProjectStore()
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [isSelectMode, setIsSelectMode] = useState<boolean>(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [isBatchDeleting, setIsBatchDeleting] = useState<boolean>(false)

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
    loadProjects()
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
      setSelectedIds(prev => {
        if (!prev.has(id)) return prev
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      message.success('Project deleted successfully')
    } catch (error) {
      message.error('Failed to delete project')
      console.error('Delete project error:', error)
    }
  }

  const handleToggleSelect = (id: string, select: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (select) {
        next.add(id)
      } else {
        next.delete(id)
      }
      if (next.size > 0 && !isSelectMode) {
        setIsSelectMode(true)
      }
      return next
    })
  }

  const handleSelectAll = (filteredIds: string[]) => {
    const allSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.has(id))
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (allSelected) {
        filteredIds.forEach(id => next.delete(id))
      } else {
        filteredIds.forEach(id => next.add(id))
      }
      return next
    })
  }

  const handleExitSelectMode = () => {
    setIsSelectMode(false)
    setSelectedIds(new Set())
  }

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return
    const idsToDelete = Array.from(selectedIds)
    setIsBatchDeleting(true)
    try {
      const res = await projectApi.batchDeleteProjects(idsToDelete)
      deleteProjects(idsToDelete)
      message.success(`Successfully deleted ${res.count ?? idsToDelete.length} projects`)
      setSelectedIds(new Set())
      setIsSelectMode(false)
    } catch (error) {
      message.error('Failed to delete selected projects')
      console.error('Batch delete error:', error)
    } finally {
      setIsBatchDeleting(false)
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
    // If project is currently importing or processing, navigate to processing stepper
    if (project.status === 'processing' || project.status === 'pending') {
      navigate(`/processing/${project.id}`)
      return
    }
    
    // Completed or review states navigate to project studio detail page
    navigate(`/project/${project.id}`)
  }

  const totalCount = projects.length
  const completedCount = projects.filter(p => normalizeProjectStatus(p.status) === 'completed').length
  const processingCount = projects.filter(p => {
    const s = normalizeProjectStatus(p.status)
    return s === 'processing' || s === 'pending'
  }).length
  const failedCount = projects.filter(p => normalizeProjectStatus(p.status) === 'failed').length

  const filteredProjects = (projects || [])
    .filter(project => {
      if (statusFilter === 'all') return true
      const s = normalizeProjectStatus(project.status)
      if (statusFilter === 'completed') return s === 'completed'
      if (statusFilter === 'processing') return s === 'processing' || s === 'pending'
      if (statusFilter === 'failed' || statusFilter === 'error') return s === 'failed'
      return s === statusFilter
    })
    .sort((a, b) => {
      // Sort by creation date descending, most recent first
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
      return timeB - timeA
    })

  const filteredIds = filteredProjects.map(p => p.id)
  const allFilteredSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.has(id))

  return (
    <Layout style={{
      minHeight: '100vh',
      background: 'var(--ac-bg)'
    }}>
      <Content style={{ padding: '36px 48px 56px', position: 'relative' }}>
        <div style={{ maxWidth: '1240px', margin: '0 auto', position: 'relative' }}>
          {/* Studio Hero Header */}
          <div style={{ textAlign: 'center', marginBottom: '28px', marginTop: '12px' }}>
            <Title level={2} style={{ margin: '0 0 8px 0', letterSpacing: '-0.5px', color: 'var(--ac-ink)', fontSize: '26px', fontWeight: 700 }}>
              Turn Long Videos into Viral Short Clips
            </Title>
            <Text style={{ fontSize: '14px', color: 'var(--ac-sub)', fontWeight: 400, maxWidth: '640px', display: 'inline-block' }}>
              Automatic AI scene detection, smart 9:16 vertical re-framing, animated captions, and multiplatform hooks.
            </Text>

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
                Upload local videos or paste YouTube video links to extract the sharpest highlight moments:
              </div>
              <div style={{
                background: 'var(--ac-card)',
                borderRadius: '16px',
                border: '1px solid var(--ac-line)',
                padding: '18px',
                boxShadow: 'var(--ac-shadow)'
              }}>
              {/* File Upload */}
              <FileUpload onUploadSuccess={async (newId?: string) => {
                await loadProjects()
                message.success('Project created! Initializing video processing pipeline...')
                if (newId) {
                  navigate(`/processing/${newId}`)
                }
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
              marginBottom: '16px'
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
              
              <Space size="middle" align="center" wrap>
                {/* Status filter Segmented tabs */}
                <Segmented
                  value={statusFilter}
                  onChange={(val) => setStatusFilter(String(val))}
                  options={[
                    { label: `All (${totalCount})`, value: 'all' },
                    { label: `Completed (${completedCount})`, value: 'completed' },
                    { label: `Processing (${processingCount})`, value: 'processing' },
                    { label: `Failed (${failedCount})`, value: 'failed' },
                  ]}
                  size="middle"
                />

                <Button
                  icon={<CheckSquareOutlined />}
                  type={isSelectMode ? 'primary' : 'default'}
                  onClick={() => {
                    if (isSelectMode) {
                      handleExitSelectMode()
                    } else {
                      setIsSelectMode(true)
                    }
                  }}
                  disabled={filteredProjects.length === 0}
                  style={{
                    borderRadius: '8px',
                    borderColor: isSelectMode ? undefined : 'var(--ac-line)',
                    background: isSelectMode ? undefined : 'var(--ac-card)',
                    color: isSelectMode ? undefined : 'var(--ac-ink)',
                    fontWeight: 500
                  }}
                >
                  {isSelectMode ? 'Done' : 'Select'}
                </Button>
              </Space>
            </div>

            {/* Batch Action Bar */}
            {isSelectMode && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 18px',
                marginBottom: '20px',
                background: 'var(--ac-card)',
                border: '1px solid var(--ac-accent)',
                borderRadius: '12px',
                boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Button
                    size="small"
                    onClick={() => handleSelectAll(filteredIds)}
                    style={{
                      fontSize: '12px',
                      borderRadius: '6px',
                      borderColor: 'var(--ac-line)'
                    }}
                  >
                    {allFilteredSelected ? 'Deselect All' : 'Select All'}
                  </Button>
                  <span style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--ac-ink)' }}>
                    {selectedIds.size} of {filteredProjects.length} selected
                  </span>
                </div>

                <Space size="small">
                  <Popconfirm
                    title={`Delete ${selectedIds.size} project${selectedIds.size > 1 ? 's' : ''}?`}
                    description="All associated videos and clips will be permanently removed. This cannot be undone."
                    onConfirm={handleBatchDelete}
                    okText="Delete All"
                    cancelText="Cancel"
                    okButtonProps={{ danger: true, loading: isBatchDeleting }}
                    disabled={selectedIds.size === 0}
                  >
                    <Button
                      danger
                      type="primary"
                      icon={<DeleteOutlined />}
                      disabled={selectedIds.size === 0}
                      loading={isBatchDeleting}
                      style={{ borderRadius: '8px', fontWeight: 500 }}
                    >
                      Delete Selected ({selectedIds.size})
                    </Button>
                  </Popconfirm>

                  <Button
                    onClick={handleExitSelectMode}
                    icon={<CloseOutlined />}
                    style={{ borderRadius: '8px' }}
                  >
                    Cancel
                  </Button>
                </Space>
              </div>
            )}

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
                         selectable={isSelectMode}
                         selected={selectedIds.has(project.id)}
                         onSelect={handleToggleSelect}
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