import React from 'react'
import { Layout, Button } from 'antd'
import { SettingOutlined, ArrowLeftOutlined, BulbOutlined, MoonOutlined, ThunderboltOutlined, FireOutlined, ShopOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTheme } from '../context/ThemeContext'

const { Header: AntHeader } = Layout

// Calm Premium header — see DESIGN.md
const Header: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const isHomePage = location.pathname === '/'
  const { theme, toggleTheme } = useTheme()

  return (
    <AntHeader
      style={{
        padding: '0 56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        backdropFilter: 'blur(10px)',
        background: 'color-mix(in srgb, var(--ac-bg) 78%, transparent)',
        borderBottom: '1px solid var(--ac-line-2)',
      }}
    >
      {/* Wordmark — ClipFarm */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <img
          src="/logo.png"
          alt="ClipFarm"
          style={{ width: '36px', height: '36px', borderRadius: '8px', objectFit: 'contain' }}
        />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span
            style={{
              fontFamily: 'var(--ac-font-serif)',
              fontSize: '20px',
              fontWeight: 700,
              color: 'var(--ac-ink)',
              letterSpacing: '0.5px',
              lineHeight: 1.2
            }}
          >
            ClipFarm
          </span>
          <span style={{ fontSize: '11px', color: 'var(--ac-sub)', letterSpacing: '0.2px' }}>
            AI Short-Form Video Studio
          </span>
        </div>
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {!isHomePage && (
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/')}
            style={{ color: 'var(--ac-sub)', height: '36px', borderRadius: '999px' }}
          >
            Back
          </Button>
        )}
        <Button
          type="text"
          icon={<ShopOutlined style={{ color: '#1877F2' }} />}
          onClick={() => navigate('/affiliate')}
          style={{
            color: location.pathname.startsWith('/affiliate') ? '#1877F2' : 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 14px',
            background: 'var(--ac-card)',
            fontSize: '13px',
            fontWeight: location.pathname.startsWith('/affiliate') ? 600 : 400
          }}
        >
          Affiliate
        </Button>
        <Button
          type="text"
          icon={<FireOutlined style={{ color: '#ff4d4f' }} />}
          onClick={() => navigate('/campaigns')}
          style={{
            color: location.pathname.startsWith('/campaigns') ? '#1890ff' : 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 14px',
            background: 'var(--ac-card)',
            fontSize: '13px'
          }}
        >
          Campaigns
        </Button>
        <Button
          type="text"
          icon={theme === 'dark' ? <BulbOutlined /> : <MoonOutlined />}
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            color: 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            width: '36px',
            height: '36px',
            padding: 0,
            background: 'var(--ac-card)',
          }}
        />
        <Button
          type="text"
          icon={<ThunderboltOutlined style={{ color: '#faad14' }} />}
          onClick={() => navigate('/settings')}
          style={{
            color: 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 14px',
            background: 'var(--ac-card)',
            fontSize: '13px'
          }}
        >
          Tokens & Rates
        </Button>
        <Button
          type="text"
          icon={<SettingOutlined />}
          onClick={() => navigate('/settings')}
          style={{
            color: 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 16px',
            background: 'var(--ac-card)',
          }}
        >
          Settings
        </Button>
      </div>
    </AntHeader>
  )
}

export default Header
