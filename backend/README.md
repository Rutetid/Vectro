# Vectro Backend API

Node.js + Express backend for Vectro - Government Scheme Discovery Platform. Uses Supabase for authentication and database, integrates with RAG service for AI-powered scheme discovery.

## Tech Stack

- **Runtime**: Node.js (ES Modules)
- **Framework**: Express.js
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth (with Google OAuth)
- **Storage**: Supabase Storage
- **RAG Integration**: Axios client for RAG service

## Project Structure

```
backend/
├── config/
│   ├── supabase.js      # Supabase client configuration
│   └── rag.js           # RAG service axios client
├── database/
│   └── schema.sql       # Database schema and RLS policies
├── middleware/
│   └── auth.js          # JWT authentication middleware
├── routes/
│   ├── auth.js          # Authentication endpoints
│   ├── users.js         # User profile & saved schemes
│   ├── schemes.js       # Scheme discovery & details
│   └── documents.js     # Document management
├── utils/
│   └── helpers.js       # Utility functions
├── uploads/             # Local uploads directory (unused - using Supabase Storage)
├── .env.example         # Environment variables template
├── .gitignore
├── package.json
└── server.js            # Main application entry point
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
npm install
```

### 2. Setup Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Wait for the project to be ready (takes ~2 minutes)
3. Get your project credentials:
   - Go to **Project Settings** → **API**
   - Copy the **Project URL** and **anon public key**
   - Copy the **service_role key** (keep this secret!)

### 3. Configure Database Schema

1. Go to your Supabase project
2. Click on **SQL Editor** in the left sidebar
3. Open the file `backend/database/schema.sql`
4. Copy the entire SQL content
5. Paste it into the SQL Editor and click **Run**
6. This will create all necessary tables, indexes, and Row Level Security policies

### 4. Enable Google OAuth (Optional)

1. In Supabase Dashboard, go to **Authentication** → **Providers**
2. Enable **Google** provider
3. Add your Google OAuth credentials:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create OAuth 2.0 credentials
   - Add authorized redirect URI: `https://your-project.supabase.co/auth/v1/callback`
4. Copy Client ID and Client Secret to Supabase

### 5. Setup Storage Bucket

The database schema automatically creates the `documents` storage bucket, but you can verify:

1. Go to **Storage** in Supabase Dashboard
2. Verify `documents` bucket exists
3. Bucket should be **private** (not public)
4. RLS policies are already set up via schema.sql

### 6. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
PORT=5000
NODE_ENV=development

# Supabase (get from Project Settings → API)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# RAG Service
RAG_SERVICE_URL=http://localhost:7860

# Frontend (for CORS)
FRONTEND_URL=http://localhost:5173
```

### 7. Start the Server

**Development mode (with auto-reload):**

```bash
npm run dev
```

**Production mode:**

```bash
npm start
```

The server will start on `http://localhost:5000`

## API Endpoints

### Health Check

```
GET /health
```

### Authentication Routes (`/api/auth`)

| Method | Endpoint    | Description               | Auth Required |
| ------ | ----------- | ------------------------- | ------------- |
| POST   | `/signup`   | Register new user         | No            |
| POST   | `/login`    | Login with email/password | No            |
| POST   | `/google`   | Initiate Google OAuth     | No            |
| GET    | `/callback` | OAuth callback handler    | No            |
| POST   | `/logout`   | Logout user               | Yes           |
| GET    | `/me`       | Get current user          | Yes           |
| POST   | `/refresh`  | Refresh access token      | No            |

### User Routes (`/api/users`)

| Method | Endpoint                           | Description         | Auth Required |
| ------ | ---------------------------------- | ------------------- | ------------- |
| GET    | `/:userId/profile`                 | Get user profile    | Yes           |
| PUT    | `/:userId/profile`                 | Update user profile | Yes           |
| GET    | `/:userId/saved-schemes`           | Get saved schemes   | Yes           |
| POST   | `/:userId/saved-schemes`           | Save a scheme       | Yes           |
| DELETE | `/:userId/saved-schemes/:schemeId` | Remove saved scheme | Yes           |

### Scheme Routes (`/api/schemes`)

| Method | Endpoint     | Description              | Auth Required |
| ------ | ------------ | ------------------------ | ------------- |
| POST   | `/discover`  | Discover schemes via RAG | Optional      |
| GET    | `/:schemeId` | Get scheme details       | No            |
| GET    | `/`          | List all schemes         | No            |
| POST   | `/`          | Create scheme (admin)    | Yes           |

### Document Routes (`/api/documents`)

| Method | Endpoint                    | Description            | Auth Required |
| ------ | --------------------------- | ---------------------- | ------------- |
| GET    | `/:userId`                  | Get user documents     | Yes           |
| PUT    | `/:userId/:documentId`      | Update document status | Yes           |
| POST   | `/:userId/upload`           | Upload document file   | Yes           |
| DELETE | `/:userId/:documentId/file` | Delete document file   | Yes           |

## Authentication Flow

### Email/Password Signup

