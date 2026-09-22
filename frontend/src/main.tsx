import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { ConfigProvider, App as AntdApp, theme as antdTheme } from 'antd'
import enUS from 'antd/locale/en_US'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary'
import { ThemeProvider, useTheme } from './context/ThemeContext'
import { initAnalytics } from './appEvents/client'
import { trackLaunch } from './appEvents/lifecycle'
import './index.css'

// Global property registration / Update event key Language settings no-op, Initialization of product analytics)
initAnalytics()
// No tracking (no-op) + Plugin configuration/installation/Report startup completed automatically
void trackLaunch()

// Configure dayjs
dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)

// Set dayjs language
dayjs.locale('en')

function Root() {
  // Root-level error boundaries only; no network requests
  return (
    <ErrorBoundary showDetails={import.meta.env.DEV}>
      <App />
    </ErrorBoundary>
  )
}

function ThemedApp() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <ConfigProvider
      locale={enUS}
      theme={{
      algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
      token: {
        // Calm Premium tokens — see DESIGN.md
        colorPrimary: isDark ? '#5A8BFF' : '#2D6BFF',
        colorText: isDark ? '#ECEAE6' : '#1A1A19',
        colorTextSecondary: isDark ? '#A6A29B' : '#6E6B66',
        colorBgBase: isDark ? '#19181A' : '#F6F5F3',
        colorBgContainer: isDark ? '#211F22' : '#FFFFFF',
        colorBorder: isDark ? '#2C2A2D' : '#EBE9E4',
        colorBorderSecondary: isDark ? '#232124' : '#F0EEEA',
        borderRadius: 10,
        fontFamily: '"Geist","PingFang SC","Noto Sans SC",system-ui,-apple-system,sans-serif',
        controlHeight: 38,
      },
      components: {
        Button: { borderRadius: 999, controlHeight: 40, fontWeight: 500 },
        Select: { borderRadius: 10 },
        Card: { borderRadiusLG: 16 },
      },
    }}
    >
    <AntdApp>
      <React.StrictMode>
        <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Root />
        </HashRouter>
      </React.StrictMode>
    </AntdApp>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ThemeProvider>
    <ThemedApp />
  </ThemeProvider>,
)
