import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { Layout } from 'antd'
import HomePage from './pages/HomePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import SettingsPage from './pages/SettingsPage'
import CampaignsPage from './pages/CampaignsPage'
import CampaignDetailPage from './pages/CampaignDetailPage'
import AffiliatePage from './pages/AffiliatePage'
import Header from './components/Header'
import { trackPageview } from './appEvents/client'

const { Content } = Layout

// HashRouter Please upload manually now pageview(init Auto-upload has already been disabled pageview)
function usePageviewTracking() {
  const location = useLocation()
  useEffect(() => {
    trackPageview(location.pathname + location.search)
  }, [location.pathname, location.search])
}

function App() {
  useEffect(() => {
    console.log('🎬 App initialized')
  }, [])
  usePageviewTracking()

  return (
    <Layout>
      <Header />
      <Content>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/project/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/campaigns" element={<CampaignsPage />} />
          <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/affiliate" element={<AffiliatePage />} />
        </Routes>
      </Content>
    </Layout>
  )
}

export default App
