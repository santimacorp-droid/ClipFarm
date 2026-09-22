# Contribution guideAutoClipProjects! We welcome all forms of contribution, including but not limited to: 

- 🐛 Bugfix/repair
- ✨ New feature development
- 📚 Document improvement
- 🧪 Test cases
- 💡 Feature suggestion
- 🎨 UI/UXimprovement

## Development environment setup

### 1. ForkAnd clone project

```bash
# ForkProject to yoursGitHubAccount, then clone
git clone https://github.com/your-username/autoclip.git
cd autoclip

# Add upstream repository
git remote add upstream https://github.com/original-username/autoclip.git
```

### 2. Set up development environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Configure environment variables
cp env.example .env
# edit.envFiles, enter necessary configurations
```

### 3. Start development server

```bash
# startupRedis
brew services start redis  # macOS
# or sudo systemctl start redis-server  # Linux

# Start backend
python -m uvicorn backend.main:app --reload --port 8000

# startupCelery Worker
celery -A backend.core.celery_app worker --loglevel=info

# Start frontend
cd frontend && npm run dev
```

## Development process

### 1. Create feature branch

```bash
# frommainBranch create new branch
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

### 2. Development guidelines

#### Code style

**Python (backend)**
- followPEP 8Conventions - useBlackCommunication with reviewersisortImport sortingdocstring

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Example function's docstring
    
    Args:
        param1: parameter/argument1description
        param2: parameter/argument2description
        
    Returns:
        Return value description
    """
    pass
```

**TypeScript (frontend)**
- useESLintandPrettier
- Component needs to be addedJSDocCommentsHooks
- followAnt DesignDesign specification

```typescript
/**
 * Example component description
 */
interface ExampleProps {
  /** Attribute description */
  title: string;
  /** Optional attribute descriptions */
  optional?: boolean;
}

const ExampleComponent: React.FC<ExampleProps> = ({ title, optional = false }) => {
  return <div>{title}</div>;
};
```

#### Commit message conventions: 

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**type (type):**
- `feat`: new feature
- `fix`: Bugfix/repair
- `docs`: Document update
- `style`: Code formatting adjustment
- `refactor`: Code refactoring
- `test`: Test-related
- `chore`: Build process or auxiliary tool changes

**example:**
```
feat(api): add video download endpoint
fix(ui): resolve upload modal display issue
docs(readme): update installation instructions
```

### 3. test

#### Backend testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Generate coverage report
pytest --cov=backend --cov-report=html
```

#### Frontend testing

```bash
cd frontend

# Run tests
npm test

# run/executionlintcheck
npm run lint

# Type checking
npm run type-check
```

### 4. Submit code

```bash
# Add changes
git add .

# Submit changes
git commit -m "feat(api): add video download endpoint"

# Push branch
git push origin feature/your-feature-name
```

### 5. creationPull Request

1. inGitHubCreate onPull Request
2. filling inPRtemplate
3. Ensure all checks pass
4. Wait for code review

## Code review process

### Review criteria

- ✅ Code follows project conventions
- ✅ Feature works properly
- ✅ Test case coverage
- ✅ Documentation has been updated
- ✅ No security vulnerabilities
- ✅ Performance impact assessment

### Review feedbackPRUpdates

## Report issue

### BugReportGitHub IssuesreportBugWhen including: 

1. **Environment information**
   - Operating system version
   - Pythonversion
   - Node.jsVersion

2. **Reproduction steps**
   - Detailed steps

3. **Error message**
   - Full error logs

4. **Additional information**
   - Relevant configuration files

### Feature suggestions: 

1. **Function description**
   - Detailed description

2. **Implementation plan**
   - Technical implementation

3. **Impact assessment**
   - On existing functionality

## Documentation contribution

### Document type

- 📖 User documentation
- 🔧 Developer documentation
- 🚀 Deployment guide
- ❓ Frequently asked questions
- 📝 APIdocumentation

### Documentation conventionMarkdownFormat

## Community conduct guidelines

### Our commitment

### Unacceptable behavior

## Contact information

- **GitHub Issues**: [projectIssues](https://github.com/your-username/autoclip/issues)
- **GitHub Discussions**: [Project discussion](https://github.com/your-username/autoclip/discussions)
- **email address/email**: support@autoclip.com

## ThanksAutoClipDevelopers who contribute to this project make it better!. 

---

**Many thanks for your contribution! ** 🎉
