import { useEffect, lazy, Suspense } from 'react'
import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import { Layout, Spin } from 'antd'
import HomePage from './pages/HomePage'
import Header from './components/Header'
import { trackPageview } from './appEvents/client'

const ProjectDetailPage = lazy(() => import('./pages/ProjectDetailPage'))
const ProcessingPage = lazy(() => import('./pages/ProcessingPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const CampaignsPage = lazy(() => import('./pages/CampaignsPage'))
const CampaignDetailPage = lazy(() => import('./pages/CampaignDetailPage'))

const { Content } = Layout

// Track page views on route change
function usePageviewTracking() {
  const location = useLocation()
  useEffect(() => {
    trackPageview(location.pathname + location.search)
  }, [location.pathname, location.search])
}

const PageLoader = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
    <Spin size="large" tip="Loading..." />
  </div>
)

function App() {
  useEffect(() => {
    console.log('🎬 ClipFarm initialized')
  }, [])
  usePageviewTracking()

  return (
    <Layout>
      <Header />
      <Content>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/project/:id" element={<ProjectDetailPage />} />
            <Route path="/projects/:id" element={<ProjectDetailPage />} />
            <Route path="/processing/:id" element={<ProcessingPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/campaigns" element={<CampaignsPage />} />
            <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
            <Route path="/affiliate" element={<Navigate to="/campaigns" replace />} />
            <Route path="/affiliate/*" element={<Navigate to="/campaigns" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Content>
    </Layout>
  )
}

export default App
