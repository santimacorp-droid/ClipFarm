import React, { useState, useEffect } from 'react'
import { Card, Tag, Button, Space, Typography, Popconfirm, message, Tooltip } from 'antd'
import { PlayCircleOutlined, DeleteOutlined, DownloadOutlined, ReloadOutlined, LoadingOutlined, CheckOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import { UnifiedStatusBar } from './UnifiedStatusBar'
import { validateApiConfig } from '../utils/apiConfigCheck'
// import { 
//   getProjectStatusConfig, 
//   calculateProjectProgress, 
//   normalizeProjectStatus,
//   getProgressStatus 
// } from '../utils/statusUtils'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)
dayjs.locale('en')

// addingCSSanimation style
const pulseAnimation = `
  @keyframes pulse {
    0% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.5;
      transform: scale(1.1);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }
  .project-card:hover .project-card-select-btn {
    opacity: 1 !important;
  }
`

// Inject styles into the page
if (typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.textContent = pulseAnimation
  document.head.appendChild(style)
}

const { Text } = Typography

// Tracks which project ids have already had a best-effort auto-start, surviving
// component remounts (the list briefly unmounts while HomePage shows its
// loading spinner). A useRef would reset on every remount and let auto-start
// fire again, which created an infinite onRetry→loadProjects→remount loop.
// Project ids are unique per import, so once-per-session is exactly right.
const autoStartedProjectIds = new Set<string>()

interface ProjectCardProps {
  project: Project
  onDelete: (id: string) => void
  onRetry?: (id: string) => void
  onClick?: () => void
  selectable?: boolean
  selected?: boolean
  onSelect?: (id: string, selected: boolean) => void
}

const ProjectCard: React.FC<ProjectCardProps> = ({ 
  project, 
  onDelete, 
  onRetry, 
  onClick,
  selectable = false,
  selected = false,
  onSelect
}) => {
  const navigate = useNavigate()
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)

  // get category info
  const getCategoryInfo = (category?: string) => {
    const categoryMap: Record<string, { name: string; icon: string; color: string }> = {
      'default': { name: 'General', icon: '🎬', color: '#4facfe' },
      'knowledge': { name: 'Knowledge', icon: '📚', color: '#52c41a' },
      'business': { name: 'Business', icon: '💼', color: '#faad14' },
      'opinion': { name: 'Commentary', icon: '💭', color: '#722ed1' },
      'experience': { name: 'Experience', icon: '🌟', color: '#13c2c2' },
      'speech': { name: 'Speeches', icon: '🎤', color: '#eb2f96' },
      'content_review': { name: 'Review', icon: '🎭', color: '#f5222d' },
      'entertainment': { name: 'Entertainment', icon: '🎪', color: '#fa8c16' }
    }
    return categoryMap[category || 'default'] || categoryMap['default']
  }

  // Manage thumbnail cache
  const thumbnailCacheKey = `thumbnail_${project.id}`
  
  // Generate project video thumbnail (with cache))
  useEffect(() => {
    const generateThumbnail = async () => {
      // Prioritize backend-provided thumbnail
      if (project.thumbnail) {
        setVideoThumbnail(project.thumbnail)
        console.log(`Using backend thumbnail: ${project.id}`)
        return
      }
      
      if (!project.video_path) {
        console.log('Project has no video path yet:', project.id)
        return
      }
      
      // check cache
      const cachedThumbnail = localStorage.getItem(thumbnailCacheKey)
      if (cachedThumbnail) {
        setVideoThumbnail(cachedThumbnail)
        return
      }
      
      setThumbnailLoading(true)
      
      try {
        const video = document.createElement('video')
        video.crossOrigin = 'anonymous'
        video.muted = true
        video.preload = 'metadata'
        
        // Attempt multiple possible video file paths
        const possiblePaths = [
          'input/input.mp4',
          'input.mp4',
          project.video_path,
          `${project.video_path}/input.mp4`
        ].filter(Boolean)
        
        let videoLoaded = false
        
        for (const path of possiblePaths) {
          if (videoLoaded) break
          
          try {
            const videoUrl = projectApi.getProjectFileUrl(project.id, path)
            console.log('Trying to load video:', videoUrl)
            
            await new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                reject(new Error('Video load timeout'))
              }, 10000)
              
              video.onloadedmetadata = () => {
                clearTimeout(timeoutId)
                console.log('Video metadata loaded successfully:', videoUrl)
                video.currentTime = Math.min(5, video.duration / 4)
              }
              
              video.onseeked = () => {
                clearTimeout(timeoutId)
                try {
                  const canvas = document.createElement('canvas')
                  const ctx = canvas.getContext('2d')
                  if (!ctx) {
                    reject(new Error('Failed to get canvas context'))
                    return
                  }
                  
                  // Set thumbnail dimensions
                  const maxWidth = 320
                  const maxHeight = 180
                  const aspectRatio = video.videoWidth / video.videoHeight
                  
                  let width = maxWidth
                  let height = maxHeight
                  
                  if (aspectRatio > maxWidth / maxHeight) {
                    height = maxWidth / aspectRatio
                  } else {
                    width = maxHeight * aspectRatio
                  }
                  
                  canvas.width = width
                  canvas.height = height
                  ctx.drawImage(video, 0, 0, width, height)
                  
                  const thumbnail = canvas.toDataURL('image/jpeg', 0.7)
                  setVideoThumbnail(thumbnail)
                  
                  // Cache thumbnail
                  try {
                    localStorage.setItem(thumbnailCacheKey, thumbnail)
                  } catch (e) {
                    const keys = Object.keys(localStorage).filter(key => key.startsWith('thumbnail_'))
                    if (keys.length > 50) {
                      keys.slice(0, 10).forEach(key => localStorage.removeItem(key))
                      localStorage.setItem(thumbnailCacheKey, thumbnail)
                    }
                  }
                  
                  videoLoaded = true
                  resolve(thumbnail)
                } catch (error) {
                  reject(error)
                }
              }
              
              video.onerror = (error) => {
                clearTimeout(timeoutId)
                console.error('Video load failed:', videoUrl, error)
                reject(error)
              }
              
              video.src = videoUrl
            })
            
            break
          } catch (error) {
            console.warn(`Failed to load path ${path}:`, error)
            continue
          }
        }
        
        if (!videoLoaded) {
          console.error('All video paths failed to load')
        }
      } catch (error) {
        console.error('Error generating thumbnail:', error)
      } finally {
        setThumbnailLoading(false)
      }
    }
    
    generateThumbnail()
  }, [project.id, project.video_path, thumbnailCacheKey])

  // Check if it is a download state processing_config and settings dual source
  const downloadConfig = project.processing_config || (project as any).settings || {}
  const downloadProgress = downloadConfig?.download_progress ?? 0
  const downloadStatus = downloadConfig?.download_status

  // Waiting state and downloading (status marker is downloading, optional present source_url But the local file has not been generated yet video_path, in progress or complete 0-99%)
  const isDownloading = project.status === 'pending' && (
    downloadStatus === 'downloading' ||
    (Boolean(project.source_url) && !project.video_path) ||
    (downloadProgress > 0 && downloadProgress < 100)
  )
  const isImporting = project.status === 'pending' && !isDownloading
  
  // Standardize state handling
  const normalizedStatus = project.status === 'error' ? 'failed' : 
                          isDownloading ? 'downloading' :
                          isImporting ? 'importing' : project.status
  

  // auto-boot pending Projects in failed state (but not including downloading projects)). 
  // Critical: Each project can only attempt once automatically, and will not pop up on failure toast. 
  // earlier this would isRetrying Add it to dependencies, but also handleRetry flipped internally isRetrying, 
  // caused by effect repeatedly trigger → For a project that hasn't finished downloading yet, Bfrantic site project POST /process(returning
  // 400 "Video file not found")→ full screen「retry failed」. After download is complete, the backend will start automatically
  // Pipeline, so only one check is needed here「do one's best」boot up automatically. 
  useEffect(() => {
    if (
      project.status === 'pending' &&
      !isDownloading &&
      !autoStartedProjectIds.has(project.id)
    ) {
      autoStartedProjectIds.add(project.id)
      // Best-effort, one-shot per project. Uploads (file already present) start
      // processing; Bsite imports whose download isn't done yet return 400 here —
      // that's fine, the backend auto-starts the pipeline when the download
      // completes. Silent + no onRetry so this never drives the parent's
      // toast/reload path.
      handleRetry({ silent: true })
    }
  }, [project.status, project.id, isDownloading])
  
  // Calculate progress percentage
  const progressPercent = project.status === 'completed' ? 100 : 
                         project.status === 'failed' ? 0 :
                         isDownloading ? downloadProgress : // Show actual download progress while downloading
                         isImporting ? 5 : // pendingstatus display5%Use "Waiting to process" for its status
                         project.current_step && project.total_steps ? 
                         Math.round((project.current_step / project.total_steps) * 100) : 
                         project.status === 'processing' ? 10 : 0

  const doRetry = async (opts?: { silent?: boolean }) => {
    if (isRetrying) return

    setIsRetrying(true)
    try {
      // forPENDINGStatus projects usestartProcessing; For other states, useretryProcessing
      if (project.status === 'pending') {
        await projectApi.startProcessing(project.id)
      } else {
        await projectApi.retryProcessing(project.id)
      }
      // Let the parent component handle it uniformly toast / refresh. but「silent auto startup」Never trigger the parent component, 
      // otherwise will follow handleRetryProject → loadProjects → re-mount list → re-auto startup
      // Dead loop. Only notify the parent component when users manually click retry. 
      if (onRetry && !opts?.silent) {
        onRetry(project.id)
      }
    } catch (error) {
      console.error('Retry failed:', error)
      // auto-boot(silent)Failure does not interrupt the user; Only show a prompt when the user manually clicks Retry. 
      if (!opts?.silent) {
        message.error('Retry failed, please try again')
      }
    } finally {
      setIsRetrying(false)
    }
  }

  const handleRetry = async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) {
      const hasValid = await validateApiConfig({
        actionName: 'Retrying Project',
        onProceed: () => {
          doRetry(opts)
        }
      })
      if (!hasValid) return
    }
    await doRetry(opts)
  }

  return (
    <Card
      hoverable
      className={`project-card ${selected ? 'project-card-selected' : ''}`}
      style={{
        width: '100%',
        borderRadius: '16px',
        overflow: 'hidden',
        background: selected ? 'rgba(90, 139, 255, 0.05)' : 'var(--ac-card)',
        border: selected ? '2px solid var(--ac-accent, #5a8bff)' : '1px solid var(--ac-line)',
        boxShadow: selected ? '0 0 0 2px rgba(90, 139, 255, 0.25), var(--ac-shadow)' : 'none',
        transition: 'all 0.2s ease',
        cursor: 'pointer',
        marginBottom: '0px'
      }}
      onClick={() => {
        if (selectable) {
          onSelect?.(project.id, !selected)
        }
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = selected 
          ? '0 0 0 2px rgba(90, 139, 255, 0.35), var(--ac-shadow)' 
          : 'var(--ac-shadow)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = selected 
          ? '0 0 0 2px rgba(90, 139, 255, 0.25), var(--ac-shadow)' 
          : 'none'
      }}
      styles={{
        body: {
          padding: '18px 20px 20px',
          background: 'transparent',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
      cover={
        <div
          style={{
            height: 160,
            position: 'relative',
            background: videoThumbnail
              ? `url(${videoThumbnail}) center/cover`
              : 'var(--ac-thumb)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden'
          }}
          onClick={(e) => {
            if (selectable) {
              e.stopPropagation()
              onSelect?.(project.id, !selected)
              return
            }

            // Projects in Importing state cannot be clicked to enter the details page
            if (project.status === 'pending') {
              message.warning('Project is importing, please wait...')
              return
            }
            
            // Projects in Processing state cannot be clicked to enter the details page
            if (project.status === 'processing') {
              message.warning('Project is currently processing. View details once complete.')
              return
            }
            
            if (onClick) {
              onClick()
            } else {
              navigate(`/project/${project.id}`)
            }
          }}
        >
          {/* Selection Checkbox */}
          <div
            className="project-card-select-btn"
            style={{
              position: 'absolute',
              top: '8px',
              left: '8px',
              zIndex: 10,
              opacity: selectable || selected ? 1 : 0,
              transition: 'opacity 0.2s ease, transform 0.15s ease'
            }}
            onClick={(e) => {
              e.stopPropagation()
              onSelect?.(project.id, !selected)
            }}
          >
            <div
              style={{
                width: '22px',
                height: '22px',
                borderRadius: '6px',
                border: selected ? '2px solid var(--ac-accent, #5a8bff)' : '2px solid rgba(255, 255, 255, 0.85)',
                background: selected ? 'var(--ac-accent, #5a8bff)' : 'rgba(0, 0, 0, 0.55)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                backdropFilter: 'blur(6px)',
                boxShadow: selected ? '0 2px 8px rgba(90, 139, 255, 0.5)' : '0 2px 6px rgba(0,0,0,0.3)',
                transition: 'all 0.15s ease'
              }}
            >
              {selected && <CheckOutlined style={{ color: '#fff', fontSize: '12px', fontWeight: 'bold' }} />}
            </div>
          </div>

          {/* Thumbnail loading status */}
          {thumbnailLoading && (
            <div style={{ textAlign: 'center', color: 'var(--ac-muted)' }}>
              <LoadingOutlined style={{ fontSize: '22px', marginBottom: '4px' }} />
              <div style={{ fontSize: '12px' }}>Generating thumbnail...</div>
            </div>
          )}

          {/* Default display when no thumbnail is available */}
          {!videoThumbnail && !thumbnailLoading && (
            <PlayCircleOutlined style={{ fontSize: '32px', color: 'var(--ac-muted)' }} />
          )}
          
          {/* Category label - Top left corner (shifted if select button is visible) */}
          {project.video_category && project.video_category !== 'default' && (
            <div style={{
              position: 'absolute',
              top: '8px',
              left: selectable || selected ? '38px' : '8px',
              transition: 'left 0.2s ease',
              zIndex: 5
            }}>
              <Tag
                style={{
                  background: `${getCategoryInfo(project.video_category).color}15`,
                  border: `1px solid ${getCategoryInfo(project.video_category).color}40`,
                  borderRadius: '3px',
                  color: getCategoryInfo(project.video_category).color,
                  fontSize: '10px',
                  fontWeight: 500,
                  padding: '2px 6px',
                  lineHeight: '14px',
                  height: '18px',
                  margin: 0
                }}
              >
                <span style={{ marginRight: '2px' }}>{getCategoryInfo(project.video_category).icon}</span>
                {getCategoryInfo(project.video_category).name}
              </Tag>
            </div>
          )}
          
          {/* Remove upper-right corner status indicator */}
          
          {/* Update time and operation buttons */}
          <div style={{
            position: 'absolute',
            bottom: '0',
            left: '0',
            right: '0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            background: 'linear-gradient(to top, rgba(0,0,0,0.42), rgba(0,0,0,0))',
            borderRadius: '0',
            padding: '10px 12px',
            height: '52px'
          }}>
            <Text style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.92)' }}>
              {dayjs(project.created_at).fromNow()}
            </Text>
            
            {/* operation buttons */}
            <div 
              className="card-action-buttons"
              style={{
                display: 'flex',
                gap: '4px',
                opacity: 0,
                transition: 'opacity 0.3s ease'
              }}
            >
              {/* Failure state: Displays only retry and delete buttons */}
              {normalizedStatus === 'failed' ? (
                <>
                  <Button
                    type="text"
                    icon={<ReloadOutlined />}
                    loading={isRetrying}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRetry()
                    }}
                    style={{
                      height: '20px',
                      width: '20px',
                      borderRadius: '3px',
                      color: '#52c41a',
                      border: '1px solid rgba(82, 196, 26, 0.5)',
                      background: 'rgba(82, 196, 26, 0.1)',
                      padding: 0,
                      minWidth: '20px',
                      fontSize: '10px'
                    }}
                  />
                  
                  <Popconfirm
                    title="Delete this project?"
                    description="This action cannot be undone."
                    onConfirm={(e) => {
                      e?.stopPropagation()
                      onDelete(project.id)
                    }}
                    onCancel={(e) => {
                      e?.stopPropagation()
                    }}
                    okText="Confirm"
                    cancelText="Cancel"
                  >
                    <Button
                      type="text"
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation()
                      }}
                      style={{
                        height: '20px',
                        width: '20px',
                        borderRadius: '3px',
                        color: '#ff6b6b',
                        border: '1px solid rgba(255, 107, 107, 0.5)',
                        background: 'rgba(255, 107, 107, 0.1)',
                        padding: 0,
                        minWidth: '20px',
                        fontSize: '10px'
                      }}
                    />
                  </Popconfirm>
                </>
              ) : (
                /* Other states: display download, retry and delete buttons */
                <>
                  <Space size={4}>
                    {/* retry button */}
                    {(normalizedStatus === 'processing' || normalizedStatus === 'importing' || project.status === 'pending') && (
                      <Tooltip title={project.status === 'pending' ? "Start Processing" : "Retry Task"}>
                        <Button
                          type="text"
                          icon={<ReloadOutlined />}
                          loading={isRetrying}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRetry()
                          }}
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '6px',
                            color: '#1890ff',
                            border: '1px solid rgba(24, 144, 255, 0.5)',
                            background: 'rgba(24, 144, 255, 0.15)',
                            padding: 0,
                            minWidth: '26px',
                            fontSize: '12px'
                          }}
                        />
                      </Tooltip>
                    )}
                    
                    {/* Download button: Only displays after completion */}
                    {normalizedStatus === 'completed' && (
                      <Tooltip title="Download Clips ZIP">
                        <Button
                          type="text"
                          icon={<DownloadOutlined />}
                          onClick={async (e) => {
                            e.stopPropagation()
                            message.loading({ content: 'Downloading clips ZIP...', key: 'dl_zip' })
                            try {
                              await projectApi.exportAllClipsZip(project.id, 'all')
                              message.success({ content: 'Clips ZIP downloaded!', key: 'dl_zip' })
                            } catch (err: any) {
                              message.error({ content: `Download failed: ${err.message || 'Error'}`, key: 'dl_zip' })
                            }
                          }}
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '6px',
                            color: 'rgba(255, 255, 255, 0.9)',
                            border: '1px solid rgba(255, 255, 255, 0.25)',
                            background: 'rgba(255, 255, 255, 0.12)',
                            padding: 0,
                            minWidth: '26px',
                            fontSize: '12px'
                          }}
                        />
                      </Tooltip>
                    )}
                    
                    {/* delete button */}
                    <Popconfirm
                      title="Are you sure you want to delete this project?"
                      description="This action cannot be undone."
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        onDelete(project.id)
                      }}
                      onCancel={(e) => {
                        e?.stopPropagation()
                      }}
                      okText="Delete"
                      cancelText="Cancel"
                    >
                      <Tooltip title="Delete Project">
                        <Button
                          type="text"
                          icon={<DeleteOutlined />}
                          onClick={(e) => {
                            e.stopPropagation()
                          }}
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '6px',
                            color: 'rgba(255, 255, 255, 0.85)',
                            border: '1px solid rgba(255, 255, 255, 0.25)',
                            background: 'rgba(255, 255, 255, 0.12)',
                            padding: 0,
                            minWidth: '26px',
                            fontSize: '12px'
                          }}
                        />
                      </Tooltip>
                    </Popconfirm>
                  </Space>
                 </>
               )}
            </div>
          </div>
        </div>
      }
    >
      <div style={{ padding: '0', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          {/* Project name - Always at top */}
          <div style={{ marginBottom: '12px', position: 'relative' }}>
            <Tooltip title={project.name} placement="top">
              <Text 
                strong 
                style={{ 
                  fontSize: '13px', 
                  color: '#ffffff',
                  fontWeight: 600,
                  lineHeight: '16px',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  cursor: 'help',
                  height: '32px'
                }}
              >
                {project.name}
              </Text>
            </Tooltip>
          </div>
          
          {/* State and statistics information — Calm Premium, see DESIGN.md */}
          {(normalizedStatus === 'importing' || normalizedStatus === 'downloading' || normalizedStatus === 'processing' || normalizedStatus === 'failed') ? (
            // in progress / Failure: fine progress line or final state point, fills width
            <div style={{ marginBottom: '2px' }}>
              <UnifiedStatusBar
                projectId={project.id}
                status={normalizedStatus}
                downloadProgress={progressPercent}
                onStatusChange={() => {}}
              />
            </div>
          ) : (
            // completed: ● completed  +  greyed out mono metadata(N slice · M collection)
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
              <UnifiedStatusBar
                projectId={project.id}
                status={normalizedStatus}
                downloadProgress={progressPercent}
                onStatusChange={() => {}}
              />
              <div style={{ color: 'var(--ac-muted)', fontSize: '12.5px', whiteSpace: 'nowrap' }}>
                <span className="ac-mono">{project.total_clips || 0}</span> Clips
                <span style={{ margin: '0 6px' }}>·</span>
                <span className="ac-mono">{project.total_collections || 0}</span> Collections
              </div>
            </div>
          )}

          {/* Detailed progress display is hidden */}

        </div>
      </div>
    </Card>
  )
}

export default ProjectCard