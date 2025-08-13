# Raketrapport - Financial Report Generator

A comprehensive system for parsing Swedish SE files and generating financial reports.

## Project Structure

```
Raketrapport/
├── backend/           # FastAPI Python backend
│   ├── main.py       # Main API server
│   ├── services/     # Business logic services
│   ├── models/       # Data models and schemas
│   ├── supabase/     # Database migrations
│   └── utils/        # Utility functions
├── frontend/         # React TypeScript frontend
│   ├── src/          # Source code
│   ├── components/   # React components
│   └── pages/        # Page components
└── README.md         # This file
```

## Features

- **SE File Parsing**: Parse Swedish accounting SE files
- **Database-Driven**: Variable mappings stored in database (no hardcoding)
- **Financial Reports**: Generate RR (Resultaträkning) and BR (Balansräkning)
- **Modern UI**: React frontend with TypeScript
- **Scalable Backend**: FastAPI with Supabase database

## Technology Stack

- **Backend**: Python FastAPI
- **Frontend**: React + TypeScript + Vite
- **Database**: Supabase (PostgreSQL)
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui

## Getting Started

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Database Setup
```bash
cd backend
supabase db push
python scripts/populate_variable_mappings.py
```

## Database Schema

The system uses a database-driven approach instead of hardcoded structures:

- **`variable_mapping_rr`**: RR (Resultaträkning) variable definitions
- **`variable_mapping_br`**: BR (Balansräkning) variable definitions
- **`financial_data`**: Actual financial values (replaces JSON approach)
- **`companies`**: Company information
- **`accounting_reports`**: Report metadata

## Benefits of New Architecture

1. **No Hardcoding**: All variable definitions in database
2. **Easy Updates**: Change account ranges without code changes
3. **Better Performance**: Direct column access vs JSON parsing
4. **Data Integrity**: Proper data types and constraints
5. **Easy Debugging**: Direct access to variable values
6. **Scalability**: Add new variables without code changes
# Force deployment - Wed Aug 13 12:25:11 CEST 2025
