import React, { useState } from 'react'
import { Modal, Steps, Card, Typography, Alert, Button, Space, Divider } from 'antd'
import { QuestionCircleOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons'

const { Paragraph, Text } = Typography
const { Step } = Steps

interface CookieHelperProps {
  visible: boolean
  onClose: () => void
}

const CookieHelper: React.FC<CookieHelperProps> = ({ visible, onClose }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [copied, setCopied] = useState(false)

  const steps = [
    {
      title: 'LoginBSite',
      description: 'Log in in browserBSite account',
      content: (
        <div>
          <Alert
            message="Step 1: LoginBSite"
            description="Please ensure that you have successfully logged into the browserBSite account"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. Open browser, access <Text code>https://www.bilibili.com</Text>
            </Paragraph>
            <Paragraph>
              2. Click the login button in the upper right corner
            </Paragraph>
            <Paragraph>
              3. Use yourBSite account login
            </Paragraph>
            <Paragraph>
              4. After confirming login success, you should see your username displayed in the upper right corner
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: 'Open developer tools',
      description: 'PressF12Open browser developer tools',
      content: (
        <div>
          <Alert
            message="Step 2: Open Developer Tools"
            description="Use shortcut keys to open the browser's developer tools"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              <Text strong>Windows/Linux:</Text> Press <Text code>F12</Text> Key
            </Paragraph>
            <Paragraph>
              <Text strong>Mac:</Text> Press <Text code>Command + Option + I</Text>
            </Paragraph>
            <Paragraph>
              Or right-click on a blank area of the page and select "Inspect".
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              The developer tools will open at the bottom or right side of the page, containing multiple tab pages
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: 'Switch toNetworkTag',
      description: 'FindNetwork(Network) tab',
      content: (
        <div>
          <Alert
            message="Step three: Switch toNetworkTag"
            description="Find in developer toolsNetworkTab"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. Find the tab page at the top of the developer tools
            </Paragraph>
            <Paragraph>
              2. Click <Text code>Network</Text> Tag
            </Paragraph>
            <Paragraph>
              3. EnsureNetworkThe panel is empty (if there is content, click the clear button))
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              NetworkThe tabs are used to monitor network requests on web pages, includingCookieInformation
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: 'Refresh page',
      description: 'RefreshBPage to capture requests',
      content: (
        <div>
          <Alert
            message="Step four: Refresh page"
            description="RefreshBPage to capture network requests"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. EnsureNetworkTab already opened
            </Paragraph>
            <Paragraph>
              2. Press <Text code>F5</Text> Or click the browser's refresh button
            </Paragraph>
            <Paragraph>
              3. ObserveNetworkRequest list shown in panel
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              After refresh, NetworkThe panel displays all network requests made during page loading
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: 'FindCookie',
      description: 'Find in request headersCookieInformation',
      content: (
        <div>
          <Alert
            message="Step five: FindCookieInformation"
            description="Find in any requestCookieField"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. AtNetworkIn the panel, find any request (usually the first one))
            </Paragraph>
            <Paragraph>
              2. Click that request; in the right-side panel, find <Text code>Headers</Text> Tag
            </Paragraph>
            <Paragraph>
              3. At <Text code>Request Headers</Text> Part found <Text code>Cookie</Text> Field
            </Paragraph>
            <Paragraph>
              4. CookieThe field value is the completeCookieString
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              CookieStrings are typically long, consisting of multiple key-value pairs separated by semicolons
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: 'CopyCookie',
      description: 'Copy completeCookieString',
      content: (
        <div>
          <Alert
            message="Step 6: CopyCookie"
            description="Copy completeCookieCopy string to clipboard"
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. Right‑click onCookieField value
            </Paragraph>
            <Paragraph>
              2. Select "Copy value" or"Copy value"
            </Paragraph>
            <Paragraph>
              3. Or double‑click to select entireCookieValue, then press <Text code>Ctrl+C</Text> Copy
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              Copied cookie string can be pasted directly into ClipFarm's cookie input box
            </Paragraph>
            <Alert
              message="Important notice"
              description="CookieThis includes your login information; please keep it secure and do not share it with others"
              type="warning"
              showIcon
            />
          </Card>
        </div>
      )
    }
  ]

  const handleCopy = () => {
    const cookieExample = "SESSDATA=your_sessdata_here; bili_jct=your_bili_jct_here; DedeUserID=your_dedeuserid_here"
    navigator.clipboard.writeText(cookieExample).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <Modal
      title={
        <Space>
          <QuestionCircleOutlined />
          <span>CookieGet guide</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="back" onClick={onClose}>
          Close
        </Button>,
        <Button
          key="copy"
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          onClick={handleCopy}
        >
          {copied ? 'Copied' : 'Copy Example'}
        </Button>
      ]}
      width={700}
    >
      <div style={{ marginBottom: 16 }}>
        <Alert
          message="CookieImport is the safest login method"
          description="Compared to scan login, CookieImport won't triggerBThe site's risk control mechanism, which is the most recommended login method. "
          type="success"
          showIcon
        />
      </div>

      <Steps current={currentStep} onChange={setCurrentStep} direction="vertical" size="small">
        {steps.map((step, index) => (
          <Step key={index} title={step.title} description={step.description} />
        ))}
      </Steps>

      <div style={{ marginTop: 24, padding: 16, backgroundColor: '#f5f5f5', borderRadius: 8 }}>
        {steps[currentStep].content}
      </div>

      <Divider />

      <Card size="small" title="CookieFormat example">
        <Paragraph code style={{ fontSize: '12px', wordBreak: 'break-all' }}>
          SESSDATA=your_sessdata_here; bili_jct=your_bili_jct_here; DedeUserID=your_dedeuserid_here; buvid3=your_buvid3_here
        </Paragraph>
        <Paragraph type="secondary" style={{ fontSize: '12px' }}>
          Note: ActualCookieThe value will be much longer than this example, containing more fields
        </Paragraph>
      </Card>
    </Modal>
  )
}

export default CookieHelper

