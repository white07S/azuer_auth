# Azure Authentication Chat Application

A multi-user chat application with Azure Active Directory authentication and Azure OpenAI integration. This application implements device code authentication flow, session management, and automatic token refresh for a seamless chat experience.

## Features

- **Azure AD Device Code Authentication**: Secure login using Azure device code flow
- **Multi-User Support**: Each user has their own session and isolated environment
- **Session Management**: User-specific folders and session persistence
- **Automatic Token Refresh**: Silent token refresh before expiry
- **Azure OpenAI Integration**: Chat with Azure OpenAI using user-specific credentials
- **Responsive Messaging**: Seamless request/response chat flow
- **Clean UI**: Light theme with responsive design

## Architecture

### Backend (FastAPI)
- **Authentication Service**: Handles Azure AD device code flow
- **Session Manager**: Manages user sessions and data persistence
- **Token Manager**: Handles token storage and automatic refresh
- **OpenAI Service**: Integrates with Azure OpenAI using user credentials
- **Role-Aware REST APIs**: Enforce Azure AD roles across requests

### Frontend (React)
- **Login Modal**: Device code authentication UI
- **Chat Interface**: Rich messaging experience with contextual history
- **Session Management**: Automatic token refresh monitoring
- **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

- Python 3.9+
- Node.js 16+
- Azure CLI installed and configured
- Azure AD tenant with appropriate permissions
- Azure OpenAI resource deployed

## Setup

### Backend Configuration

1. Navigate to the backend directory:
```bash
cd backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the example environment file:
```bash
cp .env.example .env
```

4. Configure your `.env` file with your Azure settings:
```env
# Azure AD Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=  # Optional

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Session Management
SESSION_DIR=./sessions
SESSION_TIMEOUT_HOURS=24

# Token Management
TOKEN_REFRESH_BUFFER_MINUTES=5
TOKEN_REFRESH_CHECK_INTERVAL_SECONDS=60

# Role Mappings (optional)
ROLE_MAPPINGS=group-id-1:admin,group-id-2:user
ALLOWED_ROLES=admin,user,viewer
```

### Frontend Configuration

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

## Running the Application

### Start the Backend

1. From the backend directory:
```bash
python main.py
```

The backend will start on `http://localhost:8000`

### Start the Frontend

1. From the frontend directory:
```bash
npm start
```

The frontend will start on `http://localhost:3000`

## Usage

1. Open your browser and navigate to `http://localhost:3000`

2. Click "Sign In with Azure" to start authentication

3. Copy the device code displayed in the modal

4. Click "Open Authentication Page" or manually navigate to `https://microsoft.com/devicelogin`

5. Enter the device code and authenticate with your Azure credentials

6. Once authenticated, you'll be redirected to the chat interface

7. Start chatting with the AI assistant!

## Key Features Explained

### Multi-User Support
- Each user gets a separate session folder under `./sessions/{session_id}`
- Azure CLI credentials are stored per session
- Users can have multiple concurrent sessions

### Token Management
- Tokens are automatically refreshed 5 minutes before expiry
- Silent refresh runs in the background
- Failed refreshes trigger re-authentication

### Session Persistence
- Sessions persist across page refreshes
- Session data stored in browser localStorage
- Server-side session validation on each request

### Security Features
- Device code authentication (no client secrets)
- Session isolation between users
- Automatic session cleanup
- Token expiry monitoring

## API Endpoints

### Authentication
- `POST /api/auth/start` - Start device code authentication
- `GET /api/auth/status/{session_id}` - Check authentication status
- `POST /api/auth/complete` - Complete authentication
- `POST /api/auth/refresh/{session_id}` - Refresh token
- `POST /api/auth/logout/{session_id}` - Logout session

### Chat
- `POST /api/chat/message` - Send chat message

### Session
- `GET /api/session/{session_id}/info` - Get session information
- `GET /api/health` - Health check

> Protected endpoints require both `X-Session-ID` and `Authorization: Bearer <token>` headers.

## Troubleshooting

### Authentication Issues
- Ensure Azure CLI is installed: `az --version`
- Verify tenant ID in configuration
- Check user has appropriate permissions in Azure AD

### Token Refresh Issues
- Check `TOKEN_REFRESH_BUFFER_MINUTES` setting
- Verify Azure CLI can refresh tokens: `az account get-access-token`
- Check session folder permissions

### API Access Issues
- Ensure `X-Session-ID` and `Authorization` headers are present on protected requests
- Check CORS settings match frontend URL
- Verify session ID is valid and active

## Development

### Backend Development
```bash
cd backend
python main.py  # starts main router and child routers from routers/config.json
```

### Frontend Development
```bash
cd frontend
npm start
```

### Adding Role-Based Access
Configure role mappings in `.env`:
```env
ROLE_MAPPINGS=group-id-1:admin,group-id-2:user
ALLOWED_ROLES=admin,user,viewer
```

## Production Deployment

### Backend
1. Use production ASGI server (e.g., Gunicorn with Uvicorn workers)
2. Configure proper CORS origins
3. Use secure session storage
4. Enable HTTPS

### Frontend
1. Build production bundle: `npm run build`
2. Serve with nginx or similar
3. Configure environment variables
4. Enable HTTPS

## Security Considerations

1. **Always use HTTPS in production**
2. **Validate and sanitize all inputs**
3. **Implement rate limiting**
4. **Use secure session storage**
5. **Regular token rotation**
6. **Audit logging for authentication events**
7. **Require `Authorization: Bearer` tokens alongside `X-Session-ID` on protected routes**

## License

This project is provided as-is for demonstration purposes.

## Support

For issues and questions, please check the documentation or raise an issue in the repository.
