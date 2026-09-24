import React from 'react'
import { Layout, Button } from 'antd'
import { SettingOutlined, ArrowLeftOutlined, BulbOutlined, MoonOutlined, FireOutlined, CoffeeOutlined } from '@ant-design/icons'
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
      className="app-header"
      style={{
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '60px',
        lineHeight: 'normal',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        backgroundColor: 'var(--ac-card)',
        borderBottom: '1px solid var(--ac-line)',
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.3)',
      }}
    >
      {/* Wordmark — ClipFarm */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', height: '40px' }}
        onClick={() => navigate('/')}
      >
        <img
          src="/logo.png"
          alt="ClipFarm"
          style={{ width: '36px', height: '36px', borderRadius: '8px', objectFit: 'contain' }}
        />
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <span
            style={{
              fontFamily: 'var(--ac-font-serif)',
              fontSize: '19px',
              fontWeight: 700,
              color: 'var(--ac-ink)',
              letterSpacing: '0.5px',
              lineHeight: '22px'
            }}
          >
            ClipFarm
          </span>
          <span style={{ fontSize: '11px', color: 'var(--ac-sub)', letterSpacing: '0.2px', lineHeight: '14px' }}>
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
          icon={<FireOutlined style={{ color: '#ff4d4f' }} />}
          onClick={() => navigate('/campaigns')}
          style={{
            color: location.pathname.startsWith('/campaigns') ? '#1890ff' : 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 14px',
            background: 'var(--ac-card)',
            fontSize: '13px',
            fontWeight: location.pathname.startsWith('/campaigns') ? 600 : 400
          }}
        >
          Campaigns
        </Button>
        <Button
          type="text"
          icon={<SettingOutlined style={{ color: location.pathname === '/settings' ? '#1890ff' : 'var(--ac-sub)' }} />}
          onClick={() => navigate('/settings')}
          style={{
            color: location.pathname === '/settings' ? '#1890ff' : 'var(--ac-sub)',
            border: '1px solid var(--ac-line)',
            borderRadius: '999px',
            height: '36px',
            padding: '0 16px',
            background: 'var(--ac-card)',
            fontSize: '13px',
            fontWeight: location.pathname === '/settings' ? 600 : 400
          }}
        >
          Settings
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
          type="primary"
          icon={<CoffeeOutlined style={{ fontSize: '15px' }} />}
          href="https://ko-fi.com/santima"
          target="_blank"
          rel="noopener noreferrer"
          title="Buy the developer a coffee on Ko-fi!"
          style={{
            background: 'linear-gradient(135deg, #FF5E5B 0%, #FF7E67 100%)',
            borderColor: '#FF5E5B',
            color: '#ffffff',
            borderRadius: '999px',
            height: '36px',
            padding: '0 16px',
            fontSize: '13px',
            fontWeight: 600,
            boxShadow: '0 2px 10px rgba(255, 94, 91, 0.4)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          Support on Ko-fi
        </Button>
      </div>
    </AntHeader>
  )
}

export default Header
