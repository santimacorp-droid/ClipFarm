# BAlternative login solutions guide

## Problem backgroundBSite's risk control mechanisms can cause login failures or account restrictions. To solve this problem, we provide multiple alternative login options. 

## Supported login methods

### 1. CookieImport login ⭐⭐⭐⭐⭐ (Recommend)

**Advantages: **
- Will not triggerBSite's risk control)

**Disadvantages: **
- Need to obtain manuallyCookie
- CookieHas time limits, requires regular updates

**Use cases: **
- For everyday use

**Usage method: **
1. Log in in browserBSite
2. ByF12Open developer tools
3. Switch toNetworkTab page
4. Refresh page, find any request
5. Copy in request headersCookieField values
6. Paste intoAutoClipOf/theCookieIn the input field

### 2. Account password login ⭐⭐⭐

**Advantages: **
- Intuitive operation

**Disadvantages: **
- May need to handle verification codes

**Use cases: **
- New users' first loginCookieIn this case

**Usage method: **
1. InputBSite username/Phone number
2. Enter password
3. Set nickname
4. Click login

### 3. Scan QR code for login ⭐⭐

**Advantages: **
- Simple operation

**Disadvantages: **
- Easy to triggerBSite's risk controlBSiteAPP

**Use cases: **
- For temporary testing

**Usage method: **
1. Click "Start scanning QR code to log in""
2. UseBSiteAPPScan QR code
3. AtAPPConfirm login

### 4. Third-party login ⭐⭐

**Advantages: **
- No needBSite account passwords

**Disadvantages: **
- Third-party account required

**Use cases: **
- Has WeChat/QQAccount user(s)BAccount password information

## Recommended usage strategy

### Recommended for daily use
1. **Primary: CookieImport**
   - The most stable and reliable optionCookie

2. **Alternative option: standard username/password login**
   - WhenCookieWhen invalid, use

### Batch account managementCookieImport methodCookieUpdate mechanism

### New user guidance
1. Provide detailedCookieGet tutorial
2. Create visual operational guidelines
3. One-click copy support

## Security considerations

### CookieSecurity
- CookieContains login credentials. Please keep them safe.Cookie
- Clear after use is completed

### Account security

## Technical implementation

### BackendAPI
```python
# CookieVerify
async def validate_bilibili_cookies(cookies: dict) -> dict:
    """VerifyBSiteCookieValidity"""
    # UseCookieAccess user informationAPI
    # Return verification result and user information

# Account password login
async def bilibili_password_login(username: str, password: str) -> dict:
    """BAccount password login"""
    # Handle captcha and login flow
    # Return login result
```

### Frontend component
```typescript
// Multiple login method support
const loginMethods = [
  { id: 'cookie', name: 'CookieImport', recommended: true },
  { id: 'password', name: 'Username/password', recommended: true },
  { id: 'qr', name: 'Scan QR code for login', recommended: false },
  { id: 'wechat', name: 'WeChat login', recommended: false },
  { id: 'qq', name: 'QQLogin', recommended: false }
]
```

## Troubleshooting

### Frequently asked questions

1. **CookieInvalid**
   - CheckCookieExpiration statusCookieCorrect formatCookie

2. **Account password login failed**
   - Check if username and password are correctCookieImport

3. **Scan login timeout**
   - Check network connectionBSiteAPPVersion

### Debugging methods
1. View browser console error messages
2. Check network request status codes
3. View backend logs
4. Use developer tools to analyze

## Release notes

### v1.0.0
- AddCookieImport login

### Future plansCookieAuto-update function

## Related documentation

- [CookieGet detailed tutorial](./COOKIE_GETTING_GUIDE.md)
- [BSiteAPIAPI documentation](./BILIBILI_API_DOCS.md)
- [Security best practices](./SECURITY_BEST_PRACTICES.md)

