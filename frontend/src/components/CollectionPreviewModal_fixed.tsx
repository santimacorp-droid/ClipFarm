import React, { useState, useRef, useEffect } from 'react'
import { Modal, Row, Col, Button, Space, Typography, Tag, Tooltip, message, Popconfirm } from 'antd'
import { PlayCircleOutlined, DownloadOutlined, DeleteOutlined, DragOutlined, CloseOutlined, LeftOutlined, RightOutlined, PlusOutlined } from '@ant-design/icons'
import ReactPlayer from 'react-player'
import { DragDropContext, Droppable, Draggable, DropResult } from 'react-beautiful-dnd'
import { Collection, Clip, useProjectStore } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import AddClipToCollectionModal from './AddClipToCollectionModal'
import './CollectionPreviewModal.css'

const { Title, Text } = Typography

interface CollectionPreviewModalProps {
  visible: boolean
  collection: Collection | null
  clips: Clip[]
  projectId: string
  onClose: () => void
  onUpdateCollection: (collectionId: string, updates: Partial<Collection>) => void
  onRemoveClip: (collectionId: string, clipId: string) => Promise<void>
  onReorderClips: (collectionId: string, newClipIds: string[]) => void
  onAddClip?: (collectionId: string, clipIds: string[]) => void
  onDelete?: (collectionId: string) => void
}