```javascript
POST / api / auth / signup;
Body: {
  (email, password, name);
}
Response: {
  (user, session);
}
```

### Email/Password Login

```javascript
POST / api / auth / login;
Body: {
  (email, password);
}
Response: {
  (user, session);
}
```

### Google OAuth

1. Client calls `POST /api/auth/google`
2. Backend returns OAuth URL
3. User authenticates with Google
4. Google redirects to `GET /api/auth/callback?code=...`
5. Backend exchanges code for session
6. Returns user and session data

### Using Protected Routes

Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## RAG Integration

The `/api/schemes/discover` endpoint integrates with the RAG service:

**Request Format:**

```javascript
{
  gender: "male",
  age: "25",
  state: "Maharashtra",
  residence: "urban",
  category: "general",
  income: "5",  // in Lakhs
  occupation: "private"
}
```

**Backend transforms to RAG format:**

```javascript
{
  age: 25,
  gender: "male",
  income: 500000,  // converted to rupees
  state: "Maharashtra",
  occupation: "private",
  caste: "general",  // mapped from category
  residency: "urban"  // mapped from residence
}
```

## Database Schema

### Tables

1. **profiles** - User basic info (extends auth.users)
2. **user_profiles** - Eligibility data (age, income, etc.)
3. **schemes** - Government scheme details
4. **saved_schemes** - User's saved schemes (junction table)
5. **user_documents** - Document tracking and file URLs

### Row Level Security (RLS)

All tables have RLS enabled with policies ensuring:

- Users can only access their own data
- Everyone can read public scheme data
- Document uploads are scoped to user folders

## Error Handling

All endpoints return consistent error format:

```javascript
{
  error: "Error Name",
  message: "Human-readable error message",
  stack: "..." // Only in development mode
}
```

HTTP Status Codes:

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `500` - Internal Server Error

## Development Tips

### Testing Authentication

```bash
# Signup
curl -X POST http://localhost:5000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","name":"Test User"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

### Testing Protected Routes

```bash
# Get user profile (replace TOKEN with actual token)
curl -X GET http://localhost:5000/api/users/{userId}/profile \
  -H "Authorization: Bearer TOKEN"
```

### Checking RAG Connection

```bash
# Health check
curl http://localhost:5000/health

# Test RAG discovery
curl -X POST http://localhost:5000/api/schemes/discover \
  -H "Content-Type: application/json" \
  -d '{"age":"25","state":"Delhi","residence":"urban","category":"general","income":"5","occupation":"private"}'
```

## Environment Variables

| Variable                    | Required | Description                                   |
| --------------------------- | -------- | --------------------------------------------- |
| `PORT`                      | No       | Server port (default: 5000)                   |
| `NODE_ENV`                  | No       | Environment (development/production)          |
| `SUPABASE_URL`              | Yes      | Your Supabase project URL                     |
| `SUPABASE_ANON_KEY`         | Yes      | Supabase anonymous key                        |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes      | Supabase service role key                     |
| `RAG_SERVICE_URL`           | Yes      | RAG service endpoint                          |
| `FRONTEND_URL`              | Yes      | Frontend URL for CORS                         |
| `JWT_SECRET`                | No       | Custom JWT secret (if not using Supabase JWT) |

## Deployment

### Prerequisites

- Node.js 18+ runtime
- Supabase project configured
- RAG service running and accessible

### Steps

1. Set all environment variables
2. Ensure database schema is applied
3. Run `npm start`
4. Configure reverse proxy (nginx/Apache) if needed
5. Enable HTTPS in production

### Recommended Platforms

- **Railway** - Easy Node.js deployment
- **Render** - Free tier available
- **Vercel** - Serverless functions
- **DigitalOcean App Platform**
- **AWS Elastic Beanstalk**

## Security Considerations

1. **Never commit `.env` file** - Contains sensitive keys
2. **Use service_role key carefully** - Has full database access
3. **Enable RLS on all tables** - Already configured in schema.sql
4. **Validate all user input** - Sanitization included in helpers
5. **Use HTTPS in production** - Required for OAuth
6. **Rotate keys regularly** - Especially service_role key
7. **Enable rate limiting** - Consider adding middleware
8. **Monitor Supabase logs** - Check for suspicious activity

## Troubleshooting

### "Unauthorized" errors

- Check token is valid and not expired
- Verify Authorization header format: `Bearer <token>`
- Ensure Supabase keys are correct in `.env`

### RAG service connection fails

- Verify `RAG_SERVICE_URL` is correct
- Check RAG service is running on specified port
- Test with: `curl http://localhost:7860/health` (if RAG has health endpoint)

### Database errors

- Verify schema.sql was run successfully
- Check RLS policies are enabled
- Use Supabase Dashboard → SQL Editor to test queries
- Check service_role key has proper permissions

### CORS errors

- Verify `FRONTEND_URL` matches your frontend origin
- Check browser console for actual origin
- Ensure credentials: true in frontend requests

## License

MIT

## Support

For issues, please create a GitHub issue or contact the development team.
