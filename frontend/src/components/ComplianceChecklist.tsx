import React from 'react'
import { Space, Typography, Tag } from 'antd'
import { CheckCircle2, XCircle, UserCheck, Clock } from 'lucide-react'
import { ComplianceItem } from '../api/campaigns'

const { Text } = Typography

interface PublishLogEntry {
  platform: string
  post_url?: string
  published_at: string
  expires_at: string
}

interface ComplianceChecklistProps {
  items: ComplianceItem[]
  publishLog?: PublishLogEntry[]
}

export const ComplianceChecklist: React.FC<ComplianceChecklistProps> = ({ items, publishLog }) => {
  if (!items || items.length === 0) {
    return <Text type="secondary">No compliance checklist criteria specified.</Text>
  }

  const processedItems = items.map((it) => {
    // If the rule is about staying live for X days (e.g. "Post stays live for at least 30 days")
    const isLiveRule = /stay.*live|min.*day|\d+\s*day/i.test(it.item)
    if (isLiveRule && publishLog && publishLog.length > 0) {
      const now = new Date()
      const activePosts = publishLog.filter((p) => !p.expires_at || new Date(p.expires_at) > now)
      const expiredPosts = publishLog.filter((p) => p.expires_at && new Date(p.expires_at) <= now)

      if (activePosts.length > 0) {
        const platforms = activePosts.map((p) => p.platform).join(', ')
        return {
          ...it,
          status: 'pass' as const,
          value: `Live on ${platforms}`
        }
      } else if (expiredPosts.length > 0) {
        const platforms = expiredPosts.map((p) => p.platform).join(', ')
        return {
          ...it,
          status: 'fail' as const,
          value: `Expired on ${platforms}`
        }
      }
    }
    return it
  })

  const renderStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return <CheckCircle2 size={16} className="text-emerald-500" style={{ color: '#10b981' }} />
      case 'fail':
        return <XCircle size={16} className="text-rose-500" style={{ color: '#ef4444' }} />
      case 'manual':
        return <UserCheck size={16} className="text-amber-500" style={{ color: '#f59e0b' }} />
      case 'pending':
      default:
        return <Clock size={16} className="text-slate-400" style={{ color: '#94a3b8' }} />
    }
  }

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
        return <Tag color="success">PASS</Tag>
      case 'fail':
        return <Tag color="error">FAIL</Tag>
      case 'manual':
        return <Tag color="warning">MANUAL CHECK</Tag>
      case 'pending':
      default:
        return <Tag color="default">PENDING LIVE</Tag>
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {processedItems.map((it, idx) => (
        <div
          key={idx}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 12px',
            borderRadius: '6px',
            background: 'var(--ac-card-subtle, rgba(255, 255, 255, 0.03))',
            border: '1px solid var(--ac-line-2, rgba(255, 255, 255, 0.06))',
          }}
        >
          <Space direction="horizontal" size={8} style={{ display: 'flex', alignItems: 'center' }}>
            {renderStatusIcon(it.status)}
            <Text style={{ fontSize: '13px', fontWeight: 500 }}>{it.item}</Text>
            {it.value && (
              <Text type="secondary" style={{ fontSize: '12px' }}>
                ({it.value})
              </Text>
            )}
          </Space>
          <div>{renderStatusBadge(it.status)}</div>
        </div>
      ))}
    </div>
  )
}

export default ComplianceChecklist
