import React, { useState, useRef, useEffect } from 'react'
import { Input, Button, Space, message, Modal } from 'antd'
import { EditOutlined, CheckOutlined } from '@ant-design/icons'
import { projectApi } from '../services/api'
import MagicWandIcon from './icons/MagicWandIcon'

interface EditableCollectionTitleProps {
  title: string
  collectionId: string
  onTitleUpdate?: (newTitle: string) => void
  maxLength?: number
  style?: React.CSSProperties
  className?: string
}

const EditableCollectionTitle: React.FC<EditableCollectionTitleProps> = ({
  title,
  collectionId,
  onTitleUpdate,
  maxLength = 50,
  style,
  className
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(title)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const inputRef = useRef<any>(null)

  useEffect(() => {
    setEditValue(title)
  }, [title])

  useEffect(() => {
    if (!isEditing) {
      setEditValue(title)
    }
  }, [title, isEditing])

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      // TextAreaComponent is missingselectMethod, usesetSelectionRangeReplace
      if (inputRef.current.setSelectionRange) {
        inputRef.current.setSelectionRange(0, inputRef.current.value.length)
      }
    }
  }, [isEditing])

  const handleStartEdit = () => {
    setEditValue(title)
    setIsEditing(true)
  }

  const handleCancel = () => {
    setEditValue(title)
    setIsEditing(false)
  }

  const handleSave = async () => {
    const trimmedValue = editValue.trim()

    if (!trimmedValue) {
      message.error('Title cannot be empty')
      return
    }

    if (trimmedValue.length > maxLength) {
      message.error(`Title cannot exceed ${maxLength} characters`)
      return
    }

    if (trimmedValue === title) {
      setIsEditing(false)
      return
    }

    setLoading(true)
    try {
      await projectApi.updateCollectionTitle(collectionId, trimmedValue)
      message.success('Title updated successfully')
      setIsEditing(false)
      onTitleUpdate?.(trimmedValue)
    } catch (error: any) {
      console.error('Update title failed:', error)
      message.error(error.userMessage || error.message || 'Failed to update title')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateTitle = async () => {
    console.log('Generating collection title, collectionId:', collectionId)
    setGenerating(true)
    try {
      const result = await projectApi.generateCollectionTitle(collectionId)
      console.log('Collection title result:', result)
      if (result.success && result.generated_title) {
        setEditValue(result.generated_title)
        message.success('Title generated successfully. You can edit it or click Save.')
      } else {
        message.error('Failed to generate title')
      }
    } catch (error: any) {
      console.error('Failed to generate title:', error)
      message.error(error.userMessage || error.message || 'Failed to generate title')
    } finally {
      setGenerating(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  if (isEditing) {
    return (
      <Modal
        title="Edit Collection Title"
        open={isEditing}
        onCancel={handleCancel}
        footer={null}
        width={600}
        destroyOnClose
        maskClosable={false}
      >
        <div style={{ marginBottom: '16px' }}>
          <Input.TextArea
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyPress}
            maxLength={maxLength}
            placeholder="Enter collection title"
            autoSize={{ minRows: 3, maxRows: 8 }}
            style={{ 
              resize: 'none',
              fontSize: '14px',
              lineHeight: '1.5'
            }}
          />
          <div style={{ 
            textAlign: 'right', 
            marginTop: '8px', 
            fontSize: '12px', 
            color: '#999' 
          }}>
            {editValue.length}/{maxLength}
          </div>
        </div>
        
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center' 
        }}>
          <Button 
            onClick={handleCancel}
            disabled={loading || generating}
          >
            Cancel
          </Button>
          
          <Space>
            <Button
              icon={<MagicWandIcon />}
              loading={generating}
              onClick={handleGenerateTitle}
              disabled={loading}
            >
              AI Generate
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              loading={loading}
              onClick={handleSave}
              disabled={generating}
            >
              Save
            </Button>
          </Space>
        </div>
      </Modal>
    )
  }

  return (
    <div
      style={{
        cursor: 'pointer',
        padding: '4px 0',
        ...style
      }}
      className={className}
      onClick={handleStartEdit}
      title="Click to edit collection title"
    >
      <span style={{ 
        wordBreak: 'break-word',
        lineHeight: '1.5',
        fontSize: '14px',
        minHeight: '20px',
        display: 'inline'
      }}>
        {title}
        <EditOutlined 
          style={{ 
            color: '#1890ff', 
            fontSize: '12px',
            opacity: 0.7,
            transition: 'opacity 0.2s',
            marginLeft: '6px',
            display: 'inline'
          }}
        />
      </span>
    </div>
  )
}

export default EditableCollectionTitle
