# Vectro Backend API Documentation

Complete API reference for the Vectro Government Scheme Discovery Platform backend.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Endpoints](#api-endpoints)
4. [Data Models](#data-models)
5. [Authentication Flow](#authentication-flow)
6. [Error Handling](#error-handling)
7. [Integration Guide](#integration-guide)

---

## Overview

The Vectro backend is a Node.js/Express REST API that:
- Manages user authentication with email verification via Supabase Auth
- Stores user profiles, documents, and saved schemes in Supabase PostgreSQL
- Integrates with an independent RAG (Retrieval-Augmented Generation) service for AI-powered scheme discovery
- Handles file uploads to Supabase Storage for document management

**Base URL**: `http://localhost:5000/api`

**Tech Stack**:
- **Runtime**: Node.js (ES Modules)
- **Framework**: Express.js
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth (JWT-based)
- **Storage**: Supabase Storage
- **RAG Service**: FastAPI (Python) - Independent service

---

## Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Frontend  │ ────▶│  Node.js Backend │ ────▶│  Supabase    │
│  (React)    │      │   (Express)      │      │  (Auth/DB)   │
└─────────────┘      └──────────────────┘      └──────────────┘
                              │
                              │
                              ▼
                     ┌──────────────┐
                     │  RAG Service │
                     │  (FastAPI)   │
                     └──────────────┘
```

### File Structure

```
backend/
├── config/
│   ├── supabase.js      # Supabase client (admin + anon)
│   └── rag.js           # RAG service axios client
├── database/
│   └── schema.sql       # PostgreSQL schema + RLS policies
├── middleware/
│   └── auth.js          # JWT authentication middleware
├── routes/
│   ├── auth.js          # Authentication endpoints
│   ├── users.js         # User profiles & saved schemes
│   ├── schemes.js       # Scheme discovery & details
│   └── documents.js     # Document management
├── utils/
│   └── helpers.js       # Utility functions
├── server.js            # Main Express app
├── package.json         # Dependencies
└── .env                 # Environment variables
```

---

## API Endpoints

### Health Check

#### `GET /health`

Check if the API is running.

**Response**:
```json
{
  "status": "ok",
  "message": "Vectro API is running",
  "timestamp": "2026-01-15T10:30:00.000Z"
}
```

---

### Authentication Routes

Base path: `/api/auth`

#### `POST /auth/signup`

Register a new user account. Sends verification email automatically.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "John Doe"
}
```

**Validation**:
- `email`: Required, valid email format
- `password`: Required, minimum 6 characters
- `name`: Required

**Response** (201 Created):
```json
{
  "message": "User created successfully. Please check your email to verify your account.",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar": null,
    "emailVerified": false
  },
  "requiresEmailVerification": true
}
```

**Error Responses**:
- `400`: Missing fields or invalid data
- `500`: Server error

---

#### `POST /auth/login`

Login with email and password.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response** (200 OK):
```json
{
  "message": "Login successful",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar": null
  },
  "session": {
    "access_token": "jwt_token_here",
    "refresh_token": "refresh_token_here",
    "expires_in": 3600,
    "token_type": "bearer"
  }
}
```

**Error Responses**:
- `400`: Missing credentials
- `401`: Invalid credentials or unverified email
- `500`: Server error

**Notes**:
- Email must be verified before login
- Store `access_token` in frontend for authenticated requests
- Use `refresh_token` to get new access token when expired

---

#### `POST /auth/verify-email`

Verify email address with token from verification email.

**Request Body**:
```json
{
  "token": "verification_token_from_email",
  "type": "signup"
}
```

**Response** (200 OK):
```json
{
  "message": "Email verified successfully",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar": null,
    "emailVerified": true
  },
  "session": {
    "access_token": "jwt_token_here",
    "refresh_token": "refresh_token_here"
  }
}
```

**Error Responses**:
- `400`: Invalid or expired token
- `500`: Server error

---

#### `POST /auth/resend-verification`

Resend verification email.

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200 OK):
```json
{
  "message": "Verification email sent successfully"
}
```

---

#### `POST /auth/logout`

Logout current user (invalidates session).

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "message": "Logout successful"
}
```

---

#### `GET /auth/me`

Get current authenticated user information.

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar": null
  }
}
```

**Error Responses**:
- `401`: Unauthorized (missing or invalid token)

---

#### `POST /auth/refresh`

Refresh access token using refresh token.

**Request Body**:
```json
{
  "refresh_token": "refresh_token_here"
}
```

**Response** (200 OK):
```json
{
  "message": "Token refreshed successfully",
  "session": {
    "access_token": "new_jwt_token",
    "refresh_token": "new_refresh_token",
    "expires_in": 3600
  }
}
```

---

### User Routes

Base path: `/api/users`

All routes require authentication (`Authorization: Bearer <token>`).

#### `GET /users/:userId/profile`

Get user's eligibility profile data.

**Response** (200 OK):
```json
{
  "profile": {
    "id": "uuid",
    "user_id": "uuid",
    "age": 25,
    "gender": "male",
    "income": 500000,
    "state": "Maharashtra",
    "occupation": "private",
    "family_size": 4,
    "has_disability": false,
    "residence": "urban",
    "category": "general",
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-01-15T10:00:00Z"
  }
}
```

**Notes**:
- Returns `null` if profile doesn't exist yet
- User can only access their own profile (403 otherwise)

---

#### `PUT /users/:userId/profile`

Create or update user profile.

**Request Body**:
```json
{
  "age": 25,
  "gender": "male",
  "income": 500000,
  "state": "Maharashtra",
  "occupation": "private",
  "familySize": 4,
  "hasDisability": false,
  "residence": "urban",
  "category": "general"
}
```

**Response** (200 OK):
```json
{
  "message": "Profile updated successfully",
  "profile": {
    "id": "uuid",
    "user_id": "uuid",
    "age": 25,
    "gender": "male",
    "income": 500000,
    "state": "Maharashtra",
    "occupation": "private",
    "family_size": 4,
    "has_disability": false,
    "residence": "urban",
    "category": "general",
    "updated_at": "2026-01-15T10:00:00Z"
  }
}
```

---

#### `GET /users/:userId/saved-schemes`

Get all schemes saved by the user.

**Response** (200 OK):
```json
{
  "schemes": [
    {
      "id": "uuid",
      "name": "Pradhan Mantri Awas Yojana",
      "nameHi": "प्रधानमंत्री आवास योजना",
      "category": "Housing",
      "categoryHi": "आवास",
      "benefit": "Up to ₹2.5 lakh subsidy",
      "benefitHi": "₹2.5 लाख तक सब्सिडी",
      "deadline": "Open",
      "savedAt": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

#### `POST /users/:userId/saved-schemes`

Save a scheme to user's list.

**Request Body**:
```json
{
  "schemeId": "uuid"
}
```

**Response** (201 Created):
```json
{
  "message": "Scheme saved successfully",
  "savedScheme": {
    "id": "uuid",
    "user_id": "uuid",
    "scheme_id": "uuid",
    "saved_at": "2026-01-15T10:00:00Z"
  }
}
```

**Error Responses**:
- `409`: Scheme already saved

---

#### `DELETE /users/:userId/saved-schemes/:schemeId`

Remove a scheme from saved list.

**Response** (200 OK):
```json
{
  "message": "Scheme removed from saved list"
}
```

---

### Scheme Routes

Base path: `/api/schemes`

#### `POST /schemes/discover`

Discover government schemes based on user profile using RAG service.

**Authentication**: Optional (can be used without login)

**Request Body**:
```json
{
  "gender": "male",
  "age": "25",
  "state": "Maharashtra",
  "residence": "urban",
  "category": "general",
  "income": "5",
  "occupation": "private"
}
```

**Field Descriptions**:
- `age`: Age in years (string)
- `gender`: "male", "female", or "other"
- `state`: Full state name (e.g., "Maharashtra", "Delhi")
- `residence`: "urban" or "rural"
- `category`: "general", "obc", "sc", "st", or "ews"
- `income`: Annual income in Lakhs (string, e.g., "5" = 5 Lakhs)
- `occupation`: "govt_service", "private", "business", "agriculture", "student", or "unemployed"

**Response** (200 OK):
```json
{
  "message": "Schemes discovered successfully",
  "totalSchemes": 5,
  "schemes": [
    {
      "id": 1,
      "schemeText": "Pradhan Mantri Awas Yojana (Urban)\\n...",
      "relevanceScore": 0.85,
      "name": "Pradhan Mantri Awas Yojana (Urban)"
    }
  ],
  "query": "User profile for scheme matching"
}
```

**Notes**:
- Backend automatically converts income from Lakhs to rupees
- Maps `category` to RAG's `caste` field
- Maps `residence` to RAG's `residency` field
- Returns top 5 most relevant schemes from RAG service

---

#### `GET /schemes/:schemeId`

Get detailed information about a specific scheme.

**Response** (200 OK):
```json
{
  "scheme": {
    "id": "uuid",
    "name": "Pradhan Mantri Awas Yojana",
    "nameHi": "प्रधानमंत्री आवास योजना",
    "category": "Housing",
    "categoryHi": "आवास",
    "benefit": "Up to ₹2.5 lakh subsidy",
    "benefitHi": "₹2.5 लाख तक सब्सिडी",
    "deadline": "Open",
    "deadlineHi": "खुला",
    "description": "Affordable housing for all...",
    "descriptionHi": "सभी के लिए किफायती आवास...",
    "eligibility": ["Indian citizen", "Annual income < 18 lakhs"],
    "eligibilityHi": ["भारतीय नागरिक", "वार्षिक आय < 18 लाख"],
    "benefits": ["Interest subsidy", "Credit-linked subsidy"],
    "benefitsHi": ["ब्याज सब्सिडी", "क्रेडिट से जुड़ी सब्सिडी"],
    "documents": ["Aadhar Card", "Income Certificate"],
    "documentsHi": ["आधार कार्ड", "आय प्रमाण पत्र"],
    "applicationProcess": ["Visit official website", "Register..."],
    "applicationProcessHi": ["आधिकारिक वेबसाइट पर जाएं", "पंजीकरण..."],
    "officialWebsite": "https://pmaymis.gov.in",
    "ministry": "Ministry of Housing and Urban Affairs",
    "ministryHi": "आवास और शहरी कार्य मंत्रालय"
  }
}
```

**Error Responses**:
- `404`: Scheme not found

---

#### `GET /schemes`

Get all schemes with optional filtering.

**Query Parameters**:
- `category`: Filter by category (optional)
- `ministry`: Filter by ministry (optional)
- `limit`: Number of results (default: 50, max: 100)
- `offset`: Pagination offset (default: 0)

**Example**: `GET /schemes?category=Housing&limit=10`

**Response** (200 OK):
```json
{
  "schemes": [
    {
      "id": "uuid",
      "name": "Pradhan Mantri Awas Yojana",
      "nameHi": "प्रधानमंत्री आवास योजना",
      "category": "Housing",
      "categoryHi": "आवास",
      "benefit": "Up to ₹2.5 lakh subsidy",
      "benefitHi": "₹2.5 लाख तक सब्सिडी",
      "deadline": "Open",
      "ministry": "Ministry of Housing and Urban Affairs"
    }
  ],
  "total": 100,
  "limit": 10,
  "offset": 0
}
```

---

#### `POST /schemes`

Create a new scheme (admin only - auth required).

**Request Body**: Full scheme object (same structure as GET response)

**Response** (201 Created):
```json
{
  "message": "Scheme created successfully",
  "scheme": { ... }
}
```

---

### Document Routes

Base path: `/api/documents`

All routes require authentication.

#### `GET /documents/:userId`

Get all document tracking records for a user.

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "document_type": "aadhar_card",
      "has_document": true,
      "uploaded_file": "https://supabase.co/storage/...",
      "verification_status": "verified",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    },
    {
      "id": "uuid",
      "user_id": "uuid",
      "document_type": "pan_card",
      "has_document": false,
      "uploaded_file": null,
      "verification_status": "pending",
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

**Document Types**:
- `aadhar_card`
- `pan_card`
- `income_certificate`
- `caste_certificate`
- `domicile_certificate`
- `bank_passbook`
- `ration_card`
- `disability_certificate`

**Notes**:
- If no documents exist, automatically initializes all 8 document types with `has_document: false`

---

#### `PUT /documents/:userId/:documentId`

Update document status (mark as having/not having document).

**Request Body**:
```json
{
  "hasDocument": true
}
```

**Response** (200 OK):
```json
{
  "message": "Document updated successfully",
  "document": {
    "id": "uuid",
    "user_id": "uuid",
    "document_type": "aadhar_card",
    "has_document": true,
    "updated_at": "2026-01-15T10:00:00Z"
  }
}
```

---

#### `POST /documents/:userId/upload`

Upload a document file to Supabase Storage.

**Request Body**:
```json
{
  "documentType": "aadhar_card",
  "fileName": "aadhar.pdf",
  "fileData": "base64_encoded_file_data"
}
```

**Response** (200 OK):
```json
{
  "message": "Document uploaded successfully",
  "document": {
    "id": "uuid",
    "user_id": "uuid",
    "document_type": "aadhar_card",
    "has_document": true,
    "uploaded_file": "https://supabase.co/storage/...",
    "verification_status": "pending",
    "updated_at": "2026-01-15T10:00:00Z"
  },
  "fileUrl": "https://supabase.co/storage/..."
}
```

**Notes**:
- Files are stored in Supabase Storage bucket: `documents`
- Path structure: `{userId}/{documentType}/{timestamp}_{fileName}`
- Automatically sets `has_document: true` and `verification_status: pending`
- Only user can access their own files (RLS policies enforce this)

---

#### `DELETE /documents/:userId/:documentId/file`

Delete uploaded document file from storage.

**Response** (200 OK):
```json
{
  "message": "Document file deleted successfully",
  "document": {
    "id": "uuid",
    "uploaded_file": null,
    "verification_status": "pending",
    "updated_at": "2026-01-15T10:00:00Z"
  }
}
```

---

## Data Models

### User (Supabase Auth + profiles table)

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  avatar TEXT,
  google_id TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### User Profile

```sql
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  age INTEGER,
  gender TEXT,
  income NUMERIC,
  state TEXT,
  occupation TEXT,
  family_size INTEGER,
  has_disability BOOLEAN DEFAULT FALSE,
  residence TEXT,
  category TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id)
);
```

### Scheme

```sql
CREATE TABLE schemes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  name_hi TEXT,
  category TEXT NOT NULL,
  category_hi TEXT,
  benefit TEXT NOT NULL,
  benefit_hi TEXT,
  deadline TEXT,
  deadline_hi TEXT,
  description TEXT,
  description_hi TEXT,
  eligibility JSONB,
  eligibility_hi JSONB,
  benefits JSONB,
  benefits_hi JSONB,
  documents JSONB,
  documents_hi JSONB,
  application_process JSONB,
  application_process_hi JSONB,
  official_website TEXT,
  ministry TEXT,
  ministry_hi TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Saved Scheme (Junction Table)

```sql
CREATE TABLE saved_schemes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  scheme_id UUID NOT NULL REFERENCES schemes(id),
  saved_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, scheme_id)
);
```

### User Document

```sql
CREATE TABLE user_documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  document_type TEXT NOT NULL,
  has_document BOOLEAN DEFAULT FALSE,
  uploaded_file TEXT,
  verification_status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, document_type)
);
```

---

## Authentication Flow

### 1. User Registration

```
Frontend                    Backend                     Supabase
   │                          │                            │
   ├─POST /auth/signup───────▶│                            │
   │  email, password, name   │                            │
   │                          ├─signUp()──────────────────▶│
   │                          │                            │
   │                          │◀────user created───────────┤
   │                          │  (email verification sent) │
   │◀─requiresVerification────┤                            │
   │                          │                            │
```

### 2. Email Verification

```
User Email                  Frontend                    Backend
   │                          │                            │
   ├─Click verify link───────▶│                            │
   │  (contains token)        │                            │
   │                          ├─POST /auth/verify-email──▶│
   │                          │  token, type               │
   │                          │                            │
   │                          │◀─session + user────────────┤
   │                          │  (access_token stored)     │
```

### 3. Login

```
Frontend                    Backend                     Supabase
   │                          │                            │
   ├─POST /auth/login────────▶│                            │
   │  email, password         │                            │
   │                          ├─signInWithPassword()─────▶│
   │                          │                            │
   │                          │◀─session + user────────────┤
   │◀─user + session──────────┤                            │
   │  (store access_token)    │                            │
```

### 4. Authenticated Requests

```
Frontend                    Backend                     Supabase
   │                          │                            │
   ├─GET /users/:id/profile──▶│                            │
   │  Header: Bearer <token>  │                            │
   │                          ├─verifyToken()─────────────▶│
   │                          │                            │
   │                          │◀─user valid────────────────┤
   │                          ├─query database────────────▶│
   │◀─profile data────────────┤                            │
```

### 5. Token Refresh

```
Frontend                    Backend                     Supabase
   │                          │                            │
   ├─POST /auth/refresh──────▶│                            │
   │  refresh_token           │                            │
   │                          ├─refreshSession()─────────▶│
   │                          │                            │
   │                          │◀─new tokens───────────────┤
   │◀─new session─────────────┤                            │
   │  (update stored tokens)  │                            │
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Error Name",
  "message": "Human-readable error description",
  "stack": "..." // Only in development mode
}
```

### HTTP Status Codes

- **200 OK**: Successful request
- **201 Created**: Resource successfully created
- **400 Bad Request**: Invalid input or validation error
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: User doesn't have permission
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Resource already exists (e.g., duplicate save)
- **500 Internal Server Error**: Server-side error

### Common Error Scenarios

**401 Unauthorized**:
- Missing Authorization header
- Invalid or expired JWT token
- Email not verified

**403 Forbidden**:
- Trying to access another user's data
- Trying to modify another user's resources

**400 Bad Request**:
- Missing required fields
- Invalid data format
- Password too short
- Passwords don't match

---

## Integration Guide

### Frontend Setup

1. **Install axios**:
```bash
npm install axios
```

2. **Create API client** ([frontend/src/lib/api.js](frontend/src/lib/api.js)):
```javascript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:5000/api',
  timeout: 30000,
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const session = localStorage.getItem('supabase_session');
  if (session) {
    const { access_token } = JSON.parse(session);
    config.headers.Authorization = `Bearer ${access_token}`;
  }
  return config;
});

export const authAPI = {
  signup: (email, password, name) => 
    apiClient.post('/auth/signup', { email, password, name }),
  login: (email, password) => 
    apiClient.post('/auth/login', { email, password }),
  // ... other methods
};
```

3. **Use in components**:
```javascript
import { authAPI } from '@/lib/api';

const handleLogin = async (email, password) => {
  try {
    const { data } = await authAPI.login(email, password);
    localStorage.setItem('supabase_session', JSON.stringify(data.session));
    localStorage.setItem('user', JSON.stringify(data.user));
    // Navigate to dashboard
  } catch (error) {
    console.error('Login failed:', error.response?.data?.message);
  }
};
```

### Backend Deployment

1. **Environment Variables** (.env):
```env
PORT=5000
NODE_ENV=production
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_key
RAG_SERVICE_URL=https://your-rag-service.com
FRONTEND_URL=https://your-frontend.com
```

2. **Start server**:
```bash
npm install
npm start
```

3. **Database setup**:
- Run `backend/database/schema.sql` in Supabase SQL Editor
- Enable email confirmations in Supabase Auth settings
- Configure email templates (optional)

### RAG Service Integration

The backend communicates with an independent RAG (FastAPI) service:

**RAG Endpoint**: `POST /find-schemes`

**Request to RAG**:
```json
{
  "age": 25,
  "gender": "male",
  "income": 500000,
  "state": "Maharashtra",
  "occupation": "private",
  "caste": "general",
  "residency": "urban"
}
```

**Response from RAG**:
```json
{
  "query": "User profile for matching",
  "total_schemes": 5,
  "results": [
    {
      "index": 0,
      "scheme_text": "Pradhan Mantri Awas Yojana...",
      "relevance_score": 0.85
    }
  ]
}
```

The backend (`/api/schemes/discover`) transforms frontend data format to RAG format automatically.

---

## Testing

### Using cURL

**Signup**:
```bash
curl -X POST http://localhost:5000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","name":"Test User"}'
```

**Login**:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Get Profile** (requires token):
```bash
curl -X GET http://localhost:5000/api/users/{userId}/profile \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Discover Schemes**:
```bash
curl -X POST http://localhost:5000/api/schemes/discover \
  -H "Content-Type: application/json" \
  -d '{
    "age": "25",
    "gender": "male",
    "state": "Maharashtra",
    "residence": "urban",
    "category": "general",
    "income": "5",
    "occupation": "private"
  }'
```

### Using Postman

1. Import the base URL: `http://localhost:5000/api`
2. Create an environment variable for `access_token`
3. Set Bearer token authentication using `{{access_token}}`
4. Test each endpoint systematically

---

## Security Best Practices

1. **Never commit `.env` file** - Contains sensitive keys
2. **Use Row Level Security (RLS)** - Already configured in schema.sql
3. **Validate all input** - Backend validates before database operations
4. **Use HTTPS in production** - Required for secure token transmission
5. **Rotate keys regularly** - Especially service_role key
6. **Enable rate limiting** - Consider adding express-rate-limit middleware
7. **Monitor logs** - Check Supabase dashboard for suspicious activity

---

## Support & Contributing

For issues or questions:
- Create a GitHub issue
- Check backend logs: `npm run dev` shows real-time logs
- Check Supabase logs in dashboard under "Logs" section

---

**Last Updated**: January 15, 2026  
**Version**: 1.0.0  
**Backend Port**: 5000  
**RAG Service Port**: 7860
