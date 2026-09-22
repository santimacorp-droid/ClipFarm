# BSite management function guide

## 📋 Function overviewBThe account management feature is designed for beginners, offering the simplest and most intuitive account and posting experience. 

## 🎯 Core functionality

### 1. Account management
- **add account**: SupportCookieImport method, secure and reliable
- **Multi-account support**: Can add multipleBSite account
- **account status**: Real-time display of account health status
- **Quick delete**: One-click delete unnecessary accounts

### 2. submit contribution
- **segmented submission**: Post directly from slice details page
- **Batch upload**: Support uploading multiple slices simultaneously
- **Account selection**: Flexible choice of posting account
- **Section settings**: SupportBAll sections of site

## 🚀 usage flow

### Step one: addBSite account

1. **Enter settings page**
   - Click the left navigation bar's "Settings""B"Labels" tab for site account management

2. **add account**
   - Click "Manage"BAccount button

3. **RetrieveCookie**
   - OpenBSite and loginF12Open developer toolsNetworkTabRequest HeadersFound inCookieField — copyCookieof values (not including"Cookie: "Prefix)

4. **import accounts**
   - Input account nickname (for identification)CookieContent"

### Step two: post slice

1. **select segments**
   - Enter project details page

2. **Configure posting information**
   - Select to useBAccount)

3. **Start posting**
   - Click the "Start Posting" button

## 💡 usage tips

### Cookieget tips
- **Recommended browser**: Chrome, Edge, Firefox
- **Get location**: Developer tools → Network → Any request → Request Headers
- **Format requirements**: CompleteCookieString, separated by semicolons
- **Validity period**: CookieUsually has7-30Day validity, re-obtain after expiration

### Account management tips
- **nickname set**: Use meaningful nicknames, such as "main account," "backup account""
- **Regular check**: It is recommended to regularly check account status and update expired accounts in a timely mannerCookie
- **Multi-account strategy**: You can set up accounts for different purposes, such as "test account," "official account""

### Posting optimization tips
- **title optimization**: Use engaging titles, avoiding excessively long ones
- **Select section**: Choose suitable categories to improve recommendation results
- **Tag settings**: Add relevant tags to increase visibility
- **Batch upload**: For multiple related slices, you can post in bulk

## ⚠️ Important notes

### security alert
- **CookieSecure**: CookieContains login information, please keep it safe
- **Account security**: Do not log in on public devices
- **periodic updates**: Recommend regular updatesCookie, Avoid expiration

### Usage limits
- **Upload limit**: FollowBSite upload rules and limits
- **Content standards**: Ensure content complies withBSite community guidelines
- **rate limiting**: Avoid frequent posting to prevent triggering anti-risk measures

### Troubleshooting
- **CookieInvalid**: CheckCookieFormat and validity period
- **Upload failed**: Check network connection and account status
- **Section error**: Confirm sectionIDvalid?

## 🔧 technical details

### Supported login methods
- **CookieImport** (Recommended): Most secure, will not trigger risk control
- **Account password login**: Traditional method, may have CAPTCHA
- **scan-to-login**: NeedBSiteAPP, May trigger risk control

### Upload mechanism
- **DirectAPICall**: UseBSite officialAPI, Stable and reliable
- **segmented upload**: Support large file slicing upload
- **retry mechanism**: Automatic retry of failed uploads
- **Progress tracking**: Show upload progress in real time

## 📞 Technical support: 
1. Check system logs for detailed error information
2. Check network connection and account status
3. refresh againCookieAnd update account
4. Contact technical support for assistance

---

*Last updated: 2024Year12Month*
