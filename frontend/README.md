# Auto Clips Frontend

based on React + TypeScript + Vite + Ant Design Frontend app for automated video segmentation. 

## Feature functionality

### 🎯 Core features
- **Video upload**: Support drag-and-drop upload of video files and subtitle files
- **Intelligent processing**: AI Style guidelines
- **Fragment management**: View, edit, download video segments
- **Create collection**: AI Recommended collections + Manual create collection
- **Real-time monitoring**: 处理进度实时反馈

### 🎨 User interface
- **Modern design**: based on Ant Design Component library
- **Responsive layout**: Supports desktop and mobile
- **Intuitive operations**: 拖拽排序, 一键下载
- **Status feedback**: Clear processing states and progress display

## technology stack

- **Frontend framework**: React 18 + TypeScript
- **Build tool**: Vite
- **UI component**: Ant Design
- **State management**: Zustand
- **route**: React Router DOM
- **HTTP client**: Axios
- **Drag-and-drop feature**: React Beautiful DnD
- **Video playback**: React Player
- **File upload**: React Dropzone

## Getting started

### Environment requirements
- Node.js >= 16
- npm or yarn

### Install dependencies
```bash
npm install
# or
yarn install
```

### State management using
```bash
npm run dev
# or
yarn dev
```

access http://localhost:3000

### Build production version
```bash
npm run build
# or
yarn build
```

## Project structure

```
frontend/
├── public/                 # Static resources
├── src/
│   ├── components/         # Reusable components
│   │   ├── Header.tsx      # Page header
│   │   ├── FileUpload.tsx  # File upload component
│   │   ├── ProjectCard.tsx # Project cards
│   │   ├── ClipCard.tsx    # Video clip cards
│   │   └── CollectionCard.tsx # Collection cards
│   ├── pages/              # Page component
│   │   ├── HomePage.tsx    # Project homepage
│   │   └── ProjectDetailPage.tsx # Project details page
│   ├── services/           # API service
│   │   └── api.ts          # API Interface definition
│   ├── store/              # State management
│   │   └── useProjectStore.ts # Project status
│   ├── App.tsx             # Application main component
│   ├── main.tsx            # Application entry point
│   └── index.css           # Global styles
├── package.json
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript configuration
└── README.md
```

## Page explanation

### Project homepage (`/`)
- Project list view

### Project details page (`/project/:id`)
- Project info and processing status
- AI Assembly display

## Component description

### FileUpload
- Drag-and-drop and click upload

### ProjectCard
- Project info display

### ClipCard
- Video segment info

### CollectionCard
- Assembly info display

## API Interface `/api` Proxy and backend communication, main interfaces include:: 

- `GET /api/projects` - Get project list
- `POST /api/projects` - Create new project
- `GET /api/projects/:id` - Get project details
- `POST /api/projects/:id/upload` - Upload file
- `POST /api/projects/:id/process` - Starting processing
- `GET /api/projects/:id/status` - Get processing status
- `PUT /api/projects/:id/clips/:clipId` - Update fragment
- `PUT /api/projects/:id/collections/:collectionId` - Update collection
- `GET /api/projects/:id/download` - Download video

## Development instructions

### Frontend via Zustand Lightweight state management handles:

### Drag-and-drop sorting, one-click downloads, Ant Design Theme colors

### Type definitions TypeScript Type definitions ensure type safety. 

## Deployment instructions

### Development environment
```bash
npm run dev
```

### Production environment
```bash
npm run build
npm run preview
```

### Docker deploy
```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

## Future optimization

### Feature enhancement
- [ ] Online video editing
- [ ] Batch operations
- [ ] Launch development server
- [ ] User permission management
- [ ] Cloud storage integration

### Performance optimization
- [ ] Virtual scrolling
- [ ] Image lazy loading
- [ ] Code splitting
- [ ] Cache strategy

### User experience
- [ ] Keyboard shortcut support
- [ ] Theme switching
- [ ] internationalization
- [ ] Accessibility features

## Contribution guide

1. Fork project
2. Create feature branch
3. Commit changes
4. Push to branch
5. create Pull Request

## license

MIT License