const CollectionPreviewModal: React.FC<CollectionPreviewModalProps> = ({
  visible,
  collection,
  clips,
  projectId,
  onClose,
  onRemoveClip,
  onReorderClips,
  onAddClip,
  onDelete
}) => {
  const [currentClipIndex, setCurrentClipIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const autoPlay = true
  const [downloadingClip, setDownloadingClip] = useState<string | null>(null)
  const [downloadingCollection, setDownloadingCollection] = useState(false)
  const [generatingVideo, setGeneratingVideo] = useState(false)
  const [showAddClipModal, setShowAddClipModal] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const playerRef = useRef<ReactPlayer>(null)
  const { setDragging } = useProjectStore()

  // Order clips according to collection.clip_ids
  const collectionClips = collection ? 
    (Array.isArray(collection.clip_ids) ? collection.clip_ids : [])
      .map(clipId => (Array.isArray(clips) ? clips : []).find(clip => clip.id === clipId))
      .filter(Boolean) as Clip[] : []
  const currentClip = collectionClips[currentClipIndex]

  useEffect(() => {
    if (visible && collectionClips.length > 0) {
      setCurrentClipIndex(0)
      setPlaying(false)
    }
  }, [visible, collection])

  const handleClipSelect = (index: number) => {
    if (!isUpdating) {
      setCurrentClipIndex(index)
      setPlaying(true)
    }
  }

  const handlePlayNext = () => {
    if (currentClipIndex < collectionClips.length - 1) {
      setCurrentClipIndex(currentClipIndex + 1)
      if (autoPlay) {
        setPlaying(true)
      }
    } else {
      setPlaying(false)
    }
  }

  const handlePlayPrevious = () => {
    if (currentClipIndex > 0) {
      setCurrentClipIndex(currentClipIndex - 1)
      if (autoPlay) {
        setPlaying(true)
      }
    }
  }

  const handleVideoEnd = () => {
    if (autoPlay && currentClipIndex < collectionClips.length - 1) {
      handlePlayNext()
    } else {
      setPlaying(false)
    }
  }

  const handleDragStart = () => {
    console.log('Drag started')
    setDragging(true)
  }

  const handleDragEnd = async (result: DropResult) => {
    console.log('Drag ended:', result)
    
    // Always clear drag status
    setDragging(false)
    
    if (!result.destination || !collection) {
      console.log('Drag canceled or no target position')
      return
    }

    // Check if there is actually a position change
    if (result.source.index === result.destination.index) {
      console.log('Position unchanged, skip update')
      return
    }

    const newClipIds = Array.from(collection.clip_ids)
    const [reorderedItem] = newClipIds.splice(result.source.index, 1)
    newClipIds.splice(result.destination.index, 0, reorderedItem)

    console.log('Original order:', collection.clip_ids)
    console.log('New order:', newClipIds)
    
    // Show loading state
    const hideLoading = message.loading('In progress: Updating clip order...', 0)
    setIsUpdating(true)
    
    try {
      await onReorderClips(collection.id, newClipIds)
      
      // Updating current playback index
      const currentClipId = collectionClips[currentClipIndex]?.id
      if (currentClipId) {
        const newIndex = newClipIds.indexOf(currentClipId)
        setCurrentClipIndex(newIndex)
      }
      
      hideLoading()
      message.success('Clip order updated successfully')
    } catch (error) {
      console.error('Failed to reorder clips:', error)
      hideLoading()
      message.error('Failed to modify clip order')
    } finally {
      setIsUpdating(false)
    }
  }

  const handleRemoveClip = async (clipId: string) => {
    if (!collection) return
    
    const hideLoading = message.loading('Removing chunk......', 0)
    setIsUpdating(true)
    
    try {
      await onRemoveClip(collection.id, clipId)
      
      // Adjust current playback index
      const removedIndex = collection.clip_ids.indexOf(clipId)
      if (removedIndex <= currentClipIndex && currentClipIndex > 0) {
        setCurrentClipIndex(currentClipIndex - 1)
      } else if (removedIndex === currentClipIndex && currentClipIndex >= collectionClips.length - 1) {
        setCurrentClipIndex(Math.max(0, collectionClips.length - 2))
      }
      
      hideLoading()
      message.success('Clip removed successfully')
    } catch (error) {
      console.error('Failed to remove clip:', error)
      hideLoading()
      message.error('Failed to remove clip')
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDownloadClip = async (clipId: string) => {
    setDownloadingClip(clipId)
    try {
      await projectApi.downloadVideo(projectId, clipId)
      message.success('Chunk download successful')
    } catch (error) {
      console.error('Download clip failed:', error)
      message.error('Failed to download chunk')
    } finally {
      setDownloadingClip(null)
    }
  }

  const handleDownloadCollection = async () => {
    if (!collection) return
    
    setDownloadingCollection(true)
    try {
      await projectApi.downloadVideo(projectId, undefined, collection.id)
      message.success('Collection download successful')
    } catch (error) {
      console.error('Download collection failed:', error)
      message.error('Collection download failed')
    } finally {
      setDownloadingCollection(false)
    }
  }

  const handleGenerateVideo = async () => {
    if (!collection) return
    
    try {
      setGeneratingVideo(true)
      await projectApi.generateCollectionVideo(projectId, collection.id)
      message.success('Starting to generate collection video. Please check download later.')
    } catch (error) {
      message.error('Collection video generation failed')
    } finally {
      setGeneratingVideo(false)
    }
  }

  const handleAddClips = async (selectedClipIds: string[]) => {
    if (!collection || !onAddClip) return
    
    const hideLoading = message.loading('Adding clip......', 0)
    setIsUpdating(true)
    
    try {
      await onAddClip(collection.id, selectedClipIds)
      setShowAddClipModal(false)
      hideLoading()
      message.success(`Successfully added ${selectedClipIds.length} chunks added to collection`)
    } catch (error) {
      console.error('Failed to add clips:', error)
      hideLoading()
      message.error('Failed to add chunk')
    } finally {
      setIsUpdating(false)
    }
  }

  const formatDuration = (clip: Clip) => {
    const start = clip.start_time.split(':')
    const end = clip.end_time.split(':')
    const startSeconds = parseInt(start[0]) * 3600 + parseInt(start[1]) * 60 + parseFloat(start[2].replace(',', '.'))
    const endSeconds = parseInt(end[0]) * 3600 + parseInt(end[1]) * 60 + parseFloat(end[2].replace(',', '.'))
    const duration = endSeconds - startSeconds
    const mins = Math.floor(duration / 60)
    const secs = Math.floor(duration % 60)
    return `${mins}:${String(secs).padStart(2, '0')}`
  }

  if (!collection) return null

  return (
    <Modal
      title={null}
      open={visible}
      onCancel={onClose}
      footer={null}
      width="90vw"
      style={{ top: 20 }}
      styles={{ body: { padding: 0, height: 'min(90dvh, calc(100dvh - 40px))' } }}
      className="collection-preview-modal"
      closable={false}
      maskClosable={false}
      destroyOnClose={false}
      getContainer={false}
    >
      <div className="collection-preview-container">
        {/* Top header bar */}
        <div className="preview-header">
          <div className="header-left">
            <Title level={4} style={{ margin: 0, color: 'white', display: 'inline-block', marginRight: '12px' }}>
              {collection.collection_title}
            </Title>
            <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
              ({collectionClips.length} slice(s))
            </Text>
          </div>
          <div className="header-right">
            <Space>
              <Button 
                type="primary" 
                icon={<DownloadOutlined />}
                loading={downloadingCollection}
                onClick={handleDownloadCollection}
              >
                Download bundle
              </Button>
              <Button 
                type="primary" 
                loading={generatingVideo}
                onClick={handleGenerateVideo}
              >
                Generating collection video
              </Button>
              {onDelete && (
                <Popconfirm
                  title="Delete bundle"
                  description="Are you sure you want to delete this collection? This action cannot be undone. "
                  onConfirm={() => onDelete(collection.id)}
                  okText="Confirm"
                  cancelText="Cancel"
                >
                  <Button 
                    type="text" 
                    icon={<DeleteOutlined />}
                    style={{ color: 'white' }}
                  >
                    Delete
                  </Button>
                </Popconfirm>
              )}
              <Button 
                type="text" 
                icon={<CloseOutlined />} 
                onClick={onClose}
                style={{ color: 'white' }}
              />
            </Space>
          </div>
        </div>

        {/* Main content */}
        <div className="preview-content">
          <Row style={{ height: '100%' }}>
            {/* Left-side video player */}
            <Col span={16} className="video-section">
              <div className="video-player-wrapper">
                <div className="video-container">
                  {currentClip ? (
                    <ReactPlayer
                      ref={playerRef}
                      url={projectApi.getClipVideoUrl(projectId, currentClip.id, currentClip.title || currentClip.generated_title)}
                      width="100%"
                      height="100%"
                      playing={playing}
                      controls
                      onEnded={handleVideoEnd}
                      onPlay={() => setPlaying(true)}
                      onPause={() => setPlaying(false)}
                    />
                  ) : (
                    <div className="empty-video">
                      <PlayCircleOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />
                      <Text style={{ color: '#999', marginTop: 16 }}>No video content available</Text>
                    </div>
                  )}
                </div>
                
                {/* Video information panel - Below video */}
                {currentClip && (
                  <div className="video-info-bar">
                    <div className="video-info-content">
                      <div className="video-title-section">
                        <div className="video-title">
                          {currentClip.title || currentClip.generated_title}
                        </div>
                        <div className="video-meta">
                          <Tag color="blue">{formatDuration(currentClip)}</Tag>
                          <Tag color="green">Fraction: {(currentClip.final_score * 100).toFixed(0)}</Tag>
                          <Text style={{ color: '#999', marginLeft: 8 }}>
                            {currentClipIndex + 1} / {collectionClips.length}
                          </Text>
                        </div>
                      </div>
                      
                      <div className="video-controls">
                        <Button 
                          type="text" 
                          icon={<LeftOutlined />}
                          disabled={currentClipIndex === 0}
                          onClick={handlePlayPrevious}
                          title="Previous chunk"
                          className="control-btn"
                        />
                        <Button 
                          type="text" 
                          icon={<RightOutlined />}
                          disabled={currentClipIndex === collectionClips.length - 1}
                          onClick={handlePlayNext}
                          title="Next chunk"
                          className="control-btn"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Col>

            {/* Right-side chunk list */}
            <Col span={8} className="playlist-section">
              <div className="playlist-container">
                <div className="playlist-header">
                  <div>
                    <Title level={5} style={{ margin: 0 }}>Playback playlist</Title>
                    <Text type="secondary">Drag to rearrange</Text>
                  </div>
                  {onAddClip && (
                    <Button 
                      type="primary" 
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => setShowAddClipModal(true)}
                      disabled={isUpdating}
                      style={{
                        borderRadius: '6px',
                        background: 'linear-gradient(45deg, #1890ff, #36cfc9)',
                        border: 'none',
                        fontWeight: 500
                      }}
                    >
                      Add chunk
                    </Button>
                  )}
                </div>
                
                <DragDropContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
                  <Droppable droppableId="clips">
                    {(provided) => (
                      <div
                        {...provided.droppableProps}
                        ref={provided.innerRef}
                        className="clips-list"
                      >
                        {collectionClips.map((clip, index) => (
                          <Draggable key={clip.id} draggableId={clip.id} index={index}>
                            {(provided, snapshot) => (
                              <div
                                ref={provided.innerRef}
                                {...provided.draggableProps}
                                {...provided.dragHandleProps}
                                className={`clip-item ${
                                  index === currentClipIndex ? 'active' : ''
                                } ${snapshot.isDragging ? 'dragging' : ''}`}
                                onClick={() => {
                                  if (!snapshot.isDragging && !isUpdating) {
                                    handleClipSelect(index)
                                  }
                                }}
                              >
                                <div className="clip-drag-handle">
                                  <DragOutlined />
                                </div>
                                
                                <div className="clip-content">
                                  <div className="clip-title">
                                    {clip.title || clip.generated_title}
                                  </div>
                                  <div className="clip-meta">
                                    <Text type="secondary" style={{ fontSize: '12px' }}>
                                      {formatDuration(clip)} • Fraction: {(clip.final_score * 100).toFixed(0)}
                                    </Text>
                                  </div>
                                  {clip.recommend_reason && (
                                    <div className="clip-reason">
                                      <Text type="secondary" style={{ fontSize: '11px' }}>
                                        {clip.recommend_reason}
                                      </Text>
                                    </div>
                                  )}
                                </div>

                                <div className="clip-actions">
                                  <Tooltip title="Download chunk">
                                    <Button
                                      type="text"
                                      size="small"
                                      icon={<DownloadOutlined />}
                                      loading={downloadingClip === clip.id}
                                      disabled={isUpdating}
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleDownloadClip(clip.id)
                                      }}
                                    />
                                  </Tooltip>
                                  <Popconfirm
                                    title="Are you sure you want to remove this clip from the collection?? "
                                    onConfirm={(e) => {
                                      e?.stopPropagation()
                                      handleRemoveClip(clip.id)
                                    }}
                                    okText="Confirm"
                                    cancelText="Cancel"
                                    disabled={isUpdating}
                                  >
                                    <Button
                                      type="text"
                                      size="small"
                                      icon={<DeleteOutlined />}
                                      danger
                                      disabled={isUpdating}
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                  </Popconfirm>
                                </div>
                              </div>
                            )}
                          </Draggable>
                        ))}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                </DragDropContext>
              </div>
            </Col>
          </Row>
        </div>
      </div>
      
      {/* Add clip modal */}
      <AddClipToCollectionModal
        visible={showAddClipModal}
        clips={clips}
        existingClipIds={collection?.clip_ids || []}
        onCancel={() => setShowAddClipModal(false)}
        onConfirm={handleAddClips}
      />
    </Modal>
  )
}

export default CollectionPreviewModal 