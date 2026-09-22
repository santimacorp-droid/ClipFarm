import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  Layout, 
  Card, 
  Typography, 
  Button, 
  Space, 
  Alert, 
  Spin, 
  Empty, 
  message, 
  Dropdown, 
  Segmented, 
  type MenuProps 
} from 'antd'
import { 
  ArrowLeftOutlined, 
  PlayCircleOutlined, 
  PlusOutlined, 
  DownloadOutlined, 
  DownOutlined, 
  AppstoreOutlined 
} from '@ant-design/icons'
import { useProjectStore, Clip, Collection } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import ClipCard from '../components/ClipCard'
import CollectionCard from '../components/CollectionCard'
import CollectionPreviewModal from '../components/CollectionPreviewModal'
import CreateCollectionModal from '../components/CreateCollectionModal'
import { useCollectionVideoDownload } from '../hooks/useCollectionVideoDownload'
import { ProjectTaskManager } from '../components/ProjectTaskManager'

const { Content } = Layout
const { Title, Text } = Typography

const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { 
    currentProject, 
    loading, 
    error,
    setCurrentProject,
    upsertProject,
    updateCollection,
    addCollection,
    deleteCollection,
    removeClipFromCollection,
    reorderCollectionClips,
    addClipToCollection
  } = useProjectStore()
  
  const [statusLoading, setStatusLoading] = useState(false)
  const [showCreateCollection, setShowCreateCollection] = useState(false)
  const [sortBy, setSortBy] = useState<'time' | 'score'>('score')
  const [globalPlatform, setGlobalPlatform] = useState<string>('tiktok')
  const [showCollectionDetail, setShowCollectionDetail] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null)
  const { generateAndDownloadCollectionVideo } = useCollectionVideoDownload()
  const [exportingZip, setExportingZip] = useState(false)

  const handleExportAllZip = async (platform?: string) => {
    if (!currentProject?.id) return
    setExportingZip(true)
    const platName = platform && platform !== 'all' 
      ? (platform === 'youtube_shorts' ? 'YouTube Shorts' : platform.charAt(0).toUpperCase() + platform.slice(1))
      : 'All Platforms Bundle'
    message.loading({ content: `Packaging ${platName} clips into ZIP archive...`, key: 'zip_export', duration: 0 })
    try {
      await projectApi.exportAllClipsZip(currentProject.id, platform)
      message.success({ content: `Clips ZIP archive (${platName}) downloaded successfully!`, key: 'zip_export' })
    } catch (e: any) {
      message.error({ content: `Failed to export ZIP: ${e.message || 'Unknown error'}`, key: 'zip_export' })
    } finally {
      setExportingZip(false)
    }
  }

  const zipMenuItems: MenuProps['items'] = [
    {
      key: 'all',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0', fontWeight: 600 }}>
          <AppstoreOutlined />
          <span>All Platforms Bundle (TikTok, IG, Shorts, FB)</span>
        </span>
      ),
      onClick: () => handleExportAllZip('all')
    },
    { type: 'divider' },
    {
      key: 'tiktok',
      label: '📱 All TikTok Clips (ZIP)',
      onClick: () => handleExportAllZip('tiktok')
    },
    {
      key: 'instagram',
      label: '📷 All Instagram Reels Clips (ZIP)',
      onClick: () => handleExportAllZip('instagram')
    },
    {
      key: 'youtube_shorts',
      label: '▶️ All YouTube Shorts Clips (ZIP)',
      onClick: () => handleExportAllZip('youtube_shorts')
    },
    {
      key: 'facebook',
      label: '📘 All Facebook Clips (ZIP)',
      onClick: () => handleExportAllZip('facebook')
    },
  ]

  useEffect(() => {
    if (!id) return
    loadProject()
    loadProcessingStatus()
  }, [id])

  const loadProject = async () => {
    if (!id) return
    try {
      const project = await projectApi.getProject(id)
      
      // If project is completed, load itclipsAndcollections
      if (project.status === 'completed') {
        try {
          const [clips, collections] = await Promise.all([
            projectApi.getClips(id),
            projectApi.getCollections(id)
          ])
          
          console.log('🎬 Loaded clips in ProjectDetailPage:', clips)
          console.log('📚 Loaded collections in ProjectDetailPage:', collections)
          
          const projectWithData = {
            ...project,
            clips: clips || [],
            collections: collections || []
          }
          
          console.log('🎯 Final project with data:', projectWithData)
          setCurrentProject(projectWithData)
          
          // Synchronize project list to prevent page and list state drift
          upsertProject(projectWithData)
        } catch (error) {
          console.error('Failed to load clips/collections:', error)
          // Even whenclips/collectionsFailed to load but still set basic project information
          setCurrentProject(project)
        }
      } else {
        setCurrentProject(project)
      }
    } catch (error) {
      console.error('Failed to load project:', error)
      message.error('Failed to load project')
    }
  }

  const loadProcessingStatus = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.getProcessingStatus(id)
    } catch (error) {
      console.error('Failed to load processing status:', error)
    } finally {
      setStatusLoading(false)
    }
  }

  const handleStartProcessing = async () => {
    if (!id) return
    try {
      await projectApi.startProcessing(id)
      message.success('Processing started')
      loadProcessingStatus()
    } catch (error) {
      console.error('Failed to start processing:', error)
      message.error('Failed to start processing')
    }
  }

  const handleCreateCollection = async (title: string, summary: string, clipIds: string[]) => {
    if (!id) return
    try {
      await addCollection(id, {
        id: `collection_${Date.now()}`,
        collection_title: title,
        collection_summary: summary,
        clip_ids: clipIds,
        collection_type: 'manual',
        created_at: new Date().toISOString()
      })
      setShowCreateCollection(false)
      message.success('Collection created successfully')
    } catch (error) {
      console.error('Failed to create collection:', error)
      message.error('Failed to create collection')
    }
  }

  const handleViewCollection = (collection: Collection) => {
    setSelectedCollection(collection)
    setShowCollectionDetail(true)
  }

  const handleRemoveClipFromCollection = async (collectionId: string, clipId: string): Promise<void> => {
    if (!id) return
    try {
      await removeClipFromCollection(id, collectionId, clipId)
      message.success('Clip removed from collection')
    } catch (error) {
      console.error('Failed to remove clip from collection:', error)
      message.error('Failed to remove clip')
    }
  }

  const handleDeleteCollection = async (collectionId: string) => {
    if (!id) return
    try {
      await deleteCollection(id, collectionId)
      setShowCollectionDetail(false)
      setSelectedCollection(null)
      message.success('Collection deleted')
    } catch (error) {
      console.error('Failed to delete collection:', error)
      message.error('Failed to delete collection')
    }
  }

  const handleReorderCollectionClips = async (collectionId: string, newClipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await reorderCollectionClips(id, collectionId, newClipIds)
      message.success('Collection order updated')
    } catch (error) {
      console.error('Failed to reorder collection clips:', error)
      message.error('Failed to reorder clips')
    }
  }

  const handleAddClipToCollection = async (collectionId: string, clipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await addClipToCollection(id, collectionId, clipIds)
      message.success('Clip added to collection')
    } catch (error) {
      console.error('Failed to add clip to collection:', error)
      message.error('Failed to add clip')
    }
  }

  const getSortedClips = () => {
    if (!currentProject?.clips) return []
    const clips = [...currentProject.clips]
    
    if (sortBy === 'score') {
      return clips.sort((a, b) => b.final_score - a.final_score)
    } else {
      // Sort by time - compare timestamp strings by converting to seconds
      return clips.sort((a, b) => {
        const getTimeInSeconds = (timeStr: string) => {
          const parts = timeStr.split(':')
          const hours = parseInt(parts[0])
          const minutes = parseInt(parts[1])
          const seconds = parseFloat(parts[2].replace(',', '.'))
          return hours * 3600 + minutes * 60 + seconds
        }
        
        const aTime = getTimeInSeconds(a.start_time)
        const bTime = getTimeInSeconds(b.start_time)
        return aTime - bTime
      })
    }
  }

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" />
      </Content>
    )
  }

  if (error || !currentProject) {
    return (
      <Content style={{ padding: '24px' }}>
        <Alert
          message="Load Failed"
          description={error || 'Project does not exist'}
          type="error"
          action={
            <Button size="small" onClick={() => navigate('/')}>
              Back to Home
            </Button>
          }
        />
      </Content>
    )
  }

  return (
    <Content style={{ padding: '24px' }}>
      {/* Simplified project header */}
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Button 
            type="link" 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/')}
            style={{ padding: 0, marginBottom: '8px' }}
          >
            Back to Projects
          </Button>
          <Title level={2} style={{ margin: 0 }}>
            {currentProject.name}
          </Title>
        </div>
        
        <Space>
          {currentProject.status === 'pending' && (
            <Button 
              type="primary" 
              onClick={handleStartProcessing}
              loading={statusLoading}
            >
              Start Processing
            </Button>
          )}
        </Space>
      </div>

      {/* Main content */}
      {currentProject.status === 'completed' ? (
        <div>
          {/* AICollection horizontal scroll area */}
          {currentProject.collections && currentProject.collections.length > 0 && (
            <Card style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <Title level={4} style={{ margin: 0 }}>AI Collections</Title>
                  <Text type="secondary">
                    AI recommended {currentProject.collections.length} topic collections
                  </Text>
                </div>
                <Button 
                  type="primary" 
                  icon={<PlusOutlined />}
                  onClick={() => setShowCreateCollection(true)}
                  style={{
                    borderRadius: '8px',
                    background: 'var(--ac-accent)',
                    border: 'none',
                    fontWeight: 500,
                    height: '40px',
                    padding: '0 20px',
                    fontSize: '14px'
                  }}
                >
                  Create Collection
                </Button>
              </div>
              
              <div 
                className="collections-scroll-container"
                style={{ 
                  display: 'flex',
                  gap: '16px',
                  overflowX: 'auto',
                  paddingBottom: '8px'
                }}
              >
                {currentProject.collections
                  .sort((a, b) => {
                    // Sort projects descending by creation time with newest first
                    const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
                    const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
                    return timeB - timeA
                  })
                  .map((collection) => (
                  <CollectionCard
                    key={collection.id}
                    collection={collection}
                    clips={currentProject.clips || []}
                    onView={handleViewCollection}
                    onUpdate={(collectionId, updates) => 
                      updateCollection(currentProject.id, collectionId, updates)
                    }
                    onGenerateVideo={async (collectionId) => {
                      const collection = currentProject.collections?.find(c => c.id === collectionId)
                      if (collection) {
                        await generateAndDownloadCollectionVideo(
                          currentProject.id, 
                          collectionId, 
                          collection.collection_title
                        )
                      }
                    }}
                    onDelete={handleDeleteCollection}
                  />
                ))}
              </div>
            </Card>
          )}
          
          {/* Video segment area */}
          <Card 
            style={{
              borderRadius: '16px',
              border: '1px solid var(--ac-line)',
              background: 'var(--ac-card)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Title level={4} style={{ margin: 0, color: 'var(--ac-ink)', fontWeight: 600 }}>Video Clips</Title>
                  <span style={{ 
                    background: 'rgba(82, 196, 26, 0.12)', 
                    color: '#52c41a', 
                    border: '1px solid rgba(82, 196, 26, 0.3)',
                    padding: '2px 8px', 
                    borderRadius: '999px', 
                    fontSize: '11.5px',
                    fontWeight: 600
                  }}>
                    4 Platforms Ready
                  </span>
                </div>
                <Text type="secondary" style={{ color: 'var(--ac-sub)', fontSize: '13.5px', marginTop: '4px', display: 'block' }}>
                  AI generated {currentProject.clips?.length || 0} highlight clips · 4 platform versions available per clip
                </Text>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                {/* Platform Format Selector */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Text style={{ fontSize: '12.5px', color: 'var(--ac-sub)', fontWeight: 500 }}>Format:</Text>
                  <Segmented
                    value={globalPlatform}
                    onChange={(val) => setGlobalPlatform(String(val))}
                    options={[
                      { label: '📱 TikTok', value: 'tiktok' },
                      { label: '📷 Instagram', value: 'instagram' },
                      { label: '▶️ Shorts', value: 'youtube_shorts' },
                      { label: '📘 Facebook', value: 'facebook' },
                    ]}
                    size="middle"
                  />
                </div>

                {/* Sort control */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Text style={{ fontSize: '12.5px', color: 'var(--ac-sub)', fontWeight: 500 }}>Sort:</Text>
                  <Segmented
                    value={sortBy}
                    onChange={(val) => setSortBy(val as 'time' | 'score')}
                    options={[
                      { label: 'Score', value: 'score' },
                      { label: 'Time', value: 'time' },
                    ]}
                    size="middle"
                  />
                </div>
                
                <Space>
                  {currentProject.clips && currentProject.clips.length > 0 && (
                    <Dropdown menu={{ items: zipMenuItems }} trigger={['click']}>
                      <Button
                        icon={<DownloadOutlined />}
                        loading={exportingZip}
                        style={{
                          borderRadius: '8px',
                          background: 'var(--ac-line-2)',
                          border: '1px solid var(--ac-line)',
                          color: 'var(--ac-ink)',
                          fontWeight: 500,
                          height: '36px',
                          padding: '0 14px',
                          fontSize: '13px'
                        }}
                      >
                        Download (ZIP) <DownOutlined style={{ fontSize: '10px' }} />
                      </Button>
                    </Dropdown>
                  )}
                  {(!currentProject.collections || currentProject.collections.length === 0) && (
                    <Button 
                      type="primary" 
                      icon={<PlusOutlined />}
                      onClick={() => setShowCreateCollection(true)}
                      style={{
                        borderRadius: '8px',
                        background: 'var(--ac-accent)',
                        border: 'none',
                        fontWeight: 500,
                        height: '36px',
                        padding: '0 18px',
                        fontSize: '13px'
                      }}
                    >
                      Create Collection
                    </Button>
                  )}
                </Space>
              </div>
            </div>
            
            {currentProject.clips && currentProject.clips.length > 0 ? (
              <div 
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                  gap: '20px',
                  padding: '8px 0'
                }}
              >
                {getSortedClips().map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    projectId={currentProject.id}
                    videoUrl={projectApi.getClipVideoUrl(currentProject.id, clip.id, clip.title || clip.generated_title)}
                    onDownload={(clipId) => projectApi.downloadVideo(currentProject.id, clipId)}
                    activePlatformProp={globalPlatform}
                    onPlatformChange={(plat) => setGlobalPlatform(plat)}
                    onClipUpdate={(clipId: string, updates: Partial<Clip>) => {
                      // Update local state
                      if (currentProject) {
                        const updatedProject = {
                          ...currentProject,
                          clips: currentProject.clips?.map((c: Clip) => 
                            c.id === clipId ? { ...c, ...updates } : c
                          ) || []
                        }
                        setCurrentProject(updatedProject)
                      }
                    }}
                  />
                ))}
              </div>
            ) : (
              <div style={{ 
                padding: '60px 0',
                textAlign: 'center',
                background: 'var(--ac-line)',
                borderRadius: '12px',
                border: '1px dashed var(--ac-line)'
              }}>
                <Empty 
                  description={
                    <Text style={{ color: '#888', fontSize: '14px' }}>No video clips yet</Text>
                  }
                  image={<PlayCircleOutlined style={{ fontSize: '48px', color: '#555' }} />}
                />
              </div>
            )}
          </Card>
        </div>
      ) : (
        <div>
          {/* Task management component */}
          <ProjectTaskManager 
            projectId={currentProject.id} 
            projectName={currentProject.name}
          />
          
          {/* Project status indicator */}
          <Card style={{ marginTop: '16px' }}>
            <Empty 
              image={<PlayCircleOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
              description={
                <div>
                  <Text>Project processing is not complete yet</Text>
                  <br />
                  <Text type="secondary">Clips and AI collections will appear here once finished.</Text>
                </div>
              }
            />
          </Card>
        </div>
      )}

      {/* Create collection modal */}
      <CreateCollectionModal
        visible={showCreateCollection}
        clips={currentProject.clips || []}
        onCancel={() => setShowCreateCollection(false)}
        onCreate={handleCreateCollection}
      />
      
      {/* Collection preview modal */}
      <CollectionPreviewModal
        visible={showCollectionDetail}
        collection={selectedCollection}
        clips={currentProject.clips || []}
        projectId={currentProject.id}
        onClose={() => {
          setShowCollectionDetail(false)
          setSelectedCollection(null)
        }}
        onUpdateCollection={(collectionId, updates) => 
          updateCollection(currentProject.id, collectionId, updates)
        }
        onRemoveClip={handleRemoveClipFromCollection}
        onReorderClips={handleReorderCollectionClips}
        onDelete={handleDeleteCollection}
        onAddClip={handleAddClipToCollection}
      />

    </Content>
  )
}

export default ProjectDetailPage