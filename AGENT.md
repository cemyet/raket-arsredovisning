# Raketrapport - Agent Development Guide

## Build/Lint/Test Commands
- **Frontend**: `cd frontend && npm run dev` (development), `npm run build` (production), `npm run lint` (eslint)
- **Backend**: `cd backend && python main.py` (run server), `python test_database.py` (single test file)
- No test framework configured - check for individual test files like `test_*.py`

## Architecture
- **Frontend**: React + TypeScript + Vite, shadcn/ui components, Tailwind CSS, React Router, TanStack Query
- **Backend**: FastAPI (Python), Supabase PostgreSQL database, services pattern (services/, models/, utils/)
- **Database**: Supabase with tables: variable_mapping_rr/br, financial_data, companies, accounting_reports
- **Key Services**: ReportGenerator, SupabaseService, DatabaseParser in backend/services/

## Code Style Guidelines
- **TypeScript**: Loose config (noImplicitAny: false, strictNullChecks: false), `@/` path alias for src/
- **Imports**: Use `@/` for internal imports, group external then internal imports
- **Components**: Functional components with TypeScript interfaces, use `cn()` from "@/lib/utils" for className merging
- **Naming**: PascalCase for components, camelCase for functions/variables, kebab-case for files
- **Backend**: Snake_case for Python following PEP 8, services pattern with dependency injection
- **Error Handling**: FastAPI HTTPExceptions with proper status codes, try/catch in frontend with proper error boundaries

## Database-First Approach
- Variable mappings stored in database (not hardcoded), use database services for all data operations
