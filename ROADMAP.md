# AutoClip Product roadmap

> Funnel find loss points, targeted optimization. 
> Compatibility requirement: **Hosted allowance credits billing · Video processing remains fully local · Both domestic and international (domestic first launch)· Individual developer + AI**. 

---

## 0. Preceding strategic framework

| dimension | choice | meaning |
|------|------|------|
| Monetization model | Hosted allowance credits | You paid for LLM Billing model on demand/Sell packages credits |
| Location handling | Pure local | Download/ffmpeg/Whisper On user machine, you don't bear compute power |
| market | Works internationally and domestically | **Domestic first-mover advantage, overseas Phase 3 Back on**(Avoid being slowed down by dual compliance right from the start)|
| Resources | individual + AI | Principle: **buy > generate**, Privacy policy and data retention required |

## 1. Core architecture decision. **Account, tracking, and billing require cloud backend server**——These two don't need cloud, low risk, directly improve "can post, looks good", that's now.". 
- **credits The essence of = Billing LLM Proxy**: The sole cloud service LLM Predictable and controllable. Therefore, free tier/Small feature unit/OpenAI/Gemini, press token Account deduction credits). **Always keep video processing local**, Your cloud cost is locked in at"LLM token + lightweight API/DB", Cloud backend creates new attack surface. Scale up gradually/Natural boundary for paid services: 
  - **free**: BYO-key(Self-managed instance key, Paid by yourself) or monthly free allowance credits. 
  - **Pro**: credits plan + Data model reserve). 

## 2. API calls through proxy server to Tongyi > generate)

| Capability | selection | reason |
|------|------|------|
| Cloud backend + authorization verification + DB | **Supabase**(Postgres + Auth + Edge Functions)| One-stop account solution/data/function, solo optimal economy |
| LLM Proxy + Measurement | **LiteLLM**(Open source proxy) placed in front of the backend | Unified multiple services provider + bundled with token Usage statistics, credits Basic accounting |
| Product analytics + event tracking code + Gradual/Phased + A/B | **PostHog** | Desktop-tier benefits gateway (advanced models, batch, no watermark, etc., unlocked by tiers) |
| crash/Error reporting | **Sentry** | Desktop version + Backend is connected to all |
| Payment (domestic))| WeChat Payment / Alipay (direct connection or) Ping++ Aggregation such as)| Phase 2 |
| Payment (international))| **Stripe** | Phase 3 |
| License/benefits | Self-built (save subscription status) Supabase, Desktop startup verification + Offline grace period)| Lightweight setup sufficient |

## 3. Phased implementation plan

### Phase 0 · Core capabilities (approx.) 2–4 Weekly, no handling of funds)
**target**: provide v1.1 Anonymous, can close, local buffer basic reporting (critical events: import, output, failure, settings(Apple Developer ID + notarize), Use managed services wherever possible(Intel / Windows / Linux; PBS with faster-whisper Being cross-platform already CI Build successful(`desktop-build.yml` Actually run verification) **Sentry** crash/Error reporting **PostHog**: Priority: homepage (first impression key)
- **Privacy policy + Data collection toggle**(Remove "open in new tab"**Update check / Automatic updates**(Tauri updater)

**Export standard**: Truly make it "can post, can update, can observe" product baseline.. 

### Phase 1 · account + Cloud skeleton (approximately) 4–8 week)
**target**: Establish cloud backbone, account creation allowed but optional **Supabase** Project(Auth + Postgres)
- Desktop login(**Anonymous first**: First make it usable, login unlocks synchronization/Limits) / device / Conversation model; PostHog Tracking data for pricing decisions(API key Recommendation, template library, slice sharing (with product watermark for promotion) credits Account ledger, subscription status fields

**Export standard**: Can register/Signature notarization. 

### Phase 2 · LLM Proxy + credits + Paid (domestic first launch, about 6–10 week)
**target**: Successful deduction flow → Closed loop for receiving payments. 
- **LiteLLM Proxy**: Desktop version LLM Still recommend local saving, sensitive information not sent to cloud) token Account deduction credits; retain BYO-key As free tier
- **credits Ledger / Book of accounts**: In-app/exception)
- **free / Pro hierarchical** + This is the biggest turning point, planning around "minimizing initial cost to build skeleton, then incrementally adding features")
- **Payment (domestic))**: WeChat/Alipay, credits plan + Subscription Phase 1 Data pricing bundling; launch **A/B Pricing**(PostHog experiment)

**Export standard**: Top-up, deduction, transaction history, fraud detection (frequency) Pro; Paid model with early adopters, subtitles. 

### Phase 3 · growth / Scale / Second market (ongongoing))
- **Overseas markets**: Stripe Payment + Deployment in overseas region + GDPR Go through: authorization, anti-abuse proxy, payment callback signature verification, key management/From "pure local desktop tool" to evolve into "accounted, dataed, commercialized" product. PostHog For real-running interface, do "designer eye" review and iterate and fix.), Web End companion & team collaboration

## 4. Cross-cutting concerns (span across stages)

- **privacy / Compliance**: credits One-stop API request/Transcribed text will flow through your LLM Proxy = You begin processing user content → Tracking must exist before launch; Cloud sync settings/Account compliance check before going live. 
- **secure**: China is subject to PII laws, tracking `/cso`(Security audit skill)Retention: use. 
- **Cost containment**: LLM Proxy should have rate limiting per user + single-time/Daily upper limit + Heavy reliance on managed services, conservative approach. 

## 5. UI Clean machine one-click installation, self-updating, online crash and basic usage funnel visibility + Ant Design Default appearance, function exists but is too "engineer default skin", lacks product identity.: 
1. **Determine direction**: `/design-shotgun` Release several visual direction comparisons, or `/design-consultation` Directly output a complete design system `DESIGN.md`(aesthetics/font/Color scheme/spacing/micro-interaction). 
2. **Rollout**: press `DESIGN.md` Redo per screen (home page) / Project details / settings / Progress), first capture high-frequency screens. 
3. **validate**: `/design-review` Suggested flow)> Project cards and progress tracking > Settings page > details/Slice preview. 

## 6. Users can top up, pay, and upgrade)

1. **First Phase 0 + UI Done**——As needed, reassess: cloud processing option (weak machine users ROI Highest level. 
2. Back on Phase 1 Cloud skeleton (account/No servers currently available. 
3. Phase 2 **Send only within China**, Technology selection (for indie devs, buy)(Phase 3). 
4. After login, associate user identity. 

---

> Login, backend access to see "who uses what", but no charges yet. `HANDOFF.md`. 
